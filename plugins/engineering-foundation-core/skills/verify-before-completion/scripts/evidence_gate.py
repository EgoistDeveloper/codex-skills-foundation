#!/usr/bin/env python3
"""Validate completion-evidence semantics against an optional task contract.

The gate checks structure, disclosed command freshness/exit codes, workspace
identity, and exact acceptance coverage. It cannot prove that an external
command really ran or that a human-readable claim is truthful.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ALLOWED_COMPLETION = {"COMPLETE", "PARTIAL", "BLOCKED"}
ALLOWED_STATUSES = {"PASS", "FAIL", "NOT_RUN", "NOT_APPLICABLE"}
ALLOWED_EVIDENCE_TYPES = {"command", "inspection", "runtime", "artifact", "decision"}
TOP_LEVEL_FIELDS = {"task_id", "completion_status", "workspace", "items", "remaining_risks"}
WORKSPACE_FIELDS = {"repository", "branch", "head_sha", "working_tree_reviewed"}
ITEM_FIELDS = {"criterion_id", "status", "summary", "evidence"}
EVIDENCE_FIELDS = {
    "type",
    "summary",
    "command",
    "verifier_argv",
    "fresh",
    "exit_code",
    "artifact_path",
    "receipt",
}
RECEIPT_FIELDS = {"run_id", "command_id", "payload_sha256", "child_exit_code"}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
CONTRACT_FIELDS = {
    "task_id",
    "objective",
    "context",
    "assumptions",
    "acceptance",
    "non_goals",
    "constraints",
    "risk",
    "reopen_conditions",
}
ACCEPTANCE_FIELDS = {"id", "criterion", "required", "evidence_hint"}


def _nonempty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate_contract(contract: object) -> list[str]:
    errors: list[str] = []
    if not isinstance(contract, dict):
        return ["contract must be an object"]

    unknown = set(contract) - CONTRACT_FIELDS
    if unknown:
        errors.append(f"contract has unknown fields: {sorted(unknown)}")

    for field in ("task_id", "objective"):
        if not _nonempty_string(contract.get(field)):
            errors.append(f"contract.{field} is required")

    for field in ("context", "assumptions", "non_goals", "constraints", "reopen_conditions"):
        value = contract.get(field)
        if not isinstance(value, list) or any(not _nonempty_string(item) for item in value):
            errors.append(f"contract.{field} must be an array of non-empty strings")
    if isinstance(contract.get("reopen_conditions"), list) and not contract["reopen_conditions"]:
        errors.append("contract.reopen_conditions must not be empty")

    risk = contract.get("risk")
    if not isinstance(risk, dict):
        errors.append("contract.risk must be an object")
    else:
        if set(risk) - {"level", "summary"}:
            errors.append("contract.risk has unknown fields")
        if risk.get("level") not in {"low", "medium", "high"}:
            errors.append("contract.risk.level is invalid")
        if not _nonempty_string(risk.get("summary")):
            errors.append("contract.risk.summary is required")

    acceptance = contract.get("acceptance")
    if not isinstance(acceptance, list) or not acceptance:
        errors.append("contract.acceptance must be a non-empty array")
        return errors

    seen: set[str] = set()
    for index, item in enumerate(acceptance):
        prefix = f"contract.acceptance[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{prefix} must be an object")
            continue
        unknown_item = set(item) - ACCEPTANCE_FIELDS
        if unknown_item:
            errors.append(f"{prefix} has unknown fields: {sorted(unknown_item)}")
        criterion_id = item.get("id")
        if not _nonempty_string(criterion_id):
            errors.append(f"{prefix}.id is required")
        elif criterion_id in seen:
            errors.append(f"{prefix}.id is duplicated: {criterion_id}")
        else:
            seen.add(criterion_id)
        if not _nonempty_string(item.get("criterion")):
            errors.append(f"{prefix}.criterion is required")
        if type(item.get("required")) is not bool:
            errors.append(f"{prefix}.required must be boolean")
        if not _nonempty_string(item.get("evidence_hint")):
            errors.append(f"{prefix}.evidence_hint is required")
    return errors


def _validate_artifact_path(value: object, workspace_root: Path | None, label: str) -> list[str]:
    errors: list[str] = []
    if not _nonempty_string(value):
        return [f"{label}.artifact_path is required"]
    path = Path(str(value))
    if path.is_absolute() or ".." in path.parts:
        return [f"{label}.artifact_path must stay inside the workspace"]
    if workspace_root is not None:
        root = workspace_root.resolve()
        resolved = (root / path).resolve()
        try:
            resolved.relative_to(root)
        except ValueError:
            errors.append(f"{label}.artifact_path escapes the workspace")
        else:
            if not resolved.is_file():
                errors.append(f"{label}.artifact_path does not exist: {value}")
    return errors


def validate(
    data: object,
    contract: object | None = None,
    *,
    workspace_root: Path | None = None,
) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["evidence document must be an object"]

    unknown = set(data) - TOP_LEVEL_FIELDS
    if unknown:
        errors.append(f"unknown top-level fields: {sorted(unknown)}")

    task_id = data.get("task_id")
    if not _nonempty_string(task_id):
        errors.append("task_id is required")

    completion_status = data.get("completion_status")
    if completion_status not in ALLOWED_COMPLETION:
        errors.append("completion_status is invalid")

    workspace = data.get("workspace")
    if not isinstance(workspace, dict):
        errors.append("workspace must be an object")
    else:
        unknown_workspace = set(workspace) - WORKSPACE_FIELDS
        if unknown_workspace:
            errors.append(f"workspace has unknown fields: {sorted(unknown_workspace)}")
        for field in ("repository", "branch", "head_sha"):
            if not _nonempty_string(workspace.get(field)):
                errors.append(f"workspace.{field} is required")
        if workspace.get("working_tree_reviewed") is not True:
            errors.append("workspace.working_tree_reviewed must be true")

    items = data.get("items")
    if not isinstance(items, list) or not items:
        errors.append("items must be a non-empty array")
        items = []

    seen: set[str] = set()
    item_by_id: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(items):
        prefix = f"items[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{prefix} must be an object")
            continue
        unknown_item = set(item) - ITEM_FIELDS
        if unknown_item:
            errors.append(f"{prefix} has unknown fields: {sorted(unknown_item)}")

        criterion_id = item.get("criterion_id")
        if not _nonempty_string(criterion_id):
            errors.append(f"{prefix}.criterion_id is required")
        elif criterion_id in seen:
            errors.append(f"{prefix}.criterion_id is duplicated: {criterion_id}")
        else:
            seen.add(criterion_id)
            item_by_id[str(criterion_id)] = item

        status = item.get("status")
        if status not in ALLOWED_STATUSES:
            errors.append(f"{prefix}.status is invalid")
        if not _nonempty_string(item.get("summary")):
            errors.append(f"{prefix}.summary is required")

        evidence = item.get("evidence")
        if not isinstance(evidence, list):
            errors.append(f"{prefix}.evidence must be an array")
            evidence = []
        if status in {"PASS", "FAIL"} and not evidence:
            errors.append(f"{prefix}.evidence must not be empty for {status}")
        if status in {"NOT_RUN", "NOT_APPLICABLE"} and not _nonempty_string(item.get("summary")):
            errors.append(f"{prefix}.summary must explain {status}")

        for evidence_index, record in enumerate(evidence):
            label = f"{prefix}.evidence[{evidence_index}]"
            if not isinstance(record, dict):
                errors.append(f"{label} must be an object")
                continue
            unknown_record = set(record) - EVIDENCE_FIELDS
            if unknown_record:
                errors.append(f"{label} has unknown fields: {sorted(unknown_record)}")
            record_type = record.get("type")
            if record_type not in ALLOWED_EVIDENCE_TYPES:
                errors.append(f"{label}.type is invalid")
            if not _nonempty_string(record.get("summary")):
                errors.append(f"{label}.summary is required")

            if record_type == "command":
                if not _nonempty_string(record.get("command")):
                    errors.append(f"{label}.command is required")
                if record.get("fresh") is not True:
                    errors.append(f"{label}.fresh must be true")
                exit_code = record.get("exit_code")
                if type(exit_code) is not int:
                    errors.append(f"{label}.exit_code must be an integer")
                elif status == "PASS" and exit_code != 0:
                    errors.append(f"{label}.exit_code is {exit_code} for PASS")
                elif status == "FAIL" and exit_code == 0:
                    errors.append(f"{label}.exit_code must be non-zero for FAIL command evidence")
                receipt = record.get("receipt")
                if receipt is not None:
                    if not isinstance(receipt, dict):
                        errors.append(f"{label}.receipt must be an object")
                    else:
                        unknown_receipt = set(receipt) - RECEIPT_FIELDS
                        missing_receipt = RECEIPT_FIELDS - set(receipt)
                        if unknown_receipt:
                            errors.append(
                                f"{label}.receipt has unknown fields: {sorted(unknown_receipt)}"
                            )
                        if missing_receipt:
                            errors.append(
                                f"{label}.receipt is missing fields: {sorted(missing_receipt)}"
                            )
                        for field in ("run_id", "command_id"):
                            if not _nonempty_string(receipt.get(field)):
                                errors.append(f"{label}.receipt.{field} is required")
                        if not SHA256_RE.fullmatch(
                            str(receipt.get("payload_sha256", ""))
                        ):
                            errors.append(
                                f"{label}.receipt.payload_sha256 must be lowercase SHA-256"
                            )
                        child_exit = receipt.get("child_exit_code")
                        if type(child_exit) is not int:
                            errors.append(
                                f"{label}.receipt.child_exit_code must be an integer"
                            )
                        elif type(exit_code) is int and child_exit != exit_code:
                            errors.append(
                                f"{label}.receipt.child_exit_code must match exit_code"
                            )
                    verifier_argv = record.get("verifier_argv")
                    if (
                        not isinstance(verifier_argv, list)
                        or not verifier_argv
                        or any(not _nonempty_string(value) for value in verifier_argv)
                    ):
                        errors.append(
                            f"{label}.verifier_argv must be the exact non-empty receipt child argv"
                        )
                elif "verifier_argv" in record:
                    errors.append(
                        f"{label}.verifier_argv requires a structured execution receipt"
                    )
            else:
                for field in ("command", "verifier_argv", "fresh", "exit_code", "receipt"):
                    if field in record:
                        errors.append(f"{label}.{field} is only valid for command evidence")

            if record_type == "artifact":
                errors.extend(_validate_artifact_path(record.get("artifact_path"), workspace_root, label))
            elif "artifact_path" in record:
                errors.append(f"{label}.artifact_path is only valid for artifact evidence")

    risks = data.get("remaining_risks")
    if not isinstance(risks, list) or any(not _nonempty_string(item) for item in risks):
        errors.append("remaining_risks must be an array of non-empty strings")

    contract_errors: list[str] = []
    if contract is not None:
        contract_errors = validate_contract(contract)
        errors.extend(contract_errors)
        if not contract_errors and isinstance(contract, dict):
            if task_id != contract.get("task_id"):
                errors.append("evidence task_id does not match contract task_id")
            acceptance = {str(item["id"]): item for item in contract["acceptance"]}
            expected = set(acceptance)
            missing = sorted(expected - seen)
            unexpected = sorted(seen - expected)
            if missing:
                errors.append(f"acceptance criteria missing from evidence: {missing}")
            if unexpected:
                errors.append(f"evidence contains criteria absent from contract: {unexpected}")
            for criterion_id, criterion in acceptance.items():
                item = item_by_id.get(criterion_id)
                if item is None:
                    continue
                status = item.get("status")
                if criterion.get("required") is True and status != "PASS":
                    errors.append(f"required criterion {criterion_id} is {status}, not PASS")
                if status == "NOT_APPLICABLE" and criterion.get("required") is True:
                    errors.append(f"required criterion {criterion_id} cannot be NOT_APPLICABLE")
    elif completion_status == "COMPLETE":
        errors.append("COMPLETE evidence requires --contract so omitted acceptance criteria can be detected")

    if completion_status == "COMPLETE":
        for index, item in enumerate(items):
            if isinstance(item, dict) and item.get("status") in {"FAIL", "NOT_RUN"}:
                errors.append(f"items[{index}] is {item.get('status')}; COMPLETE is not allowed")
    elif completion_status in {"PARTIAL", "BLOCKED"}:
        errors.append(f"completion_status is {completion_status}, not COMPLETE")

    return errors


def load_json(path: Path, label: str) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read {label}: {exc}") from exc


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path, help="Completion-evidence JSON file.")
    parser.add_argument("--contract", type=Path, help="Task-contract JSON used for exact acceptance coverage.")
    parser.add_argument(
        "--workspace-root",
        type=Path,
        help="Optional workspace root used to verify artifact evidence paths.",
    )
    args = parser.parse_args()
    try:
        data = load_json(args.path, "evidence")
        contract = load_json(args.contract, "contract") if args.contract else None
    except ValueError as exc:
        print(f"ERROR: {exc}")
        return 2

    errors = validate(data, contract, workspace_root=args.workspace_root)
    for error in errors:
        print(f"ERROR: {error}")
    print(f"evidence gate: {'PASS' if not errors else 'FAIL'}")
    if contract is None:
        print("NOTE: no contract supplied; COMPLETE is rejected and omitted criteria cannot be detected.")
    print("NOTE: this gate validates structure and disclosed status, not whether external evidence is truthful.")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
