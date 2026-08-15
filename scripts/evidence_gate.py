#!/usr/bin/env python3
"""Validate completion-evidence semantics without pretending to validate external truth."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ALLOWED_STATUSES = {"PASS", "FAIL", "NOT_RUN", "NOT_APPLICABLE"}
ALLOWED_COMPLETION = {"COMPLETE", "PARTIAL", "BLOCKED"}
TOP_LEVEL_FIELDS = {"task_id", "completion_status", "items", "working_tree_reviewed", "remaining_risks"}
ITEM_FIELDS = {"criterion", "status", "evidence"}
CONTRACT_FIELDS = {
    "task_id", "objective", "acceptance", "non_goals", "constraints", "evidence", "risk", "reopen_conditions"
}


def validate_contract(contract: object) -> list[str]:
    errors: list[str] = []
    if not isinstance(contract, dict):
        return ["contract must be an object"]
    unknown = set(contract) - CONTRACT_FIELDS
    if unknown:
        errors.append(f"contract has unknown fields: {sorted(unknown)}")
    for field in ("task_id", "objective"):
        value = contract.get(field)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"contract.{field} is required")
    acceptance = contract.get("acceptance")
    if not isinstance(acceptance, list) or not acceptance:
        errors.append("contract.acceptance must be a non-empty list")
    elif any(not isinstance(item, str) or not item.strip() for item in acceptance):
        errors.append("contract.acceptance must contain non-empty strings")
    elif len(set(acceptance)) != len(acceptance):
        errors.append("contract.acceptance contains duplicate criteria")
    return errors


def validate(data: object, contract: object | None = None) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["document must be an object"]

    unknown = set(data) - TOP_LEVEL_FIELDS
    if unknown:
        errors.append(f"unknown top-level fields: {sorted(unknown)}")

    task_id = data.get("task_id")
    if not isinstance(task_id, str) or not task_id.strip():
        errors.append("task_id is required")

    completion_status = data.get("completion_status")
    if completion_status not in ALLOWED_COMPLETION:
        errors.append("completion_status is invalid")
    elif completion_status != "COMPLETE":
        errors.append(f"completion_status is {completion_status}, not COMPLETE")

    items = data.get("items")
    if not isinstance(items, list) or not items:
        errors.append("items must be a non-empty list")
        items = []

    seen: set[str] = set()
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            errors.append(f"items[{index}] must be an object")
            continue
        unknown_item = set(item) - ITEM_FIELDS
        if unknown_item:
            errors.append(f"items[{index}] has unknown fields: {sorted(unknown_item)}")

        criterion = item.get("criterion")
        if not isinstance(criterion, str) or not criterion.strip():
            errors.append(f"items[{index}].criterion is required")
        elif criterion in seen:
            errors.append(f"items[{index}].criterion is duplicated")
        else:
            seen.add(criterion)

        status = item.get("status")
        evidence = item.get("evidence")
        if status not in ALLOWED_STATUSES:
            errors.append(f"items[{index}].status is invalid")
        if not isinstance(evidence, str) or not evidence.strip():
            errors.append(f"items[{index}].evidence is required for every status")
        if status == "FAIL":
            errors.append(f"items[{index}] is FAIL")
        elif status == "NOT_RUN":
            errors.append(f"items[{index}] is NOT_RUN; redefine acceptance or run the evidence before COMPLETE")

    if data.get("working_tree_reviewed") is not True:
        errors.append("working_tree_reviewed must be true")

    risks = data.get("remaining_risks")
    if not isinstance(risks, list) or any(not isinstance(item, str) or not item.strip() for item in risks):
        errors.append("remaining_risks must be an array of non-empty strings")

    if contract is not None:
        contract_errors = validate_contract(contract)
        errors.extend(contract_errors)
        if not contract_errors and isinstance(contract, dict):
            if task_id != contract.get("task_id"):
                errors.append("evidence task_id does not match contract task_id")
            expected = set(contract["acceptance"])
            missing = sorted(expected - seen)
            unexpected = sorted(seen - expected)
            if missing:
                errors.append(f"acceptance criteria missing from evidence: {missing}")
            if unexpected:
                errors.append(f"evidence contains criteria absent from contract: {unexpected}")
    return errors


def load_json(path: Path, label: str) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read {label}: {exc}") from exc


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path, help="Completion-evidence JSON file.")
    parser.add_argument("--contract", type=Path, help="Task-contract JSON used to detect omitted acceptance criteria.")
    args = parser.parse_args()
    try:
        data = load_json(args.path, "evidence")
        contract = load_json(args.contract, "contract") if args.contract else None
    except ValueError as exc:
        print(f"ERROR: {exc}")
        return 2

    errors = validate(data, contract)
    for error in errors:
        print(f"ERROR: {error}")
    print(f"evidence gate: {'PASS' if not errors else 'FAIL'}")
    if contract is None:
        print("NOTE: no contract supplied; omitted acceptance criteria cannot be detected.")
    print("NOTE: this gate validates structure and disclosed status, not whether external evidence is truthful.")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
