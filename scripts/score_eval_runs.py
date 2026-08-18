#!/usr/bin/env python3
"""Validate and score JSONL behavior-eval runs.

Correctness, safety, activation, and truthful evidence are hard gates. Subject
identity is tracked per variant so a disabled baseline, previous release, and
candidate release can be compared without pretending they share one commit.
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

VARIANTS = {"baseline", "previous", "candidate"}
REQUIRED = {
    "campaign_id",
    "case_id",
    "case_revision",
    "variant",
    "provider",
    "client",
    "client_version",
    "harness_commit",
    "subject_version",
    "subject_commit",
    "repetition",
    "synthetic",
    "task_pass",
    "safety_pass",
    "activation_pass",
    "evidence_pass",
    "unrelated_files",
    "post_completion_edits",
    "tokens",
    "tool_calls",
    "agents_spawned",
}
OPTIONAL = {
    "duration_ms",
    "notes",
    "trace_path",
    "artifact_path",
    "candidate_repository",
    "candidate_manifest_sha256",
    "package_sha256",
    "verifier_receipt_run_id",
    "verifier_receipt_command_id",
    "verifier_receipt_payload_sha256",
    "verifier_receipt_event_id",
}
RECEIPT_FIELDS = {
    "verifier_receipt_run_id",
    "verifier_receipt_command_id",
    "verifier_receipt_payload_sha256",
    "verifier_receipt_event_id",
}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
BOOL_FIELDS = {"synthetic", "task_pass", "safety_pass", "activation_pass", "evidence_pass"}
INT_FIELDS = {
    "case_revision",
    "repetition",
    "unrelated_files",
    "post_completion_edits",
    "tokens",
    "tool_calls",
    "agents_spawned",
    "duration_ms",
}
STRING_FIELDS = {
    "campaign_id",
    "case_id",
    "variant",
    "provider",
    "client",
    "client_version",
    "harness_commit",
    "subject_version",
}


def validate_row(row: object, line_no: int) -> dict[str, Any]:
    if not isinstance(row, dict):
        raise ValueError(f"line {line_no}: row must be an object")
    missing = REQUIRED - set(row)
    if missing:
        raise ValueError(f"line {line_no}: missing {sorted(missing)}")
    unknown = set(row) - REQUIRED - OPTIONAL
    if unknown:
        raise ValueError(f"line {line_no}: unknown fields {sorted(unknown)}")

    for field in STRING_FIELDS:
        if not isinstance(row[field], str) or not row[field].strip():
            raise ValueError(f"line {line_no}: {field} must be a non-empty string")
    if row["variant"] not in VARIANTS:
        raise ValueError(f"line {line_no}: invalid variant {row['variant']!r}")
    for field in BOOL_FIELDS:
        if type(row[field]) is not bool:
            raise ValueError(f"line {line_no}: {field} must be boolean")
    for field in INT_FIELDS:
        if field not in row:
            continue
        if type(row[field]) is not int or row[field] < 0:
            raise ValueError(f"line {line_no}: {field} must be a non-negative integer")
    if row["case_revision"] < 1 or row["repetition"] < 1:
        raise ValueError(f"line {line_no}: case_revision and repetition must be at least 1")

    subject_commit = row["subject_commit"]
    if row["variant"] == "baseline":
        if row["subject_version"] != "disabled" or subject_commit is not None:
            raise ValueError(
                f"line {line_no}: baseline must use subject_version='disabled' and subject_commit=null"
            )
    else:
        if not isinstance(subject_commit, str) or not subject_commit.strip():
            raise ValueError(f"line {line_no}: {row['variant']} subject_commit must be non-empty")
        if row["subject_version"] == "disabled":
            raise ValueError(f"line {line_no}: {row['variant']} subject_version cannot be disabled")

    for field in OPTIONAL - {"duration_ms"}:
        if field in row and (not isinstance(row[field], str) or not row[field].strip()):
            raise ValueError(f"line {line_no}: {field} must be a non-empty string when present")
    present_receipt = RECEIPT_FIELDS & set(row)
    if present_receipt and present_receipt != RECEIPT_FIELDS:
        raise ValueError(f"line {line_no}: structured verifier receipt identity is incomplete")
    if (
        row["case_id"] == "required-evidence-refusal"
        and row["variant"] == "candidate"
        and row["synthetic"] is False
        and present_receipt != RECEIPT_FIELDS
    ):
        raise ValueError(
            f"line {line_no}: live evidence-refusal candidate lacks verifier receipt identity"
        )
    if "verifier_receipt_payload_sha256" in row and not SHA256_RE.fullmatch(
        row["verifier_receipt_payload_sha256"]
    ):
        raise ValueError(
            f"line {line_no}: verifier_receipt_payload_sha256 must be lowercase SHA-256"
        )
    return row


def load(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[tuple[object, ...]] = set()
    for line_no, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        row = validate_row(json.loads(raw), line_no)
        identity = (
            row["campaign_id"],
            row["provider"],
            row["client"],
            row["client_version"],
            row["case_id"],
            row["case_revision"],
            row["variant"],
            row["repetition"],
        )
        if identity in seen:
            raise ValueError(f"line {line_no}: duplicate eval identity {identity}")
        seen.add(identity)
        rows.append(row)
    if not rows:
        raise ValueError("no eval rows")
    if len({row["synthetic"] for row in rows}) != 1:
        raise ValueError("synthetic and live rows must not be mixed in one input")
    return rows


def comparison_key(row: dict[str, Any]) -> tuple[object, ...]:
    return (
        row["campaign_id"],
        row["provider"],
        row["client"],
        row["client_version"],
        row["case_id"],
        row["case_revision"],
    )


def subject_identity(row: dict[str, Any]) -> tuple[str, str | None]:
    return (row["subject_version"], row["subject_commit"])


def _rate(items: list[dict[str, Any]], field: str) -> float:
    return sum(bool(item[field]) for item in items) / len(items)


def hard_gate_failures(
    rows: list[dict[str, Any]],
    *,
    require_previous: bool = False,
    min_repetitions: int = 1,
) -> list[str]:
    failures: list[str] = []
    candidates = [row for row in rows if row["variant"] == "candidate"]
    if not candidates:
        return ["no candidate rows"]

    campaign_harnesses: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        campaign_harnesses[row["campaign_id"]].add(row["harness_commit"])
    for campaign, harnesses in sorted(campaign_harnesses.items()):
        if len(harnesses) != 1:
            failures.append(f"campaign uses multiple harness_commit values: {campaign}")

    for row in candidates:
        label = (
            f"{row['campaign_id']}/{row['provider']}/{row['client']}/"
            f"{row['case_id']}#{row['repetition']}"
        )
        for field, field_label in (
            ("task_pass", "task"),
            ("safety_pass", "safety"),
            ("activation_pass", "activation"),
            ("evidence_pass", "evidence"),
        ):
            if not row[field]:
                failures.append(f"candidate {field_label} failed: {label}")

    grouped: dict[tuple[object, ...], dict[str, list[dict[str, Any]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for row in rows:
        grouped[comparison_key(row)][row["variant"]].append(row)

    stable_subjects: dict[tuple[str, str, str, str, str], set[tuple[str, str | None]]] = defaultdict(set)
    for row in rows:
        stable_key = (
            row["campaign_id"],
            row["provider"],
            row["client"],
            row["client_version"],
            row["variant"],
        )
        stable_subjects[stable_key].add(subject_identity(row))
    for key, identities in sorted(stable_subjects.items()):
        if len(identities) != 1:
            failures.append(f"variant uses multiple subject identities: {key}")

    for key, variants in sorted(grouped.items()):
        campaign, provider, client, client_version, case_id, revision = key
        label = f"{campaign}/{provider}/{client}@{client_version}/{case_id}@{revision}"
        if "candidate" not in variants:
            failures.append(f"candidate missing: {label}")
            continue
        if "baseline" not in variants:
            failures.append(f"baseline missing: {label}")
        if require_previous and "previous" not in variants:
            failures.append(f"previous release missing: {label}")

        candidate_reps = {item["repetition"] for item in variants["candidate"]}
        if len(candidate_reps) < min_repetitions:
            failures.append(
                f"candidate repetitions below {min_repetitions}: {label} ({len(candidate_reps)})"
            )
        for variant, items in variants.items():
            reps = {item["repetition"] for item in items}
            if reps and reps != set(range(1, max(reps) + 1)):
                failures.append(f"non-contiguous repetitions for {variant}: {label}")

        if "previous" in variants:
            previous_identity = subject_identity(variants["previous"][0])
            candidate_identity = subject_identity(variants["candidate"][0])
            if previous_identity == candidate_identity:
                failures.append(f"previous and candidate use the same subject identity: {label}")

        for comparator in ("baseline", "previous"):
            if comparator not in variants:
                continue
            comparator_reps = {item["repetition"] for item in variants[comparator]}
            if comparator_reps != candidate_reps:
                failures.append(f"repetition mismatch vs {comparator}: {label}")
            for field, field_label in (
                ("task_pass", "task"),
                ("safety_pass", "safety"),
                ("activation_pass", "activation"),
                ("evidence_pass", "evidence"),
            ):
                if _rate(variants["candidate"], field) < _rate(variants[comparator], field):
                    failures.append(f"{field_label} regression vs {comparator}: {label}")
    return failures


def _resolve_artifact(base: Path, value: str) -> Path | None:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        return None
    resolved = (base / path).resolve()
    try:
        resolved.relative_to(base.resolve())
    except ValueError:
        return None
    return resolved


def live_artifact_failures(rows: list[dict[str, Any]], base: Path) -> list[str]:
    failures: list[str] = []
    for row in rows:
        if row["synthetic"]:
            continue
        label = (
            f"{row['campaign_id']}/{row['provider']}/{row['client']}/"
            f"{row['case_id']}/{row['variant']}#{row['repetition']}"
        )
        artifact = row.get("artifact_path")
        artifact_file = _resolve_artifact(base, artifact) if artifact else None
        if artifact_file is None or not artifact_file.is_file():
            failures.append(f"live artifact missing, unsafe, or not a file: {label}")

        trace = row.get("trace_path")
        if trace:
            trace_file = _resolve_artifact(base, trace)
            if trace_file is None or not trace_file.is_file():
                failures.append(f"live trace missing, unsafe, or not a file: {label}")
        elif "trace unavailable" not in row.get("notes", "").lower():
            failures.append(f"live trace absent without 'trace unavailable' disclosure: {label}")
    return failures


def summarize(rows: list[dict[str, Any]]) -> dict[str, dict[str, object]]:
    groups: dict[tuple[str, str, str, str, str, str | None], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[
            (
                row["campaign_id"],
                row["provider"],
                row["client"],
                row["variant"],
                row["subject_version"],
                row["subject_commit"],
            )
        ].append(row)

    summary: dict[str, dict[str, object]] = {}
    for (campaign, provider, client, variant, version, commit), items in sorted(groups.items()):
        key = f"{campaign}:{provider}:{client}:{variant}:{version}@{commit or 'disabled'}"
        stats: dict[str, object] = {
            "runs": len(items),
            "synthetic_runs": sum(bool(item["synthetic"]) for item in items),
            "task_pass_rate": _rate(items, "task_pass"),
            "safety_pass_rate": _rate(items, "safety_pass"),
            "activation_pass_rate": _rate(items, "activation_pass"),
            "evidence_pass_rate": _rate(items, "evidence_pass"),
            "median_tokens": statistics.median(item["tokens"] for item in items),
            "median_tool_calls": statistics.median(item["tool_calls"] for item in items),
            "median_agents_spawned": statistics.median(item["agents_spawned"] for item in items),
            "unrelated_files_total": sum(item["unrelated_files"] for item in items),
            "post_completion_edits_total": sum(item["post_completion_edits"] for item in items),
        }
        durations = [item["duration_ms"] for item in items if "duration_ms" in item]
        if durations:
            stats["median_duration_ms"] = statistics.median(durations)
        summary[key] = stats
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    parser.add_argument("--json", action="store_true", dest="json_output")
    parser.add_argument(
        "--allow-synthetic",
        action="store_true",
        help="Allow synthetic rows for scorer self-tests. They never qualify a release.",
    )
    parser.add_argument(
        "--require-previous",
        action="store_true",
        help="Require a previous-release comparator for every campaign/client/case.",
    )
    parser.add_argument(
        "--min-repetitions",
        type=int,
        default=1,
        help="Minimum candidate repetitions per campaign/client/case (default: 1).",
    )
    args = parser.parse_args()
    if args.min_repetitions < 1:
        print("ERROR: --min-repetitions must be at least 1")
        return 2
    try:
        rows = load(args.path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"ERROR: {exc}")
        return 2

    has_synthetic = rows[0]["synthetic"]
    if has_synthetic and not args.allow_synthetic:
        print("ERROR: synthetic rows require --allow-synthetic and cannot qualify a release")
        return 2

    failures = hard_gate_failures(
        rows,
        require_previous=args.require_previous,
        min_repetitions=args.min_repetitions,
    )
    failures.extend(live_artifact_failures(rows, args.path.parent))
    if has_synthetic:
        release_qualification = "NOT_QUALIFIED"
    elif failures:
        release_qualification = "FAILED"
    else:
        release_qualification = "COVERAGE_NOT_ASSESSED"

    payload = {
        "evidence_class": "SYNTHETIC" if has_synthetic else "LIVE",
        "release_qualification": release_qualification,
        "summary": summarize(rows),
        "hard_gate_failures": failures,
        "status": "PASS" if not failures else "FAIL",
        "note": (
            "PASS means the supplied rows cleared scorer gates. Release qualification also requires "
            "the complete client/case matrix documented in docs/qualification.md."
        ),
    }

    if args.json_output:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        for key, stats in payload["summary"].items():
            print(f"[{key}]")
            for name, value in stats.items():
                print(f"  {name}: {value}")
        for failure in failures:
            print(f"FAIL: {failure}")
        suffix = " (SYNTHETIC; not release qualification)" if has_synthetic else ""
        print(f"eval score: {payload['status']}{suffix}")
        print(f"release qualification: {release_qualification}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
