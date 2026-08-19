#!/usr/bin/env python3
"""Run a checkpointed Codex core repeatability campaign.

The campaign executes the isolated explicit-positive debugging smoke and the
isolated negative tiny-edit smoke repeatedly under one harness identity. It
fails closed on the first non-PASS child, preserves every child artifact, and
scores the combined repetitions only after the full matrix is complete.
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import sys
import time
import uuid
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TextIO

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import run_codex_live_smoke as base

ROOT = Path(__file__).resolve().parents[1]
SCORER_PATH = ROOT / "scripts" / "score_eval_runs.py"
DEFAULT_OUTPUT = ROOT / ".eval-runs" / "codex-core-repeatability"
LOCK_PATH = ROOT / ".eval-runs" / "codex-core-repeatability.lock"
SCHEMA_VERSION = 1
DEFAULT_REPETITIONS = 3


@dataclass(frozen=True)
class CaseSpec:
    key: str
    case_id: str
    case_revision: int
    script: Path
    effort: str


@dataclass(frozen=True)
class PlannedRun:
    sequence: int
    case_key: str
    repetition: int

    @property
    def step_id(self) -> str:
        return f"{self.case_key}-r{self.repetition:02d}"


CASES = {
    "positive": CaseSpec(
        key="positive",
        case_id="debug-before-fix",
        case_revision=2,
        script=ROOT / "scripts" / "run_codex_positive_smoke_isolated.py",
        effort="medium",
    ),
    "negative": CaseSpec(
        key="negative",
        case_id="tiny-edit-skips-plan",
        case_revision=6,
        script=ROOT / "scripts" / "run_codex_negative_smoke_v4.py",
        effort="low",
    ),
}


class CampaignLock(AbstractContextManager["CampaignLock"]):
    def __init__(self, path: Path, campaign: Path) -> None:
        self.path = path
        self.campaign = campaign
        self.acquired = False

    def __enter__(self) -> "CampaignLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "pid": os.getpid(),
            "campaign": str(self.campaign),
            "created_at": utc_now(),
        }
        try:
            descriptor = os.open(
                self.path,
                os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                0o600,
            )
        except FileExistsError as exc:
            existing = ""
            try:
                existing = self.path.read_text(encoding="utf-8").strip()
            except OSError:
                pass
            raise base.HarnessError(
                "another repeatability campaign lock exists: "
                f"{self.path}\n{existing or 'lock contents unavailable'}"
            ) from exc
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        self.acquired = True
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> bool:
        if self.acquired:
            try:
                self.path.unlink()
            except FileNotFoundError:
                pass
        return False


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def campaign_directory(base_dir: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = base_dir / f"{stamp}-{uuid.uuid4().hex[:8]}"
    path.mkdir(parents=True, exist_ok=False)
    return path


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    os.replace(temporary, path)


def build_plan(repetitions: int) -> list[PlannedRun]:
    plan: list[PlannedRun] = []
    sequence = 0
    for repetition in range(1, repetitions + 1):
        order = ("positive", "negative") if repetition % 2 else ("negative", "positive")
        for case_key in order:
            sequence += 1
            plan.append(
                PlannedRun(
                    sequence=sequence,
                    case_key=case_key,
                    repetition=repetition,
                )
            )
    return plan


def require_clean_repository() -> str:
    status = base.git(["status", "--porcelain"], cwd=ROOT)
    if status.strip():
        raise base.HarnessError(
            "foundation working tree is not clean; repeatability campaign refused to start:\n"
            + status
        )
    return base.git(["rev-parse", "HEAD"], cwd=ROOT)


def next_attempt_root(campaign: Path, step: PlannedRun) -> Path:
    base_dir = campaign / "runs" / step.case_key / f"rep-{step.repetition:02d}"
    base_dir.mkdir(parents=True, exist_ok=True)
    attempts = [
        path
        for path in base_dir.iterdir()
        if path.is_dir() and path.name.startswith("attempt-")
    ]
    attempt = len(attempts) + 1
    path = base_dir / f"attempt-{attempt:02d}"
    path.mkdir(parents=True, exist_ok=False)
    return path


def stream_process(
    command: list[str],
    *,
    transcript_path: Path,
) -> int:
    transcript_path.parent.mkdir(parents=True, exist_ok=True)
    process = subprocess.Popen(
        command,
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )
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
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            raise
    return process.wait()


def discover_child_campaign(attempt_root: Path) -> Path:
    campaigns = sorted(path for path in attempt_root.iterdir() if path.is_dir())
    if len(campaigns) != 1:
        raise base.HarnessError(
            f"expected one child campaign below {attempt_root}, found {len(campaigns)}."
        )
    return campaigns[0]


def load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise base.HarnessError(f"could not read JSON artifact {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise base.HarnessError(f"JSON artifact must contain an object: {path}")
    return payload


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise base.HarnessError(f"could not read JSONL artifact {path}: {exc}") from exc
    for line_number, raw in enumerate(lines, 1):
        if not raw.strip():
            continue
        try:
            row = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise base.HarnessError(
                f"invalid JSONL at {path}:{line_number}: {exc}"
            ) from exc
        if not isinstance(row, dict):
            raise base.HarnessError(f"JSONL row must be an object: {path}:{line_number}")
        rows.append(row)
    return rows


def path_under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def transform_rows(
    *,
    rows: list[dict[str, Any]],
    child_campaign: Path,
    parent_campaign: Path,
    parent_campaign_id: str,
    spec: CaseSpec,
    repetition: int,
    harness_commit: str,
) -> list[dict[str, Any]]:
    if len(rows) != 2:
        raise base.HarnessError(
            f"{spec.key} repetition {repetition} emitted {len(rows)} rows; expected two."
        )
    variants = {str(row.get("variant")) for row in rows}
    if variants != {"baseline", "candidate"}:
        raise base.HarnessError(
            f"{spec.key} repetition {repetition} emitted invalid variants: {sorted(variants)}"
        )

    transformed: list[dict[str, Any]] = []
    for source in rows:
        row = dict(source)
        if row.get("case_id") != spec.case_id:
            raise base.HarnessError(
                f"{spec.key} emitted case_id={row.get('case_id')!r}; expected {spec.case_id!r}."
            )
        if row.get("case_revision") != spec.case_revision:
            raise base.HarnessError(
                f"{spec.key} emitted case_revision={row.get('case_revision')!r}; "
                f"expected {spec.case_revision}."
            )
        if row.get("harness_commit") != harness_commit:
            raise base.HarnessError(
                f"{spec.key} used harness commit {row.get('harness_commit')!r}; "
                f"expected {harness_commit}."
            )
        row["campaign_id"] = parent_campaign_id
        row["repetition"] = repetition
        for field in ("trace_path", "artifact_path"):
            relative = row.get(field)
            if not isinstance(relative, str) or not relative:
                raise base.HarnessError(f"{spec.key} row omitted {field}.")
            absolute = (child_campaign / relative).resolve()
            if not path_under(absolute, parent_campaign) or not absolute.is_file():
                raise base.HarnessError(
                    f"{spec.key} emitted unsafe or missing {field}: {relative}"
                )
            row[field] = absolute.relative_to(parent_campaign.resolve()).as_posix()
        existing_notes = str(row.get("notes", "")).strip()
        row["notes"] = (
            existing_notes
            + f" Repeatability parent {parent_campaign.name}; repetition {repetition}."
        ).strip()
        transformed.append(row)
    return transformed


def child_identity(summary: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    baseline = summary.get("baseline")
    candidate = summary.get("candidate")
    if not isinstance(baseline, dict) or not isinstance(candidate, dict):
        raise base.HarnessError("child summary omitted baseline or candidate artifacts.")
    if (
        baseline.get("model") != candidate.get("model")
        or baseline.get("model_provider") != candidate.get("model_provider")
        or baseline.get("service_tier") != candidate.get("service_tier")
    ):
        raise base.HarnessError("child baseline and candidate model identity drifted.")
    candidate_rows = [row for row in rows if row.get("variant") == "candidate"]
    if len(candidate_rows) != 1:
        raise base.HarnessError("child candidate row identity is ambiguous.")
    candidate_row = candidate_rows[0]
    return {
        "client_version": candidate_row.get("client_version"),
        "harness_commit": candidate_row.get("harness_commit"),
        "subject_version": candidate_row.get("subject_version"),
        "subject_commit": candidate_row.get("subject_commit"),
        "candidate_repository": candidate_row.get("candidate_repository"),
        "candidate_manifest_sha256": candidate_row.get(
            "candidate_manifest_sha256"
        ),
        "package_sha256": candidate_row.get("package_sha256"),
        "model": candidate.get("model"),
        "model_provider": candidate.get("model_provider"),
        "service_tier": candidate.get("service_tier"),
    }


def compact_variant(artifact: object) -> dict[str, Any] | None:
    if not isinstance(artifact, dict):
        return None
    usage = artifact.get("token_usage")
    return {
        "task_pass": artifact.get("task_pass"),
        "safety_pass": artifact.get("safety_pass"),
        "activation_pass": artifact.get("activation_pass"),
        "evidence_pass": artifact.get("evidence_pass"),
        "environment_pass": artifact.get("environment_pass"),
        "tokens": artifact.get("tokens"),
        "tool_calls": artifact.get("tool_calls"),
        "agents_spawned": artifact.get("agents_spawned"),
        "duration_ms": artifact.get("duration_ms"),
        "token_usage": usage if isinstance(usage, dict) else {},
    }


def run_child(
    *,
    campaign: Path,
    step: PlannedRun,
    timeout_seconds: int,
    harness_commit: str,
    parent_campaign_id: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    spec = CASES[step.case_key]
    if not spec.script.is_file():
        raise base.HarnessError(f"child harness not found: {spec.script}")

    attempt_root = next_attempt_root(campaign, step)
    transcript_path = (
        campaign
        / "transcripts"
        / f"{step.sequence:02d}-{step.step_id}-{attempt_root.name}.txt"
    )
    command = [
        sys.executable,
        str(spec.script),
        "--confirm-live",
        "--effort",
        spec.effort,
        "--timeout-seconds",
        str(timeout_seconds),
        "--output",
        str(attempt_root),
    ]

    print("\n" + "=" * 92)
    print(
        f"[{step.sequence:02d}] {step.case_key.upper()} repetition "
        f"{step.repetition} | two authenticated model turns"
    )
    print("=" * 92)
    started_at = utc_now()
    exit_code = stream_process(command, transcript_path=transcript_path)
    finished_at = utc_now()

    child_campaign: Path | None = None
    summary: dict[str, Any] | None = None
    rows: list[dict[str, Any]] = []
    try:
        child_campaign = discover_child_campaign(attempt_root)
        summary = load_json(child_campaign / "summary.json")
        source_rows = load_jsonl(child_campaign / "runs.jsonl")
        rows = transform_rows(
            rows=source_rows,
            child_campaign=child_campaign,
            parent_campaign=campaign,
            parent_campaign_id=parent_campaign_id,
            spec=spec,
            repetition=step.repetition,
            harness_commit=harness_commit,
        )
    except base.HarnessError:
        if exit_code == 0:
            raise

    outcome = str(summary.get("outcome")) if summary else "HARNESS_ERROR"
    state_restored = bool(summary.get("plugin_state_restored")) if summary else False
    identity = child_identity(summary, rows) if summary and rows else None
    record = {
        "step_id": step.step_id,
        "sequence": step.sequence,
        "case_key": step.case_key,
        "case_id": spec.case_id,
        "case_revision": spec.case_revision,
        "repetition": step.repetition,
        "started_at": started_at,
        "finished_at": finished_at,
        "exit_code": exit_code,
        "outcome": outcome,
        "plugin_state_restored": state_restored,
        "attempt_root": str(attempt_root.relative_to(campaign)),
        "child_campaign": (
            str(child_campaign.relative_to(campaign)) if child_campaign else None
        ),
        "summary_path": (
            str((child_campaign / "summary.json").relative_to(campaign))
            if child_campaign
            else None
        ),
        "transcript_path": str(transcript_path.relative_to(campaign)),
        "identity": identity,
        "baseline": compact_variant(summary.get("baseline")) if summary else None,
        "candidate": compact_variant(summary.get("candidate")) if summary else None,
        "score": summary.get("score") if summary else None,
        "invalid_reasons": summary.get("invalid_reasons", []) if summary else [],
        "error": summary.get("error") if summary else "child campaign was not readable",
    }
    return record, rows


def write_runs(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
            for row in rows
        ),
        encoding="utf-8",
        newline="\n",
    )


def ensure_identity_stable(records: list[dict[str, Any]]) -> dict[str, Any]:
    identities = [record.get("identity") for record in records]
    if not identities or not all(isinstance(item, dict) for item in identities):
        raise base.HarnessError("repeatability campaign has incomplete child identities.")
    canonical = dict(identities[0])
    for record, identity in zip(records[1:], identities[1:]):
        if identity != canonical:
            raise base.HarnessError(
                "model/client/subject drift across repetitions: "
                f"{record['step_id']} -> {json.dumps(identity, ensure_ascii=False)}; "
                f"expected {json.dumps(canonical, ensure_ascii=False)}"
            )
    return canonical


def metric_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for case_key in CASES:
        result[case_key] = {}
        case_records = [record for record in records if record["case_key"] == case_key]
        for variant in ("baseline", "candidate"):
            artifacts = [
                record[variant]
                for record in case_records
                if isinstance(record.get(variant), dict)
            ]
            if not artifacts:
                continue
            def values(field: str) -> list[int]:
                return [
                    int(item[field])
                    for item in artifacts
                    if isinstance(item.get(field), int)
                ]

            tokens = values("tokens")
            tools = values("tool_calls")
            agents = values("agents_spawned")
            durations = values("duration_ms")
            uncached = [
                int(item["token_usage"]["uncached_input_tokens"])
                for item in artifacts
                if isinstance(item.get("token_usage"), dict)
                and isinstance(item["token_usage"].get("uncached_input_tokens"), int)
            ]
            result[case_key][variant] = {
                "runs": len(artifacts),
                "task_pass_rate": sum(bool(item.get("task_pass")) for item in artifacts)
                / len(artifacts),
                "safety_pass_rate": sum(bool(item.get("safety_pass")) for item in artifacts)
                / len(artifacts),
                "activation_pass_rate": sum(
                    bool(item.get("activation_pass")) for item in artifacts
                )
                / len(artifacts),
                "evidence_pass_rate": sum(
                    bool(item.get("evidence_pass")) for item in artifacts
                )
                / len(artifacts),
                "environment_pass_rate": sum(
                    bool(item.get("environment_pass")) for item in artifacts
                )
                / len(artifacts),
                "median_tokens": statistics.median(tokens),
                "median_uncached_input_tokens": statistics.median(uncached),
                "median_tool_calls": statistics.median(tools),
                "median_agents_spawned": statistics.median(agents),
                "median_duration_ms": statistics.median(durations),
                "min_tokens": min(tokens),
                "max_tokens": max(tokens),
            }
    return result


def run_scorer(runs_path: Path, repetitions: int) -> tuple[int, dict[str, Any]]:
    result = subprocess.run(
        [
            sys.executable,
            str(SCORER_PATH),
            str(runs_path),
            "--min-repetitions",
            str(repetitions),
            "--json",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        combined = "\n".join(part for part in (result.stdout, result.stderr) if part)
        raise base.HarnessError(f"repeatability scorer emitted invalid JSON:\n{combined}") from exc
    if not isinstance(payload, dict):
        raise base.HarnessError("repeatability scorer returned a non-object payload.")
    return result.returncode, payload


def render_report(summary: dict[str, Any]) -> str:
    lines = [
        "# Codex core repeatability campaign",
        "",
        f"- campaign: `{summary['campaign']}`",
        f"- outcome: **{summary['outcome']}**",
        f"- repetitions per case: `{summary['repetitions_completed']}` / "
        f"`{summary['repetitions_requested']}`",
        f"- authenticated model turns completed: `{summary['model_turns_completed']}`",
        f"- harness commit: `{summary['harness_commit']}`",
        "",
        "## Child outcomes",
        "",
        "| Case | Repetition | Outcome | Restored |",
        "|---|---:|---:|---:|",
    ]
    for record in summary["children"]:
        lines.append(
            f"| {record['case_key']} | {record['repetition']} | "
            f"{record['outcome']} | {record['plugin_state_restored']} |"
        )
    lines.extend(
        [
            "",
            "## Aggregate metrics",
            "",
            "```json",
            json.dumps(summary.get("metrics", {}), ensure_ascii=False, indent=2),
            "```",
            "",
            "## Evidence boundary",
            "",
            "A PASS establishes repeated behavior only for the two included Codex CLI cases "
            "under one harness, client, model, and subject identity. It does not complete the "
            "remaining client or package qualification matrix.",
            "",
        ]
    )
    return "\n".join(lines)


def finalize_failure(
    *,
    campaign: Path,
    manifest: dict[str, Any],
    reason: str,
    record: dict[str, Any] | None = None,
) -> None:
    manifest["outcome"] = "FAIL"
    manifest["updated_at"] = utc_now()
    manifest["failure_reason"] = reason
    atomic_write_json(campaign / "manifest.json", manifest)
    payload = {
        "campaign": campaign.name,
        "outcome": "FAIL",
        "reason": reason,
        "failed_child": record,
        "completed_children": manifest.get("completed", []),
        "resume_allowed": False,
    }
    atomic_write_json(campaign / "failure-diagnostics.json", payload)
    print("\nREPEATABILITY FAILURE DIAGNOSTICS")
    print(f"  reason : {reason}")
    if record:
        print(f"  child  : {record.get('step_id')}")
        print(f"  outcome: {record.get('outcome')}")
        print(f"  summary: {record.get('summary_path')}")
        print(f"  transcript: {record.get('transcript_path')}")
    print(f"  file   : {campaign / 'failure-diagnostics.json'}")


def new_manifest(
    *,
    campaign: Path,
    repetitions: int,
    harness_commit: str,
    client_version: str,
    subject_version: str,
) -> dict[str, Any]:
    plan = build_plan(repetitions)
    return {
        "schema_version": SCHEMA_VERSION,
        "campaign": campaign.name,
        "campaign_id": f"codex-core-repeatability-{campaign.name}",
        "created_at": utc_now(),
        "updated_at": utc_now(),
        "outcome": "IN_PROGRESS",
        "repetitions": repetitions,
        "expected_model_turns": repetitions * len(CASES) * 2,
        "harness_commit": harness_commit,
        "client_version": client_version,
        "subject_version": subject_version,
        "plan": [
            {
                "sequence": step.sequence,
                "step_id": step.step_id,
                "case_key": step.case_key,
                "repetition": step.repetition,
            }
            for step in plan
        ],
        "completed": [],
    }


def load_resume_manifest(campaign: Path, harness_commit: str) -> dict[str, Any]:
    manifest = load_json(campaign / "manifest.json")
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise base.HarnessError("resume manifest schema is incompatible.")
    if manifest.get("harness_commit") != harness_commit:
        raise base.HarnessError(
            "resume refused because the foundation HEAD changed; start a new campaign."
        )
    if manifest.get("outcome") not in {"IN_PROGRESS", "INTERRUPTED"}:
        raise base.HarnessError(
            f"campaign outcome {manifest.get('outcome')!r} is not resumable."
        )
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run checkpointed positive and negative Codex core repetitions."
    )
    parser.add_argument(
        "--confirm-live",
        action="store_true",
        help="Acknowledge authenticated model usage and temporary Codex plugin changes.",
    )
    parser.add_argument(
        "--repetitions",
        type=int,
        default=DEFAULT_REPETITIONS,
        help="Repetitions per case (default: 3; total model turns: repetitions * 4).",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=900,
        help="Maximum wait passed to each child turn (default: 900).",
    )
    parser.add_argument(
        "--pause-seconds",
        type=float,
        default=2.0,
        help="Pause after each restored child campaign (default: 2).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Repeatability campaign output root.",
    )
    parser.add_argument(
        "--resume",
        type=Path,
        help="Resume one interrupted campaign directory under the same HEAD.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the deterministic plan without model calls or config changes.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.repetitions < 2 or args.repetitions > 10:
        print("ERROR: --repetitions must be between 2 and 10.")
        return 2
    if args.timeout_seconds < 30:
        print("ERROR: --timeout-seconds must be at least 30.")
        return 2
    if args.pause_seconds < 0:
        print("ERROR: --pause-seconds cannot be negative.")
        return 2

    plan = build_plan(args.repetitions)
    expected_turns = len(plan) * 2
    if args.dry_run:
        print("Codex core repeatability dry run")
        print(f"  repetitions per case: {args.repetitions}")
        print(f"  child campaigns      : {len(plan)}")
        print(f"  authenticated turns  : {expected_turns}")
        for step in plan:
            print(
                f"  {step.sequence:02d}. {step.case_key} repetition {step.repetition}"
            )
        return 0
    if not args.confirm_live:
        print(
            "ERROR: campaign not started. Re-run with --confirm-live to acknowledge "
            f"{expected_turns} authenticated model turns."
        )
        return 2

    harness_commit = require_clean_repository()
    launchers = base.resolve_codex_launchers()
    auth = base.login_status(launchers)
    client_version = ".".join(str(part) for part in launchers.version)
    subject_version = base.load_catalog()

    if args.resume:
        campaign = args.resume.resolve()
        manifest = load_resume_manifest(campaign, harness_commit)
        if int(manifest.get("repetitions", 0)) != args.repetitions:
            raise base.HarnessError(
                "--repetitions must match the interrupted campaign manifest."
            )
    else:
        output_root = args.output.resolve()
        output_root.mkdir(parents=True, exist_ok=True)
        campaign = campaign_directory(output_root)
        manifest = new_manifest(
            campaign=campaign,
            repetitions=args.repetitions,
            harness_commit=harness_commit,
            client_version=client_version,
            subject_version=subject_version,
        )
        atomic_write_json(campaign / "manifest.json", manifest)

    completed_records = list(manifest.get("completed", []))
    completed_ids = {str(record.get("step_id")) for record in completed_records}
    combined_rows = (
        load_jsonl(campaign / "runs.jsonl")
        if (campaign / "runs.jsonl").is_file()
        else []
    )

    print("Codex core repeatability campaign")
    print(f"  codex       : {launchers.version_text}")
    print(f"  login       : {auth}")
    print(f"  campaign    : {campaign}")
    print(f"  cases       : {', '.join(CASES)}")
    print(f"  repetitions : {args.repetitions} per case")
    print(f"  turns       : {expected_turns} authenticated model turns")
    print("  fail policy : stop on first non-PASS child")
    print("  resume      : checkpoint after every restored PASS child")

    with CampaignLock(LOCK_PATH, campaign):
        try:
            for step in plan:
                if step.step_id in completed_ids:
                    print(f"\nSKIP: {step.step_id} already completed in checkpoint.")
                    continue
                record, rows = run_child(
                    campaign=campaign,
                    step=step,
                    timeout_seconds=args.timeout_seconds,
                    harness_commit=harness_commit,
                    parent_campaign_id=str(manifest["campaign_id"]),
                )
                completed_records.append(record)
                manifest["completed"] = completed_records
                manifest["updated_at"] = utc_now()

                if (
                    record["outcome"] != "PASS"
                    or record["exit_code"] != 0
                    or not record["plugin_state_restored"]
                ):
                    reason = (
                        f"{step.step_id} did not produce a restored PASS "
                        f"(outcome={record['outcome']}, exit={record['exit_code']}, "
                        f"restored={record['plugin_state_restored']})."
                    )
                    finalize_failure(
                        campaign=campaign,
                        manifest=manifest,
                        reason=reason,
                        record=record,
                    )
                    return 1

                combined_rows.extend(rows)
                write_runs(campaign / "runs.jsonl", combined_rows)
                atomic_write_json(campaign / "manifest.json", manifest)
                require_clean_repository()
                if args.pause_seconds:
                    time.sleep(args.pause_seconds)
        except KeyboardInterrupt:
            manifest["outcome"] = "INTERRUPTED"
            manifest["updated_at"] = utc_now()
            manifest["completed"] = completed_records
            atomic_write_json(campaign / "manifest.json", manifest)
            print("\nINTERRUPTED: checkpoint preserved.")
            print(
                "Resume with: "
                f"{sys.executable} {Path(__file__).name} --confirm-live "
                f"--repetitions {args.repetitions} --resume {campaign}"
            )
            return 130

    identity = ensure_identity_stable(completed_records)
    scorer_exit, score = run_scorer(campaign / "runs.jsonl", args.repetitions)
    outcome = "PASS" if scorer_exit == 0 and score.get("status") == "PASS" else "FAIL"
    repetitions_completed = min(
        sum(
            1
            for record in completed_records
            if record["case_key"] == case_key and record["outcome"] == "PASS"
        )
        for case_key in CASES
    )
    summary = {
        "schema_version": SCHEMA_VERSION,
        "campaign": campaign.name,
        "campaign_id": manifest["campaign_id"],
        "outcome": outcome,
        "created_at": manifest["created_at"],
        "completed_at": utc_now(),
        "repetitions_requested": args.repetitions,
        "repetitions_completed": repetitions_completed,
        "model_turns_completed": len(completed_records) * 2,
        "harness_commit": harness_commit,
        "identity": identity,
        "children": completed_records,
        "metrics": metric_summary(completed_records),
        "score": score,
        "evidence_boundary": (
            "Repeated Codex CLI evidence for two core cases only; remaining clients, "
            "packages, and release-critical cases are not qualified."
        ),
    }
    atomic_write_json(campaign / "summary.json", summary)
    (campaign / "report.md").write_text(
        render_report(summary),
        encoding="utf-8",
        newline="\n",
    )
    manifest["outcome"] = outcome
    manifest["updated_at"] = utc_now()
    manifest["completed"] = completed_records
    manifest["score_path"] = "score.json"
    atomic_write_json(campaign / "manifest.json", manifest)
    atomic_write_json(campaign / "score.json", score)

    print("\nCORE REPEATABILITY SUMMARY")
    print(f"  outcome             : {outcome}")
    print(f"  repetitions per case: {repetitions_completed}/{args.repetitions}")
    print(f"  model turns         : {len(completed_records) * 2}")
    print(f"  scorer              : {score.get('status')}")
    print(f"  qualification       : {score.get('release_qualification')}")
    print(f"  artifacts           : {campaign}")

    if outcome == "PASS":
        print(
            "Result: PASS (two core cases repeated under one stable identity; "
            "full product qualification remains partial)"
        )
        return 0

    finalize_failure(
        campaign=campaign,
        manifest=manifest,
        reason="combined repeatability scorer did not pass.",
    )
    return 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (base.HarnessError, OSError, subprocess.SubprocessError, json.JSONDecodeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
