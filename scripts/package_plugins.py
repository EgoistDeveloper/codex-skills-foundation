#!/usr/bin/env python3
"""Build deterministic per-plugin ZIP archives and a checksum manifest."""
from __future__ import annotations

import argparse
import hashlib
import json
import stat
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "catalog/plugins.json"
FIXED_TIME = (2020, 1, 1, 0, 0, 0)
FIXED_FILE_MODE = stat.S_IFREG | 0o644


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_files(plugin_root: Path) -> list[Path]:
    files: list[Path] = []
    for path in sorted(plugin_root.rglob("*")):
        if path.is_symlink():
            raise ValueError(f"symlinks are not allowed in release packages: {path}")
        if path.is_file():
            relative = path.relative_to(plugin_root)
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError(f"unsafe release path: {relative}")
            files.append(path)
    return files


def build_archive(plugin: dict, output: Path) -> tuple[Path, str]:
    plugin_root = ROOT / plugin["path"]
    archive = output / f"{plugin['name']}-{plugin['version']}.zip"
    files = safe_files(plugin_root)
    required = {
        Path("plugin.json"),
        Path(".codex-plugin/plugin.json"),
        Path(".claude-plugin/plugin.json"),
    }
    relative_files = {path.relative_to(plugin_root) for path in files}
    missing = required - relative_files
    if missing:
        raise ValueError(f"{plugin['name']} missing package files: {sorted(map(str, missing))}")
    if not any(path.parts[:1] == ("skills",) and path.name == "SKILL.md" for path in relative_files):
        raise ValueError(f"{plugin['name']} has no packaged skill")

    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path in files:
            relative = path.relative_to(plugin_root).as_posix()
            info = zipfile.ZipInfo(relative, FIXED_TIME)
            # Plugin packages contain data/configuration files, not directly executed programs.
            # Pin Unix metadata instead of using os.access(), whose X_OK behavior differs on Windows.
            info.create_system = 3
            info.external_attr = FIXED_FILE_MODE << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(info, path.read_bytes())
    return archive, sha256(archive)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "dist")
    parser.add_argument("--check", action="store_true", help="Build twice and require byte-identical output.")
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    output.mkdir(parents=True, exist_ok=True)
    for old in output.glob("*.zip"):
        old.unlink()
    checksum_path = output / "SHA256SUMS"
    if checksum_path.exists():
        checksum_path.unlink()

    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    built: list[tuple[Path, str]] = []
    try:
        for plugin in catalog["plugins"]:
            built.append(build_archive(plugin, output))
        checksum_path.write_text(
            "".join(f"{digest}  {path.name}\n" for path, digest in built),
            encoding="utf-8",
        )
        if args.check:
            first = {path.name: path.read_bytes() for path, _ in built}
            for plugin in catalog["plugins"]:
                build_archive(plugin, output)
            for path, _ in built:
                if path.read_bytes() != first[path.name]:
                    raise ValueError(f"non-deterministic archive: {path.name}")
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}")
        return 1

    for path, digest in built:
        print(f"{digest}  {path.relative_to(ROOT)}")
    print("package build: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
