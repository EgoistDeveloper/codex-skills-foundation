#!/usr/bin/env python3
"""Qualify lifecycle and live behavior against one exact Core ZIP identity."""
from __future__ import annotations

import argparse
import json
import os
import platform
import signal
import shutil
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import release_candidate
import qualification_rehearsal
import qualification_workspace
import run_codex_live_smoke as live_base
import run_codex_core_repeatability as repeat_entry
from console_output import (
    write_console_safe,
    write_transcript_bundle,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / ".eval-runs" / "exact-artifact-qualification"


class QualificationError(RuntimeError):
    """Fail-closed exact-artifact qualification error."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_process(
    command: list[str],
    *,
    env: dict[str, str] | None = None,
    transcript: Path,
    timeout: float,
) -> None:
    popen_kwargs: dict[str, Any] = {
        "cwd": ROOT,
        "env": env,
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
    }
    if os.name == "nt":
        popen_kwargs["creationflags"] = getattr(
            subprocess, "CREATE_NEW_PROCESS_GROUP", 0
        )
    else:
        popen_kwargs["start_new_session"] = True
    process = subprocess.Popen(command, **popen_kwargs)
    timed_out = False
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        try:
            if os.name == "nt":
                process.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                os.killpg(process.pid, signal.SIGINT)
            stdout, stderr = process.communicate(
                timeout=repeat_entry.INTERRUPT_GRACE_SECONDS
            )
        except (AttributeError, OSError, subprocess.TimeoutExpired):
            process.terminate()
            try:
                stdout, stderr = process.communicate(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                stdout, stderr = process.communicate()
    stdout_bytes = bytes(stdout)
    stderr_bytes = bytes(stderr)
    stdout_text = stdout_bytes.decode("utf-8", errors="replace")
    stderr_text = stderr_bytes.decode("utf-8", errors="replace")
    write_transcript_bundle(
        transcript,
        "$ " + " ".join(command) + "\n\n" + stdout_text + stderr_text,
        stdout_bytes,
        stderr_bytes,
    )
    write_console_safe(sys.stdout, stdout_text)
    if stderr_text:
        write_console_safe(sys.stderr, stderr_text)
    if timed_out:
        raise QualificationError(
            f"exact-artifact command timed out after {timeout} seconds: "
            f"{' '.join(command)}"
        )
    if process.returncode != 0:
        raise QualificationError(
            f"exact-artifact command returned {process.returncode}: "
            f"{' '.join(command)}"
        )


def one_campaign(output: Path) -> Path:
    campaigns = sorted(path for path in output.iterdir() if path.is_dir())
    if len(campaigns) != 1:
        raise QualificationError(
            f"expected one campaign under {output}, found {len(campaigns)}"
        )
    return campaigns[0]


def load_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise QualificationError(f"cannot read qualification artifact {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise QualificationError(f"qualification artifact is not an object: {path}")
    return value


def load_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise QualificationError(f"cannot read live rows {path}: {exc}") from exc
    for line_number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise QualificationError(
                f"invalid live JSONL {path}:{line_number}: {exc}"
            ) from exc
        if not isinstance(value, dict):
            raise QualificationError(
                f"live JSONL row is not an object: {path}:{line_number}"
            )
        rows.append(value)
    return rows


def relative_artifact(path: Path, run_root: Path) -> dict[str, Any]:
    resolved = path.resolve(strict=True)
    try:
        relative = resolved.relative_to(run_root.resolve(strict=True)).as_posix()
    except ValueError as exc:
        raise QualificationError(f"artifact escaped bounded run: {path}") from exc
    return {"path": relative, "sha256": release_candidate.sha256_file(resolved)}


def command_version(command: str) -> str:
    executable = shutil.which(command)
    if not executable:
        return "NOT_USED"
    result = subprocess.run(
        [executable, "--version"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        return "NOT_USED"
    return (result.stdout.strip() or result.stderr.strip()).splitlines()[0]


def _contains_absolute_path(value: object) -> bool:
    if isinstance(value, dict):
        return any(_contains_absolute_path(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_absolute_path(item) for item in value)
    if not isinstance(value, str):
        return False
    if PurePosixPath(value).is_absolute():
        return True
    if len(value) >= 3 and value[1:3] in {":\\", ":/"}:
        return True
    return False


def copy_candidate_set(
    manifest_path: Path,
    artifacts: Path,
    destination: Path,
) -> tuple[Path, Path]:
    destination.mkdir(parents=True, exist_ok=False)
    manifest = load_object(manifest_path)
    expected = [
        str(package["archive_filename"]) for package in manifest.get("packages", [])
    ] + [release_candidate.CHECKSUM_FILENAME]
    for filename in expected:
        source = artifacts / filename
        if not source.is_file():
            raise QualificationError(f"candidate artifact is missing: {source}")
        shutil.copyfile(source, destination / filename)
    copied_manifest = destination / release_candidate.MANIFEST_FILENAME
    shutil.copyfile(manifest_path, copied_manifest)
    return copied_manifest, destination


def bounded_output_root(requested: Path) -> Path:
    """Accept raw H04 evidence only below the repository's ignored run root."""
    ignored_root = Path(os.path.abspath(ROOT / ".eval-runs"))
    lexical = Path(os.path.abspath(requested))
    try:
        relative = lexical.relative_to(ignored_root)
    except ValueError as exc:
        raise QualificationError(
            "exact-artifact output must stay under the ignored .eval-runs directory"
        ) from exc
    try:
        release_candidate._reject_link_or_reparse(ROOT)
        if ignored_root.exists() or ignored_root.is_symlink():
            release_candidate._reject_link_or_reparse(ignored_root)
        else:
            ignored_root.mkdir()
            release_candidate._reject_link_or_reparse(ignored_root)
        current = ignored_root
        for part in relative.parts:
            current /= part
            if current.exists() or current.is_symlink():
                release_candidate._reject_link_or_reparse(current)
    except (OSError, release_candidate.CandidateError) as exc:
        raise QualificationError(
            f"exact-artifact output contains a linked or unsafe component: {exc}"
        ) from exc
    return lexical


def validate_live_campaign(
    *,
    campaign: Path,
    manifest: dict[str, Any],
    manifest_digest: str,
    repeatability: bool,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    summary = load_object(campaign / "summary.json")
    if summary.get("outcome") != "PASS":
        raise QualificationError(f"live campaign did not PASS: {campaign}")
    if summary.get("plugin_state_restored") is not True and not (
        repeatability and summary.get("parent_state_restored") is True
    ):
        raise QualificationError(f"live campaign did not restore plugin state: {campaign}")
    rows = load_rows(campaign / "runs.jsonl")
    try:
        release_candidate.verify_live_rows(manifest, rows, manifest_digest)
    except release_candidate.CandidateError as exc:
        raise QualificationError(str(exc)) from exc
    return summary, rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-manifest", type=Path, required=True)
    parser.add_argument("--artifacts", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--confirm-live", action="store_true")
    parser.add_argument(
        "--zero-model-rehearsal",
        action="store_true",
        help="Exercise every qualification infrastructure path with zero model calls.",
    )
    parser.add_argument(
        "--lifecycle-only",
        action="store_true",
        help="Run the zero-model exact-artifact lifecycle only (for CI).",
    )
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--timeout-seconds", type=int, default=900)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if sum(bool(value) for value in (
        args.confirm_live,
        args.lifecycle_only,
        args.zero_model_rehearsal,
    )) != 1:
        raise QualificationError(
            "select exactly one qualification mode"
        )
    if args.repetitions != 3:
        raise QualificationError("canonical exact-artifact repeatability requires 3 repetitions")
    status = live_base.git(["status", "--porcelain"], cwd=ROOT)
    if status:
        raise QualificationError(f"foundation working tree must be clean:\n{status}")
    head = live_base.git(["rev-parse", "HEAD"], cwd=ROOT)
    manifest = release_candidate.verify_candidate_manifest(
        args.candidate_manifest,
        args.artifacts,
        repository=ROOT,
        expected_commit=head,
    )

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    output_root = bounded_output_root(args.output)
    output_root.mkdir(parents=True, exist_ok=True)
    run_root = output_root / f"{stamp}-{uuid.uuid4().hex[:8]}"
    qualification_workspace.validate_artifact_paths(
        {
            "candidate_context": run_root / "candidate-context.json",
            "lifecycle_state": run_root / "lifecycle" / ("c" * 24) / "state-restoration.json",
            "repeatability_state": run_root / "live/repeatability" / ("c" * 24) / "runs/positive/rep-03/attempt-01" / ("c" * 24) / "state-restoration.json",
            "receipt_identity": run_root / "live/evidence-refusal" / ("c" * 24) / "receipt-outputs" / ("c" * 40) / "receipt.json",
            "transcript_identity": run_root / "transcripts/evidence-refusal.artifacts.json",
            "rehearsal_summary": run_root / "rehearsal/zero-model-rehearsal.json",
        }
    )
    run_root.mkdir(parents=True, exist_ok=False)
    candidate_dir = run_root / "candidate"
    copied_manifest, copied_artifacts = copy_candidate_set(
        args.candidate_manifest.resolve(),
        args.artifacts.resolve(),
        candidate_dir,
    )
    manifest = release_candidate.verify_candidate_manifest(
        copied_manifest,
        copied_artifacts,
        repository=ROOT,
        expected_commit=head,
    )
    manifest_digest = release_candidate.sha256_file(copied_manifest)

    marketplace_name = f"egoist-engineering-foundation-h04-{run_root.name.lower()}"
    marketplace_lease = qualification_workspace.allocate_workspace(
        artifact_root=run_root,
        mapping_path=run_root / "candidate-marketplace-workspace.json",
        identity={"campaign": run_root.name, "family": "marketplace"},
    )
    marketplace_root = marketplace_lease.child("m")
    release_candidate.materialize_candidate_marketplace(
        copied_manifest,
        copied_artifacts,
        marketplace_root,
        repository=ROOT,
        expected_commit=head,
        marketplace_name=marketplace_name,
    )
    context = release_candidate.create_live_runtime_context(
        manifest_path=copied_manifest,
        artifact_dir=copied_artifacts,
        run_root=run_root,
        marketplace_root=marketplace_root,
        workspace_root=marketplace_lease.path,
        marketplace_name=marketplace_name,
        repository=ROOT,
        expected_commit=head,
    )
    context_path = run_root / "candidate-context.json"
    release_candidate.write_json(context_path, context)

    lifecycle_output = run_root / "lifecycle"
    lifecycle_command = [
        sys.executable,
        str(ROOT / "scripts/run_public_beta_lifecycle.py"),
        "--candidate-manifest",
        str(copied_manifest),
        "--artifacts",
        str(copied_artifacts),
        "--output",
        str(lifecycle_output),
    ]
    run_process(
        lifecycle_command,
        transcript=run_root / "transcripts/lifecycle.txt",
        timeout=args.timeout_seconds,
    )
    lifecycle_campaign = one_campaign(lifecycle_output)
    lifecycle_summary_path = lifecycle_campaign / "summary.json"
    lifecycle_summary = load_object(lifecycle_summary_path)
    try:
        release_candidate.verify_lifecycle_evidence(manifest, lifecycle_summary)
    except release_candidate.CandidateError as exc:
        raise QualificationError(str(exc)) from exc

    if args.lifecycle_only:
        marketplace_lease.cleanup()
        summary = {
            "schema_version": 1,
            "qualification_status": "LIFECYCLE_ONLY",
            "candidate_manifest": relative_artifact(copied_manifest, run_root),
            "subject_commit_sha": head,
            "package_sha256": {
                package["name"]: package["sha256"]
                for package in manifest["packages"]
            },
            "lifecycle_evidence": relative_artifact(
                lifecycle_summary_path, run_root
            ),
            "model_turns": 0,
            "state_restored": True,
            "live_cases": [],
            "not_run_clients": [
                "ChatGPT/Codex desktop",
                "Codex CLI authenticated session",
                "Codex Cloud",
                "Claude Code authenticated session",
                "Agent Plugins reference client",
            ],
        }
        release_candidate.validate_shareable_provenance(summary)
        release_candidate.write_json(run_root / "qualification-summary.json", summary)
        print(f"exact-artifact qualification: LIFECYCLE_ONLY PASS ({run_root})")
        return 0

    if args.zero_model_rehearsal:
        previous_context = os.environ.get(release_candidate.LIVE_CONTEXT_ENV)
        try:
            os.environ[release_candidate.LIVE_CONTEXT_ENV] = str(context_path)
            live_base._CANDIDATE_RUNTIME_CACHE = None
            live_base.candidate_runtime()
            rehearsal = qualification_rehearsal.run(
                artifact_root=run_root / "rehearsal",
                campaign_id=run_root.name,
                marketplace_root=marketplace_root,
                lifecycle_summary=lifecycle_summary,
            )
        finally:
            if previous_context is None:
                os.environ.pop(release_candidate.LIVE_CONTEXT_ENV, None)
            else:
                os.environ[release_candidate.LIVE_CONTEXT_ENV] = previous_context
            live_base._CANDIDATE_RUNTIME_CACHE = None
        marketplace_lease.cleanup()
        summary = {
            "schema_version": 1,
            "qualification_status": "ZERO_MODEL_REHEARSAL_PASS",
            "candidate_manifest": relative_artifact(copied_manifest, run_root),
            "subject_commit_sha": head,
            "package_sha256": {
                package["name"]: package["sha256"] for package in manifest["packages"]
            },
            "lifecycle_evidence": relative_artifact(lifecycle_summary_path, run_root),
            "rehearsal_evidence": relative_artifact(
                run_root / "rehearsal/zero-model-rehearsal.json", run_root
            ),
            "model_turns": 0,
            "model_calls": rehearsal["model_calls"],
            "state_restored": True,
            "workspace_cleanup": "PASS",
            "live_cases": [],
        }
        release_candidate.validate_shareable_provenance(summary)
        release_candidate.write_json(run_root / "qualification-summary.json", summary)
        print(f"exact-artifact qualification: ZERO_MODEL_REHEARSAL PASS ({run_root})")
        return 0

    live_evidence: list[dict[str, Any]] = []
    case_rows: list[dict[str, Any]] = []
    state_restored = True
    total_turns = 0
    previous_context = os.environ.get(release_candidate.LIVE_CONTEXT_ENV)
    original_marketplace_name = live_base.MARKETPLACE_NAME
    original_plugin_id = live_base.PLUGIN_ID
    parent_guard: repeat_entry.CampaignStateGuard | None = None
    parent_state_path = run_root / "parent-state-restoration.json"
    try:
        os.environ[release_candidate.LIVE_CONTEXT_ENV] = str(context_path)
        live_base._CANDIDATE_RUNTIME_CACHE = None
        live_base.candidate_runtime()
        launchers = live_base.resolve_codex_launchers()
        live_base.login_status(launchers)
        env = os.environ.copy()
        live_root = run_root / "live"
        commands = [
            (
                "repeatability",
                [
                    sys.executable,
                    str(ROOT / "scripts/run_codex_core_repeatability.py"),
                    "--confirm-live",
                    "--repetitions",
                    str(args.repetitions),
                    "--timeout-seconds",
                    str(args.timeout_seconds),
                    "--output",
                    str(live_root / "repeatability"),
                ],
                True,
            ),
            (
                "bounded-delegation",
                [
                    sys.executable,
                    str(ROOT / "scripts/run_codex_bounded_delegation_smoke_v5.py"),
                    "--confirm-live",
                    "--timeout-seconds",
                    str(args.timeout_seconds),
                    "--output",
                    str(live_root / "bounded-delegation"),
                ],
                False,
            ),
            (
                "evidence-refusal",
                [
                    sys.executable,
                    str(ROOT / "scripts/run_codex_evidence_refusal_smoke.py"),
                    "--confirm-live",
                    "--timeout-seconds",
                    str(args.timeout_seconds),
                    "--output",
                    str(live_root / "evidence-refusal"),
                ],
                False,
            ),
        ]
        parent_guard = repeat_entry.CampaignStateGuard(
            launchers=launchers,
            subject_version=str(release_candidate.core_package(manifest)["version"]),
        )
        try:
            with parent_guard:
                for key, command, repeatability in commands:
                    run_process(
                        command,
                        env=env,
                        transcript=run_root / f"transcripts/{key}.txt",
                        timeout=max(
                            args.timeout_seconds * (12 if repeatability else 2),
                            1800,
                        ),
                    )
                    campaign = one_campaign(live_root / key)
                    campaign_summary, rows = validate_live_campaign(
                        campaign=campaign,
                        manifest=manifest,
                        manifest_digest=manifest_digest,
                        repeatability=repeatability,
                    )
                    summary_path = campaign / "summary.json"
                    live_evidence.append(
                        {
                            "campaign": key,
                            **relative_artifact(summary_path, run_root),
                            "scorer_status": (
                                campaign_summary.get("score", {}).get("status")
                                if isinstance(campaign_summary.get("score"), dict)
                                else None
                            ),
                        }
                    )
                    candidates = [
                        row for row in rows if row.get("variant") == "candidate"
                    ]
                    case_rows.extend(candidates)
                    total_turns += len(rows)
                    if repeatability:
                        state_restored = state_restored and bool(
                            campaign_summary.get("parent_state_restored")
                        )
                    else:
                        state_restored = state_restored and bool(
                            campaign_summary.get("plugin_state_restored")
                        )
        except BaseException as exc:
            release_candidate.write_json(parent_state_path, parent_guard.evidence())
            if not parent_guard.restored:
                raise QualificationError(
                    "parent exact-artifact state restoration failed"
                ) from exc
            raise
        release_candidate.write_json(parent_state_path, parent_guard.evidence())
        if not parent_guard.restored:
            raise QualificationError("parent exact-artifact state restoration failed")
        state_restored = state_restored and parent_guard.restored
    finally:
        if previous_context is None:
            os.environ.pop(release_candidate.LIVE_CONTEXT_ENV, None)
        else:
            os.environ[release_candidate.LIVE_CONTEXT_ENV] = previous_context
        live_base._CANDIDATE_RUNTIME_CACHE = None
        live_base.MARKETPLACE_NAME = original_marketplace_name
        live_base.PLUGIN_ID = original_plugin_id

    if total_turns != 16:
        raise QualificationError(
            f"exact-artifact campaign completed {total_turns} model turns; expected 16"
        )
    if not state_restored:
        raise QualificationError("one or more live campaigns did not restore state")
    try:
        release_candidate.verify_live_rows(manifest, case_rows, manifest_digest)
    except release_candidate.CandidateError as exc:
        raise QualificationError(str(exc)) from exc
    case_inventory = sorted(
        {
            (str(row["case_id"]), int(row["case_revision"]))
            for row in case_rows
        }
    )
    expected_cases = {
        ("debug-before-fix", 2),
        ("tiny-edit-skips-plan", 6),
        ("bounded-read-only-delegation", 5),
        ("required-evidence-refusal", 1),
    }
    if set(case_inventory) != expected_cases:
        raise QualificationError(
            f"exact-artifact live case inventory differs: {case_inventory}"
        )

    summary = {
        "schema_version": 1,
        "evidence_class": "LIVE",
        "qualification_status": "PARTIAL",
        "candidate_state": "UNRELEASED",
        "candidate_manifest": relative_artifact(copied_manifest, run_root),
        "subject_commit_sha": head,
        "package_sha256": {
            package["name"]: package["sha256"] for package in manifest["packages"]
        },
        "operating_system": platform.platform(),
        "python_version": platform.python_version(),
        "codex_cli_version": launchers.version_text,
        "claude_cli_version": command_version("claude"),
        "login_mode": "existing_authenticated_session",
        "lifecycle_evidence": relative_artifact(lifecycle_summary_path, run_root),
        "live_evidence": live_evidence,
        "cases": [
            {"case_id": case_id, "case_revision": revision}
            for case_id, revision in case_inventory
        ],
        "installed_plugin": {
            "name": "engineering-foundation-core",
            "version": release_candidate.core_package(manifest)["version"],
            "artifact_sha256": release_candidate.core_package(manifest)["sha256"],
        },
        "model_turns": total_turns,
        "scorer_result": "PASS",
        "state_restored": state_restored,
        "parent_state_evidence": relative_artifact(parent_state_path, run_root),
        "errors": [],
        "not_run_clients": [
            "ChatGPT/Codex desktop",
            "Codex Cloud",
            "Claude Code authenticated session",
            "Agent Plugins reference client",
        ],
    }
    if _contains_absolute_path(summary):
        raise QualificationError("shareable qualification summary contains an absolute path")
    release_candidate.validate_shareable_provenance(summary)
    marketplace_lease.cleanup()
    release_candidate.write_json(run_root / "qualification-summary.json", summary)
    print(f"exact-artifact qualification: PARTIAL PASS ({run_root})")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(qualification_workspace.run_with_cleanup(main))
    except (
        QualificationError,
        qualification_rehearsal.RehearsalError,
        qualification_workspace.WorkspaceError,
        release_candidate.CandidateError,
        live_base.HarnessError,
        OSError,
        subprocess.SubprocessError,
        json.JSONDecodeError,
    ) as exc:
        payload = (
            exc.payload()
            if isinstance(exc, qualification_workspace.WorkspacePathError)
            else release_candidate.failure_payload("exact-artifact-qualification", exc)
        )
        write_console_safe(
            sys.stderr,
            json.dumps(
                payload,
                ensure_ascii=False,
                separators=(",", ":"),
            )
            + "\n",
        )
        raise SystemExit(1)
