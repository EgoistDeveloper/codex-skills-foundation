#!/usr/bin/env python3
from __future__ import annotations

import re
import runpy
from pathlib import Path

path = Path(__file__).with_name("apply_live_smoke_v2_fix.py")
text = path.read_text(encoding="utf-8")

# The fixture replacement is itself embedded in a triple-single-quoted patch
# string. Use triple-double quotes for the generated JavaScript payloads so the
# one-shot patch remains valid Python.
replacements = [
    ('"retry_after.mjs": \'\'\'export', '"retry_after.mjs": """export'),
    ('\n\'\'\',\n        "smoke-test.mjs": \'\'\'import', '\n""",\n        "smoke-test.mjs": """import'),
    ('\n}\n\'\'\',\n        "README.md"', '\n}\n""",\n        "README.md"'),
]
for old, new in replacements:
    if text.count(old) != 1:
        raise SystemExit(f"quoting repair expected one match, found {text.count(old)}: {old!r}")
    text = text.replace(old, new, 1)

# Every multiline source payload in the one-shot patch is code or documentation
# whose backslash escapes must survive into the generated file. Prefix opening
# triple-single delimiters with `r`; closing delimiters contain no following text
# and therefore do not match this expression.
text, count = re.subn(
    r"(?m)^(\s*)'''(?=[^'\r\n])",
    r"\1r'''",
    text,
)
if count < 8:
    raise SystemExit(f"expected multiple raw replacement strings, converted only {count}")

path.write_text(text, encoding="utf-8", newline="\n")
runpy.run_path(str(path), run_name="__main__")
