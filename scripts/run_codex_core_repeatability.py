#!/usr/bin/env python3
"""Safe entry point for the checkpointed Codex core repeatability campaign.

The implementation lives in ``_codex_core_repeatability``. This entry point
adds one campaign-level state snapshot around all child runs and forwards an
interrupt to the active child before falling back to termination. The outer
snapshot protects the user's Codex marketplace, plugin, and ``config.toml``
state even when a child process is interrupted between its own cleanup steps.
"""
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import tempfile
from contextlib import AbstractContextManager
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import _codex_core_repeatability as _impl
from _codex_core_repeatability import *  # noqa: F401,F403 - compatibility re-export
import run_codex_live_smoke as base

INTERRUPT_GRACE_SECONDS = 30


def plugin_states_equal(
    left: base.OriginalPluginState,
    right: base.OriginalPluginState,
) -> bool:
    roots_equal = (
        left.marketplace_root == right.marketplace_root
        if left.marketplace_root is None or right.marketplace_root is None
        else base.normalized_path(left.marketplace_root)
        == base.normalized_path(right.marketplace_root)
    )
    return (
        left.marketplace_existed == right.marketplace_existed
        and roots_equal
        and left.plugin_installed == right.plugin_installed
        and left.plugin_enabled == right.plugin_enabled
        and left.plugin_version == right.plugin_version
    )


def plugin_state_payload(state: base.OriginalPluginState) -> dict[str, Any]:
    return {
        "marketplace_existed": state.marketplace_existed,
        "marketplace_root": state.marketplace_root,
        "plugin_installed": state.plugin_installed,
        "plugin_enabled": state.plugin_enabled,
        "plugin_version": state.plugin_version,
    }


class CampaignStateGuard(AbstractContextManager["CampaignStateGuard"]):
    """Restore exact user Codex state after the complete parent campaign."""

    def __init__(
        self,
        *,
        launchers: base.CodexLaunchers,
        subject_version: str,
    ) -> None:
        self.launchers = launchers
        self.guard = base.PluginStateGuard(
            launchers=launchers,
            repo_root=_impl.ROOT,
            candidate_version=subject_version,
        )
        self.codex_home: Path | None = None
        self.restored = False
        self.restore_error: str | None = None
        self.current_state: base.OriginalPluginState | None = None
        self.config_restored = False

    def __enter__(self) -> "CampaignStateGuard":
        with tempfile.TemporaryDirectory(
            prefix="engineering-foundation-repeatability-state-"
        ) as tmp:
            with base.AppServer(
                command=self.launchers.app_server_command,
                node_executable=self.launchers.node_executable,
                cwd=_impl.ROOT,
                trace_path=Path(tmp) / "home-trace.jsonl",
                timeout_seconds=120,
            ) as server:
                self.codex_home = server.initialize()
        self.guard.snapshot_config(self.codex_home)
        return self

    def _config_matches_snapshot(self) -> bool:
        if self.codex_home is None:
            return False
        config = self.codex_home / "config.toml"
        if self.guard.config_existed:
            return (
                self.guard.config_snapshot is not None
                and config.is_file()
                and config.read_bytes() == self.guard.config_snapshot
            )
        return not config.exists()

    def __exit__(self, exc_type: object, exc: object, tb: object) -> bool:
        try:
            current_before = base.read_plugin_state(self.launchers, _impl.ROOT)
            # The parent did not add the marketplace itself, but an interrupted
            # child may have done so. Tell the existing lossless restore logic
            # to remove it only when it is currently present and was absent in
            # the parent snapshot, avoiding a double-remove after normal child
            # cleanup.
            self.guard.marketplace_added = (
                current_before.marketplace_existed
                and not self.guard.original.marketplace_existed
            )
            self.guard.__exit__(exc_type, exc, tb)
        except BaseException as error:  # restoration must be reported even on interrupt
            self.restore_error = str(error)

        try:
            self.current_state = base.read_plugin_state(self.launchers, _impl.ROOT)
            self.config_restored = self._config_matches_snapshot()
            self.restored = (
                plugin_states_equal(self.current_state, self.guard.original)
                and self.config_restored
                and self.restore_error is None
            )
        except BaseException as error:
            detail = str(error)
            self.restore_error = (
                f"{self.restore_error} | verification failed: {detail}"
                if self.restore_error
                else f"verification failed: {detail}"
            )
            self.restored = False

        if not self.restored:
            message = "campaign-level Codex state restoration failed"
            if self.restore_error:
                message += f": {self.restore_error}"
            if exc is None:
                raise base.HarnessError(message)
            print(f"WARNING: {message}", file=sys.stderr)
        return False

    def evidence(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "restored": self.restored,
            "config_restored": self.config_restored,
            "restore_error": self.restore_error,
            "original": plugin_state_payload(self.guard.original),
            "current": (
                plugin_state_payload(self.current_state)
                if self.current_state is not None
                else None
            ),
        }


def _forward_interrupt(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    try:
        if os.name == "nt":
            process.send_signal(signal.CTRL_BREAK_EVENT)
        else:
            os.killpg(process.pid, signal.SIGINT)
        process.wait(timeout=INTERRUPT_GRACE_SECONDS)
        return
    except (AttributeError, OSError, subprocess.TimeoutExpired):
        pass

    try:
        process.terminate()
        process.wait(timeout=10)
        return
    except (OSError, subprocess.TimeoutExpired):
        pass

    if process.poll() is None:
        process.kill()
        process.wait()


def interruptible_stream_process(
    command: list[str],
    *,
    transcript_path: Path,
) -> int:
    """Stream a child while allowing its Python cleanup to receive Ctrl+C."""
    transcript_path.parent.mkdir(parents=True, exist_ok=True)
    popen_kwargs: dict[str, Any] = {
        "cwd": str(_impl.ROOT),
        "stdout": subprocess.PIPE,
        "stderr": subprocess.STDOUT,
        "text": True,
        "encoding": "utf-8",
        "errors": "replace",
        "bufsize": 1,
    }
    if os.name == "nt":
        popen_kwargs["creationflags"] = getattr(
            subprocess,
            "CREATE_NEW_PROCESS_GROUP",
            0,
        )
    else:
        popen_kwargs["start_new_session"] = True

    process = subprocess.Popen(command, **popen_kwargs)
    if process.stdout is None:
        process.kill()
        raise base.HarnessError("child live-smoke stdout could not be captured.")

    with transcript_path.open("w", encoding="utf-8", newline="\n") as transcript:
        try:
            for line in iter(process.stdout.readline, ""):
                print(line, end="")
                transcript.write(line)
                transcript.flush()
        except KeyboardInterrupt:
            _forward_interrupt(process)
            raise
    return process.wait()


def _resume_campaign_argument() -> Path | None:
    try:
        index = sys.argv.index("--resume")
    except ValueError:
        return None
    if index + 1 >= len(sys.argv):
        return None
    return Path(sys.argv[index + 1]).resolve()


def write_parent_state_evidence(
    campaign: Path,
    guard: CampaignStateGuard,
) -> Path:
    path = campaign / "parent-state-restoration.json"
    payload = guard.evidence()
    _impl.atomic_write_json(path, payload)

    manifest_path = campaign / "manifest.json"
    if manifest_path.is_file():
        manifest = _impl.load_json(manifest_path)
        manifest["parent_state_restored"] = guard.restored
        manifest["parent_state_evidence"] = path.name
        manifest["updated_at"] = _impl.utc_now()
        _impl.atomic_write_json(manifest_path, manifest)
    return path


def main() -> int:
    if "--dry-run" in sys.argv or "--confirm-live" not in sys.argv:
        return _impl.main()

    launchers = base.resolve_codex_launchers()
    subject_version = base.load_catalog()
    captured_campaign: dict[str, Path] = {}
    resume_campaign = _resume_campaign_argument()
    if resume_campaign is not None:
        captured_campaign["path"] = resume_campaign

    original_campaign_directory = _impl.campaign_directory
    original_stream_process = _impl.stream_process

    def capture_campaign(output_root: Path) -> Path:
        campaign = original_campaign_directory(output_root)
        captured_campaign["path"] = campaign
        return campaign

    _impl.campaign_directory = capture_campaign
    _impl.stream_process = interruptible_stream_process
    state_guard = CampaignStateGuard(
        launchers=launchers,
        subject_version=subject_version,
    )

    try:
        with state_guard:
            result = _impl.main()
    finally:
        _impl.campaign_directory = original_campaign_directory
        _impl.stream_process = original_stream_process
        campaign = captured_campaign.get("path")
        if campaign is not None and campaign.is_dir():
            evidence_path = write_parent_state_evidence(campaign, state_guard)
            print("\nCAMPAIGN STATE RESTORATION")
            print(f"  restored: {state_guard.restored}")
            print(f"  evidence: {evidence_path}")

    if not state_guard.restored:
        raise base.HarnessError(
            "repeatability campaign finished without verified parent-state restoration."
        )
    return result


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("ERROR: interrupted after checkpoint and state restoration.", file=sys.stderr)
        raise SystemExit(130)
    except (
        base.HarnessError,
        OSError,
        subprocess.SubprocessError,
        json.JSONDecodeError,
    ) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
