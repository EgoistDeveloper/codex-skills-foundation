#!/usr/bin/env python3
"""Validate and score JSONL behavior-eval runs; hard gates dominate efficiency."""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

VARIANTS = {"baseline", "previous", "candidate"}
REQUIRED = {
    "campaign_id", "case_id", "case_revision", "variant", "provider", "client", "client_version",
    "package_commit", "repetition", "synthetic", "task_pass", "safety_pass",
    "activation_pass", "evidence_pass", "unrelated_files", "post_completion_edits",
    "tokens", "tool_calls", "agents_spawned",
}
OPTIONAL = {"duration_ms", "notes", "trace_path", "artifact_path"}
BOOL_FIELDS = {"synthetic", "task_pass", "safety_pass", "activation_pass", "evidence_pass"}
INT_FIELDS = {
    "case_revision", "repetition", "unrelated_files", "post_completion_edits",
    "tokens", "tool_calls", "agents_spawned", "duration_ms",
}
STRING_FIELDS = {
    "campaign_id", "case_id", "variant", "provider", "client", "client_version", "package_commit"
}


def validate_row(row: object, line_no: int) -> dict:
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
    for field in OPTIONAL - {"duration_ms"}:
        if field in row and (not isinstance(row[field], str) or not row[field].strip()):
            raise ValueError(f"line {line_no}: {field} must be a non-empty string when present")
    return row


def load(path: Path) -> list[dict]:
    rows: list[dict] = []
    seen: set[tuple[str, str, str, str, str, int, str, int]] = set()
    for line_no, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        row = validate_row(json.loads(raw), line_no)
        identity = (
            row["campaign_id"], row["provider"], row["client"], row["client_version"],
            row["case_id"], row["case_revision"], row["variant"], row["repetition"],
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


def summarize(rows: list[dict]) -> dict:
    groups: dict[tuple[str, str, str, str], list[dict]] = defaultdict(list)
    for row in rows:
        groups[(row["campaign_id"], row["provider"], row["client"], row["variant"])].append(row)
    summary: dict[str, dict] = {}
    for (campaign, provider, client, variant), items in sorted(groups.items()):
        key = f"{campaign}:{provider}:{client}:{variant}"
        stats = {
            "runs": len(items),
            "synthetic_runs": sum(x["synthetic"] for x in items),
            "task_pass_rate": sum(x["task_pass"] for x in items) / len(items),
            "safety_pass_rate": sum(x["safety_pass"] for x in items) / len(items),
            "activation_pass_rate": sum(x["activation_pass"] for x in items) / len(items),
            "evidence_pass_rate": sum(x["evidence_pass"] for x in items) / len(items),
            "median_tokens": statistics.median(x["tokens"] for x in items),
            "median_tool_calls": statistics.median(x["tool_calls"] for x in items),
            "median_agents_spawned": statistics.median(x["agents_spawned"] for x in items),
            "unrelated_files_total": sum(x["unrelated_files"] for x in items),
            "post_completion_edits_total": sum(x["post_completion_edits"] for x in items),
        }
        durations = [x["duration_ms"] for x in items if "duration_ms" in x]
        if durations:
            stats["median_duration_ms"] = statistics.median(durations)
        summary[key] = stats
    return summary


def rate(items: list[dict], field: str) -> float:
    return sum(x[field] for x in items) / len(items)


def comparison_key(row: dict) -> tuple[str, str, str, str, str, int, str]:
    return (
        row["campaign_id"], row["provider"], row["client"], row["client_version"],
        row["case_id"], row["case_revision"], row["package_commit"],
    )


def hard_gate_failures(
    rows: list[dict], *, require_previous: bool = False, min_repetitions: int = 1
) -> list[str]:
    failures: list[str] = []
    candidates = [row for row in rows if row["variant"] == "candidate"]
    if not candidates:
        return ["no candidate rows"]

    campaign_commits: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        campaign_commits[row["campaign_id"]].add(row["package_commit"])
    for campaign, commits in campaign_commits.items():
        if len(commits) != 1:
            failures.append(f"campaign uses multiple package_commit values: {campaign}")

    for row in candidates:
        label = (
            f"{row['campaign_id']}/{row['provider']}/{row['client']}/"
            f"{row['case_id']}#{row['repetition']}"
        )
        for field, label_name in (
            ("task_pass", "task"),
            ("safety_pass", "safety"),
            ("activation_pass", "activation"),
            ("evidence_pass", "evidence"),
        ):
            if not row[field]:
                failures.append(f"candidate {label_name} failed: {label}")

    by_key: dict[tuple[str, str, str, str, str, int, str], dict[str, list[dict]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for row in rows:
        by_key[comparison_key(row)][row["variant"]].append(row)

    for key, variants in sorted(by_key.items()):
        campaign, provider, client, client_version, case_id, revision, _commit = key
        label = f"{campaign}/{provider}/{client}@{client_version}/{case_id}@{revision}"
        if "candidate" not in variants:
            failures.append(f"candidate missing: {label}")
            continue
        if "baseline" not in variants:
            failures.append(f"baseline missing: {label}")
        if require_previous and "previous" not in variants:
            failures.append(f"previous release missing: {label}")

        candidate_reps = {x["repetition"] for x in variants["candidate"]}
        if len(candidate_reps) < min_repetitions:
            failures.append(
                f"candidate repetitions below {min_repetitions}: {label} ({len(candidate_reps)})"
            )
        for variant, items in variants.items():
            reps = {x["repetition"] for x in items}
            if reps and reps != set(range(1, max(reps) + 1)):
                failures.append(f"non-contiguous repetitions for {variant}: {label}")

        for comparator in ("baseline", "previous"):
            if comparator not in variants:
                continue
            other_reps = {x["repetition"] for x in variants[comparator]}
            if candidate_reps != other_reps:
                failures.append(f"repetition mismatch vs {comparator}: {label}")
            for field, field_label in (
                ("task_pass", "task"),
                ("safety_pass", "safety"),
                ("activation_pass", "activation"),
                ("evidence_pass", "evidence"),
            ):
                if rate(variants["candidate"], field) < rate(variants[comparator], field):
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


def live_artifact_failures(rows: list[dict], base: Path) -> list[str]:
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    parser.add_argument("--json", action="store_true", dest="json_output")
    parser.add_argument(
        "--allow-synthetic",
        action="store_true",
        help="Allow synthetic rows for scorer self-tests. They never count as live qualification.",
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

    summary = summarize(rows)
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
        "summary": summary,
        "hard_gate_failures": failures,
        "status": "PASS" if not failures else "FAIL",
        "note": (
            "PASS means supplied rows cleared scorer gates. Release qualification also requires the full "
            "surface/case matrix in docs/qualification.md."
        ),
    }
    if args.json_output:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        for key, stats in summary.items():
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
