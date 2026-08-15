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


def escape_newlines_in_short_strings(source: str, *, label: str) -> str:
    """Repair generator-interpreted newlines inside ordinary Python strings."""

    output: list[str] = []
    state = "code"
    quote = ""
    state_start = 0
    index = 0

    while index < len(source):
        if state == "code":
            if source.startswith("'''", index) or source.startswith('"""', index):
                token = source[index : index + 3]
                output.append(token)
                quote = token[0]
                state = "triple"
                state_start = index
                index += 3
                continue
            char = source[index]
            output.append(char)
            if char == "#":
                state = "comment"
                state_start = index
            elif char in {"'", '"'}:
                quote = char
                state = "short"
                state_start = index
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
        line = source.count("\n", 0, state_start) + 1
        context = source[max(0, state_start - 120) : min(len(source), state_start + 240)]
        raise SystemExit(
            f"{label}: generated Python contains an unterminated {state} string "
            f"starting at line {line}: {context!r}"
        )
    return "".join(output)


root = path.parents[1]
for target in (
    root / "scripts/run_codex_live_smoke.py",
    root / "tests/test_codex_live_smoke.py",
):
    generated = target.read_text(encoding="utf-8")
    target.write_text(
        escape_newlines_in_short_strings(generated, label=str(target)),
        encoding="utf-8",
        newline="\n",
    )
