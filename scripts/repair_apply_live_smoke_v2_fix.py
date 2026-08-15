#!/usr/bin/env python3
from __future__ import annotations

import runpy
from pathlib import Path

path = Path(__file__).with_name("apply_live_smoke_v2_fix.py")
text = path.read_text(encoding="utf-8")
replacements = [
    ('"retry_after.mjs": \'\'\'export', '"retry_after.mjs": """export'),
    ('\n\'\'\',\n        "smoke-test.mjs": \'\'\'import', '\n""",\n        "smoke-test.mjs": """import'),
    ('\n}\n\'\'\',\n        "README.md"', '\n}\n""",\n        "README.md"'),
]
for old, new in replacements:
    if text.count(old) != 1:
        raise SystemExit(f"quoting repair expected one match, found {text.count(old)}: {old!r}")
    text = text.replace(old, new, 1)
path.write_text(text, encoding="utf-8", newline="\n")
runpy.run_path(str(path), run_name="__main__")

# The one-shot patch embeds source code inside Python strings. Normalize any
# quote-newline-quote sequences back to explicit escaped newline literals in the
# generated Python files before validation.
root = path.parents[1]
for target in (
    root / "scripts/run_codex_live_smoke.py",
    root / "tests/test_codex_live_smoke.py",
):
    generated = target.read_text(encoding="utf-8")
    generated = generated.replace('"\n"', '"\\n"')
    generated = generated.replace("'\n'", "'\\n'")
    target.write_text(generated, encoding="utf-8", newline="\n")
