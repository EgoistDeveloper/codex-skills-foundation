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
    """Repair newlines interpreted by the one-shot generator inside short strings.

    Triple-quoted generated fixtures and documentation remain untouched. A physical
    newline inside an ordinary single- or double-quoted Python string is never valid,
    so replacing it with the two characters ``\\n`` is lossless for this generator.
    """

    output: list[str] = []
    quote: str | None = None
    triple = False
    index = 0

    while index < len(source):
        if quote is None:
            if source.startswith("'''", index) or source.startswith('"""', index):
                token = source[index : index + 3]
                output.append(token)
                quote = token[0]
                triple = True
                index += 3
                continue
            char = source[index]
            output.append(char)
            if char in {"'", '"'}:
                quote = char
                triple = False
            index += 1
            continue

        if triple:
            delimiter = quote * 3
            if source.startswith(delimiter, index):
                output.append(delimiter)
                quote = None
                triple = False
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
            quote = None
            index += 1
            continue
        if char == "\n":
            output.append("\\n")
            index += 1
            continue
        output.append(char)
        index += 1

    if quote is not None:
        raise SystemExit("generated Python still contains an unterminated string")
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
