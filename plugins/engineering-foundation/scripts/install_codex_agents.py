#!/usr/bin/env python3
"""Install optional Codex custom-agent templates into a target project."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil


def plan_install(source: Path, target: Path, force: bool) -> list[dict[str, str]]:
    if not source.is_dir():
        raise FileNotFoundError(f"agent source directory not found: {source}")

    actions: list[dict[str, str]] = []
    for source_file in sorted(source.glob("*.toml")):
        target_file = target / source_file.name
        if not target_file.exists():
            status = "create"
        elif target_file.read_bytes() == source_file.read_bytes():
            status = "identical"
        elif force:
            status = "replace"
        else:
            status = "conflict"
        actions.append(
            {
                "source": str(source_file),
                "target": str(target_file),
                "status": status,
            }
        )
    return actions


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", type=Path, default=Path(".codex/agents"))
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    script_root = Path(__file__).resolve().parent
    source = script_root.parent / "adapters" / "codex" / "agents"
    target = args.target.resolve()

    try:
        actions = plan_install(source, target, args.force)
    except OSError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        raise SystemExit(2) from exc

    conflicts = [item for item in actions if item["status"] == "conflict"]
    if args.apply and not conflicts:
        target.mkdir(parents=True, exist_ok=True)
        for item in actions:
            if item["status"] in {"create", "replace"}:
                shutil.copy2(item["source"], item["target"])

    result = {
        "ok": not conflicts,
        "applied": bool(args.apply and not conflicts),
        "target": str(target),
        "actions": actions,
    }
    print(json.dumps(result, indent=2))
    raise SystemExit(1 if conflicts else 0)


if __name__ == "__main__":
    main()
