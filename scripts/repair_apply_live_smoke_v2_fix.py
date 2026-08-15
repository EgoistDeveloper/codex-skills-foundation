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


def escape_newlines_in_short_strings(source: str) -> str:
    """Repair generator-interpreted newlines inside ordinary Python strings."""

    output: list[str] = []
    state = "code"
    quote = ""
    index = 0

    while index < len(source):
        if state == "code":
            if source.startswith("'''", index) or source.startswith('"""', index):
                token = source[index : index + 3]
                output.append(token)
                quote = token[0]
                state = "triple"
                index += 3
                continue
            char = source[index]
            output.append(char)
            if char == "#":
                state = "comment"
            elif char in {"'", '"'}:
                quote = char
                state = "short"
            index += 1
            continue

        if state == "comment":
            char = source[index]
            output.append(char)
            index += 1
            if char == "\n":
                state = "code"
            continue

        if state == "triple":
            delimiter = quote * 3
            if source.startswith(delimiter, index):
                output.append(delimiter)
                state = "code"
                quote = ""
                index += 3
                continue
            char = source[index]
            output.append(char)
            if char == "\\" and index + 1 < len(source):
                output.append(source[index + 1])
                index += 2
            else:
                index += 1
            continue

        char = source[index]
        if char == "\\" and index + 1 < len(source):
            output.append(char)
            output.append(source[index + 1])
            index += 2
            continue
        if char == quote:
            output.append(char)
            state = "code"
            quote = ""
            index += 1
            continue
        if char == "\n":
            output.append("\\n")
            index += 1
            continue
        output.append(char)
        index += 1

    if state not in {"code", "comment"}:
        raise SystemExit(f"generated Python still contains an unterminated {state} string")
    return "".join(output)


root = path.parents[1]
for target in (
    root / "scripts/run_codex_live_smoke.py",
    root / "tests/test_codex_live_smoke.py",
):
    generated = target.read_text(encoding="utf-8")
    target.write_text(
        escape_newlines_in_short_strings(generated),
        encoding="utf-8",
        newline="\n",
    )
