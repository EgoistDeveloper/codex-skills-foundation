#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
targets = (
    ROOT / "scripts/run_codex_live_smoke.py",
    ROOT / "tests/test_codex_live_smoke.py",
)

removed_total = 0
for target in targets:
    lines = target.read_text(encoding="utf-8").splitlines()
    cleaned = [line for line in lines if line.strip() != "r"]
    removed = len(lines) - len(cleaned)
    if removed == 0:
        raise SystemExit(f"expected generated raw-marker lines in {target}")
    removed_total += removed
    source = "\n".join(cleaned) + "\n"
    compile(source, str(target), "exec")
    target.write_text(source, encoding="utf-8", newline="\n")

print(f"generated live smoke cleanup: PASS ({removed_total} markers removed)")
