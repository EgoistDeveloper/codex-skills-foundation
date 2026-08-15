#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "scripts/run_codex_live_smoke.py"
TESTS = ROOT / "tests/test_codex_live_smoke.py"

removed_total = 0
for target in (HARNESS, TESTS):
    lines = target.read_text(encoding="utf-8").splitlines()
    cleaned = [line for line in lines if line.strip() != "r"]
    removed = len(lines) - len(cleaned)
    if removed == 0:
        raise SystemExit(f"expected generated raw-marker lines in {target}")
    removed_total += removed
    target.write_text("\n".join(cleaned) + "\n", encoding="utf-8", newline="\n")

text = HARNESS.read_text(encoding="utf-8")
old = '''    allowed = normalized_path(allowed_skill_path) if allowed_skill_path else None
    forbidden = {
        normalized_path(path)
        for path in disabled_skill_paths
        if allowed is None or normalized_path(path) != allowed
    }
    for command in turn.commands:
        normalized_command = command.command.replace("\\\\", "/").lower()
        if "/.codex/memories/" in normalized_command or "\\\\.codex\\\\memories\\\\" in command.command.lower():
            findings.append("agent read Codex memory state")
        for path in forbidden:
            path_text = path.replace("\\\\", "/").lower()
            if path_text in normalized_command:
                findings.append(f"agent read disabled skill path: {path}")
'''
new = '''    allowed = normalized_path(allowed_skill_path) if allowed_skill_path else None
    forbidden: list[tuple[str, set[str]]] = []
    for raw_path in disabled_skill_paths:
        normalized = normalized_path(raw_path)
        if allowed is not None and normalized == allowed:
            continue
        variants = {
            raw_path.replace("\\\\", "/").lower(),
            normalized.replace("\\\\", "/").lower(),
        }
        forbidden.append((raw_path, variants))

    for command in turn.commands:
        normalized_command = command.command.replace("\\\\", "/").lower()
        if "/.codex/memories/" in normalized_command or "\\\\.codex\\\\memories\\\\" in command.command.lower():
            findings.append("agent read Codex memory state")
        for raw_path, variants in forbidden:
            if any(path_text in normalized_command for path_text in variants):
                findings.append(f"agent read disabled skill path: {raw_path}")
'''
if text.count(old) != 1:
    raise SystemExit(f"environment path block expected once, found {text.count(old)}")
HARNESS.write_text(text.replace(old, new, 1), encoding="utf-8", newline="\n")

for target in (HARNESS, TESTS):
    source = target.read_text(encoding="utf-8")
    compile(source, str(target), "exec")

print(f"generated live smoke cleanup: PASS ({removed_total} markers removed)")
