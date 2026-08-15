#!/usr/bin/env python3
"""One-shot source patch used by the v0.2.1 repair branch."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one match, found {count}")
    return text.replace(old, new, 1)


def patch_validator() -> None:
    path = ROOT / "scripts/validate_repository.py"
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        'ALLOWED_OPENAI_INSTALLATION = {"AVAILABLE", "INSTALLED_BY_DEFAULT", "NOT_AVAILABLE"}\n\n\nclass Report:',
        '''ALLOWED_OPENAI_INSTALLATION = {"AVAILABLE", "INSTALLED_BY_DEFAULT", "NOT_AVAILABLE"}
EXCLUDED_PATH_PARTS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "dist",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".tox",
    ".nox",
}


class Report:''',
        "validator exclusion constants",
    )
    text = replace_once(
        text,
        '''def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def load_json''',
        '''def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def is_excluded_path(path: Path) -> bool:
    try:
        parts = path.relative_to(ROOT).parts
    except ValueError:
        return False
    return any(part in EXCLUDED_PATH_PARTS for part in parts)


def load_json''',
        "validator exclusion helper",
    )
    text = replace_once(
        text,
        '        if ".git" in path.parts or "dist" in path.parts:\n            continue',
        '        if is_excluded_path(path):\n            continue',
        "markdown scan exclusion",
    )
    text = replace_once(
        text,
        '        if not path.is_file() or ".git" in path.parts or "dist" in path.parts:\n            continue',
        '        if not path.is_file() or is_excluded_path(path):\n            continue',
        "security scan exclusion",
    )
    path.write_text(text, encoding="utf-8")


def patch_packaging_test() -> None:
    path = ROOT / "tests/test_packaging.py"
    text = path.read_text(encoding="utf-8")
    text = replace_once(text, "import json\n", "import json\nimport stat\n", "packaging stat import")
    old = (
        '                    self.assertTrue(any(name.endswith("/SKILL.md") for name in names))\n'
        '                    self.assertTrue(all(not Path(name).is_absolute() and ".." not in Path(name).parts for name in names))'
    )
    new = old + (
        '\n                    for info in zf.infolist():\n'
        '                        self.assertEqual(info.create_system, 3)\n'
        '                        mode = info.external_attr >> 16\n'
        '                        self.assertEqual(mode & 0o170000, stat.S_IFREG)\n'
        '                        self.assertEqual(mode & 0o777, 0o644)'
    )
    path.write_text(replace_once(text, old, new, "packaging mode assertions"), encoding="utf-8")


def patch_validator_test() -> None:
    path = ROOT / "tests/test_repository_validator.py"
    text = path.read_text(encoding="utf-8")
    marker = '    def test_catalog_matches_five_modular_packages(self) -> None:\n'
    addition = '''    def test_local_dependency_directories_are_excluded(self) -> None:
        for relative in (
            ".venv/Lib/site-packages/example.py",
            "venv/lib/python/site-packages/example.py",
            "node_modules/example/index.js",
            ".tox/example/lib/site-packages/example.py",
        ):
            self.assertTrue(module.is_excluded_path(ROOT / relative))
        self.assertFalse(
            module.is_excluded_path(
                ROOT / "plugins/engineering-foundation-core/skills/task-contract/SKILL.md"
            )
        )

'''
    path.write_text(
        replace_once(text, marker, addition + marker, "validator exclusion test"),
        encoding="utf-8",
    )


def bump_catalog() -> None:
    path = ROOT / "catalog/plugins.json"
    catalog = json.loads(path.read_text(encoding="utf-8"))
    for plugin in catalog["plugins"]:
        current = plugin["version"]
        if current != "0.2.0":
            raise SystemExit(f"unexpected version for {plugin['name']}: {current}")
        plugin["version"] = "0.2.1"
    path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def update_changelog() -> None:
    path = ROOT / "CHANGELOG.md"
    text = path.read_text(encoding="utf-8")
    heading = "# Changelog\n\n"
    if not text.startswith(heading):
        raise SystemExit("unexpected changelog heading")
    entry = '''## 0.2.1 - 2026-08-15

### Cross-platform correctness

- Excluded local virtual environments and dependency directories from repository-wide link, secret, and placeholder scans.
- Added `.venv`, `venv`, `node_modules`, and common tool caches to `.gitignore`.
- Replaced operating-system-dependent executable checks with fixed Unix `0644` ZIP metadata.
- Added regression tests for local dependency exclusions and cross-platform archive modes.

'''
    path.write_text(heading + entry + text[len(heading) :], encoding="utf-8")


def main() -> None:
    patch_validator()
    patch_packaging_test()
    patch_validator_test()
    bump_catalog()
    update_changelog()
    print("v0.2.1 source patch: PASS")


if __name__ == "__main__":
    main()
