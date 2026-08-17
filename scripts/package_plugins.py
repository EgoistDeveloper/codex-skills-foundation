#!/usr/bin/env python3
"""Build deterministic per-plugin ZIP archives and a checksum manifest."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "catalog/plugins.json"
FIXED_TIME = (2020, 1, 1, 0, 0, 0)
FIXED_FILE_MODE = stat.S_IFREG | 0o644
WINDOWS_REPARSE_POINT = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x0400)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def is_reparse_point(metadata: os.stat_result) -> bool:
    """Return whether Windows marked an entry as a filesystem reparse point."""
    attributes = getattr(metadata, "st_file_attributes", 0)
    return bool(attributes & WINDOWS_REPARSE_POINT)


def inspect_path(path: Path) -> os.stat_result:
    try:
        return path.lstat()
    except OSError as exc:
        raise ValueError(f"cannot inspect release path {path}: {exc}") from exc


def reject_link_or_reparse(path: Path, metadata: os.stat_result) -> None:
    if stat.S_ISLNK(metadata.st_mode):
        raise ValueError(f"symlinks are not allowed in release packages: {path}")
    if is_reparse_point(metadata):
        raise ValueError(
            f"junctions and reparse points are not allowed in release packages: {path}"
        )


def resolve_strict(path: Path) -> Path:
    try:
        return path.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise ValueError(f"cannot safely resolve release path {path}: {exc}") from exc


def require_contained(path: Path, root: Path, *, label: str) -> Path:
    try:
        return path.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"{label} {path} is outside repository root {root}") from exc


def validate_relative_path(relative: Path) -> None:
    if relative.is_absolute() or relative.drive or ".." in relative.parts:
        raise ValueError(f"unsafe release path: {relative}")


def validate_repository_root(repository_root: Path) -> Path:
    resolved = resolve_strict(repository_root)
    metadata = inspect_path(resolved)
    if not stat.S_ISDIR(metadata.st_mode):
        raise ValueError(f"release repository root is not a directory: {repository_root}")
    return resolved


def validate_plugin_root(plugin_root: Path, repository_root: Path) -> Path:
    resolved_repository = validate_repository_root(repository_root)
    metadata = inspect_path(plugin_root)
    reject_link_or_reparse(plugin_root, metadata)
    if not stat.S_ISDIR(metadata.st_mode):
        raise ValueError(f"release plugin root is not a directory: {plugin_root}")
    resolved_plugin = resolve_strict(plugin_root)
    require_contained(resolved_plugin, resolved_repository, label="release plugin root")
    return resolved_plugin


def validate_path_components(path: Path, plugin_root: Path) -> os.stat_result:
    try:
        relative = path.relative_to(plugin_root)
    except ValueError as exc:
        raise ValueError(f"release file {path} is outside plugin root {plugin_root}") from exc
    validate_relative_path(relative)
    if not relative.parts:
        raise ValueError(f"release file path names the plugin root: {path}")

    current = plugin_root
    metadata: os.stat_result | None = None
    for index, part in enumerate(relative.parts):
        current /= part
        metadata = inspect_path(current)
        reject_link_or_reparse(current, metadata)
        if index < len(relative.parts) - 1 and not stat.S_ISDIR(metadata.st_mode):
            raise ValueError(f"release path component is not a directory: {current}")

    assert metadata is not None
    return metadata


def validate_regular_file(
    path: Path, plugin_root: Path, resolved_plugin_root: Path
) -> os.stat_result:
    metadata = validate_path_components(path, plugin_root)
    if not stat.S_ISREG(metadata.st_mode):
        raise ValueError(f"unsupported special file in release package: {path}")
    resolved = resolve_strict(path)
    try:
        resolved.relative_to(resolved_plugin_root)
    except ValueError as exc:
        raise ValueError(
            f"release file {path} resolves outside plugin root {resolved_plugin_root}"
        ) from exc
    return metadata


def scan_directory(
    directory: Path,
    relative_directory: Path,
    resolved_plugin_root: Path,
    files: list[Path],
) -> None:
    try:
        with os.scandir(directory) as entries:
            scanned = sorted(entries, key=lambda entry: entry.name)
    except OSError as exc:
        raise ValueError(f"cannot scan release directory {directory}: {exc}") from exc

    for entry in scanned:
        path = directory / entry.name
        relative = relative_directory / entry.name
        validate_relative_path(relative)
        try:
            metadata = entry.stat(follow_symlinks=False)
        except OSError as exc:
            raise ValueError(f"cannot inspect release path {path}: {exc}") from exc
        reject_link_or_reparse(path, metadata)
        resolved = resolve_strict(path)
        try:
            resolved.relative_to(resolved_plugin_root)
        except ValueError as exc:
            raise ValueError(
                f"release path {path} resolves outside plugin root {resolved_plugin_root}"
            ) from exc

        if stat.S_ISDIR(metadata.st_mode):
            scan_directory(path, relative, resolved_plugin_root, files)
        elif stat.S_ISREG(metadata.st_mode):
            files.append(path)
        else:
            raise ValueError(f"unsupported special file in release package: {path}")


def safe_files(plugin_root: Path, *, repository_root: Path | None = None) -> list[Path]:
    repository = ROOT if repository_root is None else repository_root
    resolved_plugin_root = validate_plugin_root(plugin_root, repository)
    files: list[Path] = []
    scan_directory(plugin_root, Path(), resolved_plugin_root, files)
    # Path ordering follows host path semantics, including case-folding on Windows.
    # Sort canonical POSIX archive names instead so entry order is identical everywhere.
    return sorted(files, key=lambda path: path.relative_to(plugin_root).as_posix())


def read_verified_file(path: Path, plugin_root: Path, repository_root: Path) -> bytes:
    """Revalidate a packaged file immediately before opening and reading it."""
    resolved_plugin_root = validate_plugin_root(plugin_root, repository_root)
    validate_regular_file(path, plugin_root, resolved_plugin_root)
    try:
        with path.open("rb") as handle:
            opened = os.fstat(handle.fileno())
            reject_link_or_reparse(path, opened)
            if not stat.S_ISREG(opened.st_mode):
                raise ValueError(f"unsupported special file in release package: {path}")

            current = validate_regular_file(path, plugin_root, resolved_plugin_root)
            if (current.st_dev, current.st_ino) != (opened.st_dev, opened.st_ino):
                raise ValueError(f"release file changed while being opened: {path}")
            return handle.read()
    except OSError as exc:
        raise ValueError(f"cannot read release file {path}: {exc}") from exc


def build_archive(plugin: dict, output: Path) -> tuple[Path, str]:
    plugin_path = Path(plugin["path"])
    validate_relative_path(plugin_path)
    plugin_root = ROOT / plugin_path
    archive = output / f"{plugin['name']}-{plugin['version']}.zip"
    files = safe_files(plugin_root, repository_root=ROOT)
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

    # The packages are tiny. Store entries without DEFLATE so archive bytes do not depend on
    # platform-specific zlib builds or Python patch releases.
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_STORED) as zf:
        for path in files:
            relative = path.relative_to(plugin_root).as_posix()
            info = zipfile.ZipInfo(relative, FIXED_TIME)
            # Plugin packages contain data/configuration files, not directly executed programs.
            # Pin Unix metadata instead of using os.access(), whose X_OK behavior differs on Windows.
            info.create_system = 3
            info.external_attr = FIXED_FILE_MODE << 16
            info.compress_type = zipfile.ZIP_STORED
            zf.writestr(info, read_verified_file(path, plugin_root, ROOT))
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
        checksum_path.write_bytes(
            "".join(f"{digest}  {path.name}\n" for path, digest in built).encode("utf-8")
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
