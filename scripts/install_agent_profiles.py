#!/usr/bin/env python3
"""Explicitly install optional project-scoped Codex or Claude agent profiles."""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROVIDERS = {
    "codex": (ROOT / "profiles" / "codex", Path(".codex/agents"), "*.toml"),
    "claude": (ROOT / "profiles" / "claude", Path(".claude/agents"), "*.md"),
}


def plan(provider: str, target: Path) -> list[tuple[Path, Path, str]]:
    source_root, relative_destination, pattern = PROVIDERS[provider]
    destination_root = target / relative_destination
    actions: list[tuple[Path, Path, str]] = []
    for source in sorted(source_root.glob(pattern)):
        destination = destination_root / source.name
        if not destination.exists():
            status = "CREATE"
        elif destination.read_bytes() == source.read_bytes():
            status = "UNCHANGED"
        else:
            status = "CONFLICT"
        actions.append((source, destination, status))
    return actions


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", choices=sorted(PROVIDERS), required=True)
    parser.add_argument("--target", type=Path, required=True, help="Target repository root.")
    parser.add_argument("--apply", action="store_true", help="Copy files. Without this flag the command is a dry run.")
    parser.add_argument("--force", action="store_true", help="Overwrite conflicting profile files.")
    args = parser.parse_args()

    target = args.target.resolve()
    if not target.is_dir():
        print(f"ERROR: target repository directory does not exist: {target}", file=sys.stderr)
        return 2

    actions = plan(args.provider, target)
    if not actions:
        print(f"ERROR: no {args.provider} profiles found", file=sys.stderr)
        return 2

    conflicts = [item for item in actions if item[2] == "CONFLICT"]
    for source, destination, status in actions:
        print(f"{status}: {destination.relative_to(target)} <- {source.relative_to(ROOT)}")

    if conflicts and not args.force:
        print("ERROR: conflicting profiles found; review them or rerun with --force", file=sys.stderr)
        return 3
    if not args.apply:
        print("dry run: no files changed; add --apply to install")
        return 0

    for source, destination, status in actions:
        if status == "UNCHANGED":
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    print(f"installed {args.provider} project profiles: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
