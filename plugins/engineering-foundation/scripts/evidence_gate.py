#!/usr/bin/env python3
"""Validate a machine-readable completion evidence packet."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def validate_packet(packet: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    goal = packet.get("goal")
    if not isinstance(goal, str) or not goal.strip():
        errors.append("`goal` must be a non-empty string")

    requirements = packet.get("requirements")
    if not isinstance(requirements, list) or not requirements:
        errors.append("`requirements` must be a non-empty array")
    else:
        seen: set[str] = set()
        for index, requirement in enumerate(requirements):
            prefix = f"requirements[{index}]"
            if not isinstance(requirement, dict):
                errors.append(f"{prefix} must be an object")
                continue
            requirement_id = requirement.get("id")
            if not isinstance(requirement_id, str) or not requirement_id.strip():
                errors.append(f"{prefix}.id must be non-empty")
            elif requirement_id in seen:
                errors.append(f"{prefix}.id is duplicated: {requirement_id}")
            else:
                seen.add(requirement_id)
            if requirement.get("status") != "pass":
                errors.append(f"{prefix}.status must be `pass`")
            evidence = requirement.get("evidence")
            if not isinstance(evidence, list) or not evidence or not all(
                isinstance(item, str) and item.strip() for item in evidence
            ):
                errors.append(f"{prefix}.evidence must contain at least one concrete item")

    commands = packet.get("commands")
    if not isinstance(commands, list) or not commands:
        errors.append("`commands` must be a non-empty array")
    else:
        for index, command in enumerate(commands):
            prefix = f"commands[{index}]"
            if not isinstance(command, dict):
                errors.append(f"{prefix} must be an object")
                continue
            if not isinstance(command.get("command"), str) or not command["command"].strip():
                errors.append(f"{prefix}.command must be non-empty")
            if command.get("fresh") is not True:
                errors.append(f"{prefix}.fresh must be true")
            exit_code = command.get("exit_code")
            if not isinstance(exit_code, int) or isinstance(exit_code, bool):
                errors.append(f"{prefix}.exit_code must be an integer")
            elif exit_code != 0:
                errors.append(f"{prefix}.exit_code is {exit_code}")
            if not isinstance(command.get("summary"), str) or not command["summary"].strip():
                errors.append(f"{prefix}.summary must be non-empty")

    if packet.get("diff_reviewed") is not True:
        errors.append("`diff_reviewed` must be true")

    unresolved = packet.get("unresolved", [])
    if not isinstance(unresolved, list):
        errors.append("`unresolved` must be an array")
    elif unresolved:
        errors.append("`unresolved` must be empty before completion")

    return errors


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("packet", type=Path)
    args = parser.parse_args()

    try:
        payload = json.loads(args.packet.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("packet must contain a JSON object")
        errors = validate_packet(payload)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(json.dumps({"pass": False, "errors": [str(exc)]}, indent=2))
        raise SystemExit(2) from exc

    print(json.dumps({"pass": not errors, "errors": errors}, indent=2))
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
