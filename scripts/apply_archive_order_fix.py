#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one match, found {count}")
    return text.replace(old, new, 1)


package = ROOT / "scripts/package_plugins.py"
text = package.read_text(encoding="utf-8")
text = replace_once(
    text,
    '    for path in sorted(plugin_root.rglob("*")):',
    '    for path in plugin_root.rglob("*"):',
    "path traversal",
)
text = replace_once(
    text,
    "    return files\n\n\ndef build_archive",
    '''    # Path ordering follows host path semantics, including case-folding on Windows.
    # Sort canonical POSIX archive names instead so entry order is identical everywhere.
    return sorted(files, key=lambda path: path.relative_to(plugin_root).as_posix())


def build_archive''',
    "canonical archive ordering",
)
text = replace_once(
    text,
    '''        checksum_path.write_text(
            "".join(f"{digest}  {path.name}\\n" for path, digest in built),
            encoding="utf-8",
        )''',
    '''        checksum_path.write_bytes(
            "".join(f"{digest}  {path.name}\\n" for path, digest in built).encode("utf-8")
        )''',
    "checksum newline policy",
)
package.write_text(text, encoding="utf-8")

test = ROOT / "tests/test_packaging.py"
text = test.read_text(encoding="utf-8")
text = replace_once(
    text,
    "                    names = zf.namelist()",
    "                    names = zf.namelist()\n                    self.assertEqual(names, sorted(names))",
    "archive order assertion",
)
test.write_text(text, encoding="utf-8")
print("archive order/newline patch: PASS")
