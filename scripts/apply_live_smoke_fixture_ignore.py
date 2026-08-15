#!/usr/bin/env python3
from pathlib import Path

path = Path(__file__).resolve().with_name("run_codex_live_smoke.py")
text = path.read_text(encoding="utf-8")
marker = "def fixture_source() -> dict[str, str]:\n    return {\n        \"retry_after.py\":"
replacement = (
    "def fixture_source() -> dict[str, str]:\n"
    "    return {\n"
    "        \".gitignore\": \"__pycache__/\\n*.py[cod]\\n\",\n"
    "        \"retry_after.py\":"
)
if text.count(marker) != 1:
    raise SystemExit(f"fixture marker count is {text.count(marker)}, expected 1")
path.write_text(text.replace(marker, replacement, 1), encoding="utf-8")
print("live fixture ignore patch: PASS")
