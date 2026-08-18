#!/usr/bin/env python3
"""Safe entry point for the checkpointed Codex core repeatability campaign.

The implementation lives in ``_codex_core_repeatability``. This entry point
adds one campaign-level state snapshot around all child runs, forwards an
interrupt to the active child before falling back to termination, atomically
checkpoints combined evidence, and repairs resumable checkpoints from their
manifest. The outer snapshot protects the user's Codex marketplace, plugin,
and ``config.toml`` state even when a child is interrupted between cleanup
steps.
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
        self.repo_root = getattr(self.guard, "repo_root", _impl.ROOT)
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
            current_before = base.read_plugin_state(
                self.launchers, self.repo_root
            )
            # An interrupted child may have added the marketplace. Mark it as
            # parent-added only when it is still present and was absent in the
            # snapshot, avoiding a double-remove after normal child cleanup.
            self.guard.marketplace_added = (
                current_before.marketplace_existed
                and not self.guard.original.marketplace_existed
            )
            self.guard.__exit__(exc_type, exc, tb)
        except BaseException as error:  # restoration must be reported even on interrupt
            self.restore_error = str(error)

        try:
            self.current_state = base.read_plugin_state(
                self.launchers, self.repo_root
            )
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


def atomic_write_runs(path: Path, rows: list[dict[str, Any]]) -> None:
    """Atomically replace parent JSONL so an interrupt cannot leave a torn file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
            for row in rows
        ),
        encoding="utf-8",
        newline="\n",
    )
    os.replace(temporary, path)


def rebuild_parent_runs(
    campaign: Path,
    manifest: dict[str, Any],
) -> list[dict[str, Any]]:
    """Reconstruct parent rows from manifest-authorized PASS children only."""
    completed = manifest.get("completed", [])
    if not isinstance(completed, list):
        raise base.HarnessError("repeatability manifest has an invalid completed list.")
    parent_campaign_id = manifest.get("campaign_id")
    harness_commit = manifest.get("harness_commit")
    if not isinstance(parent_campaign_id, str) or not parent_campaign_id:
        raise base.HarnessError("repeatability manifest omitted campaign_id.")
    if not isinstance(harness_commit, str) or not harness_commit:
        raise base.HarnessError("repeatability manifest omitted harness_commit.")

    rows: list[dict[str, Any]] = []
    for record in completed:
        if not isinstance(record, dict):
            raise base.HarnessError("repeatability manifest contains a non-object child.")
        if record.get("outcome") != "PASS" or not record.get("plugin_state_restored"):
            raise base.HarnessError(
                "resumable manifest contains a child that is not a restored PASS."
            )
        case_key = record.get("case_key")
        repetition = record.get("repetition")
        child_relative = record.get("child_campaign")
        if case_key not in _impl.CASES or type(repetition) is not int:
            raise base.HarnessError("resumable manifest contains invalid child identity.")
        if not isinstance(child_relative, str) or not child_relative:
            raise base.HarnessError("resumable manifest child omitted its campaign path.")
        child_campaign = (campaign / child_relative).resolve()
        if not _impl.path_under(child_campaign, campaign) or not child_campaign.is_dir():
            raise base.HarnessError(
                f"resumable child campaign is unsafe or missing: {child_relative}"
            )
        source_rows = _impl.load_jsonl(child_campaign / "runs.jsonl")
        rows.extend(
            _impl.transform_rows(
                rows=source_rows,
                child_campaign=child_campaign,
                parent_campaign=campaign,
                parent_campaign_id=parent_campaign_id,
                spec=_impl.CASES[str(case_key)],
                repetition=repetition,
                harness_commit=harness_commit,
            )
        )

    runs_path = campaign / "runs.jsonl"
    if rows:
        atomic_write_runs(runs_path, rows)
    else:
        runs_path.unlink(missing_ok=True)
    return rows


def validate_resume_environment(
    campaign: Path,
    *,
    launchers: base.CodexLaunchers,
    subject_version: str,
) -> dict[str, Any] | None:
    manifest = _impl.load_json(campaign / "manifest.json")
    expected_client = ".".join(str(part) for part in launchers.version)
    if manifest.get("client_version") != expected_client:
        raise base.HarnessError(
            "resume refused because the Codex CLI version changed: "
            f"manifest={manifest.get('client_version')!r}, current={expected_client!r}."
        )
    if manifest.get("subject_version") != subject_version:
        raise base.HarnessError(
            "resume refused because the core subject version changed: "
            f"manifest={manifest.get('subject_version')!r}, current={subject_version!r}."
        )
    rebuild_parent_runs(campaign, manifest)
    completed = manifest.get("completed", [])
    if not completed:
        return None
    if not isinstance(completed, list):
        raise base.HarnessError("resume manifest has an invalid completed list.")
    return _impl.ensure_identity_stable(completed)


def finalize_failure(
    *,
    campaign: Path,
    manifest: dict[str, Any],
    reason: str,
    record: dict[str, Any] | None = None,
) -> None:
    outcome = "FAIL"
    if record is not None and record.get("outcome") in {"INVALID", "HARNESS_ERROR"}:
        outcome = str(record["outcome"])
    manifest["outcome"] = outcome
    manifest["updated_at"] = _impl.utc_now()
    manifest["failure_reason"] = reason
    _impl.atomic_write_json(campaign / "manifest.json", manifest)
    payload = {
        "campaign": campaign.name,
        "outcome": outcome,
        "reason": reason,
        "failed_child": record,
        "completed_children": manifest.get("completed", []),
        "resume_allowed": False,
    }
    _impl.atomic_write_json(campaign / "failure-diagnostics.json", payload)
    print("\nREPEATABILITY FAILURE DIAGNOSTICS")
    print(f"  outcome: {outcome}")
    print(f"  reason : {reason}")
    if record:
        print(f"  child  : {record.get('step_id')}")
        print(f"  child-outcome: {record.get('outcome')}")
        print(f"  summary: {record.get('summary_path')}")
        print(f"  transcript: {record.get('transcript_path')}")
    print(f"  file   : {campaign / 'failure-diagnostics.json'}")


def guarded_run_child(
    original_run_child: Any,
    identity_box: dict[str, dict[str, Any] | None],
) -> Any:
    def run(**kwargs: Any) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        record, rows = original_run_child(**kwargs)
        if record.get("outcome") != "PASS":
            return record, rows
        identity = record.get("identity")
        if not isinstance(identity, dict):
            record["outcome"] = "HARNESS_ERROR"
            record["exit_code"] = 1
            record["error"] = "PASS child omitted stable identity evidence."
            return record, rows
        canonical = identity_box.get("canonical")
        if canonical is None:
            identity_box["canonical"] = dict(identity)
        elif identity != canonical:
            record["outcome"] = "HARNESS_ERROR"
            record["exit_code"] = 1
            record["error"] = (
                "model/client/subject identity drifted before the next child was allowed: "
                f"found={json.dumps(identity, ensure_ascii=False)}, "
                f"expected={json.dumps(canonical, ensure_ascii=False)}"
            )
        return record, rows

    return run


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
        if not guard.restored:
            manifest["outcome"] = "HARNESS_ERROR"
            manifest["failure_reason"] = (
                "campaign-level Codex state restoration could not be verified."
            )
        _impl.atomic_write_json(manifest_path, manifest)

    summary_path = campaign / "summary.json"
    if summary_path.is_file():
        summary = _impl.load_json(summary_path)
        summary["parent_state_restored"] = guard.restored
        summary["parent_state_evidence"] = path.name
        if not guard.restored:
            summary["outcome"] = "HARNESS_ERROR"
            summary["error"] = (
                "campaign-level Codex state restoration could not be verified."
            )
        _impl.atomic_write_json(summary_path, summary)
    return path


def main() -> int:
    if "--dry-run" in sys.argv or "--confirm-live" not in sys.argv:
        return _impl.main()

    launchers = base.resolve_codex_launchers()
    subject_version = base.load_catalog()
    captured_campaign: dict[str, Path] = {}
    resume_campaign = _resume_campaign_argument()
    canonical_identity: dict[str, Any] | None = None
    if resume_campaign is not None:
        captured_campaign["path"] = resume_campaign
        canonical_identity = validate_resume_environment(
            resume_campaign,
            launchers=launchers,
            subject_version=subject_version,
        )

    original_campaign_directory = _impl.campaign_directory
    original_stream_process = _impl.stream_process
    original_write_runs = _impl.write_runs
    original_run_child = _impl.run_child
    original_finalize_failure = _impl.finalize_failure
    identity_box: dict[str, dict[str, Any] | None] = {
        "canonical": canonical_identity,
    }

    def capture_campaign(output_root: Path) -> Path:
        campaign = original_campaign_directory(output_root)
        captured_campaign["path"] = campaign
        return campaign

    _impl.campaign_directory = capture_campaign
    _impl.stream_process = interruptible_stream_process
    _impl.write_runs = atomic_write_runs
    _impl.run_child = guarded_run_child(original_run_child, identity_box)
    _impl.finalize_failure = finalize_failure
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
        _impl.write_runs = original_write_runs
        _impl.run_child = original_run_child
        _impl.finalize_failure = original_finalize_failure
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
