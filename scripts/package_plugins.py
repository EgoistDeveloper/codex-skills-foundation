#!/usr/bin/env python3
"""Build deterministic per-plugin ZIP archives and a checksum manifest."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import sys
import tempfile
import zipfile
from pathlib import Path, PureWindowsPath

SCRIPT_DIRECTORY = Path(__file__).resolve().parent
if str(SCRIPT_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIRECTORY))

import packaged_resources

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "catalog/plugins.json"
FIXED_TIME = (2020, 1, 1, 0, 0, 0)
FIXED_FILE_MODE = stat.S_IFREG | 0o644
WINDOWS_REPARSE_POINT = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x0400)
REQUIRED_PLUGIN_FILES = {
    "engineering-foundation-core": {
        Path("skills/verify-before-completion/scripts/evidence_gate.py"),
        Path(
            "skills/verify-before-completion/scripts/"
            "run_verifier_with_receipt.py"
        ),
    },
}


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
    windows_path = PureWindowsPath(relative.as_posix())
    if (
        relative.is_absolute()
        or relative.drive
        or ".." in relative.parts
        or windows_path.is_absolute()
        or windows_path.drive
        or ".." in windows_path.parts
        or any("\\" in part for part in relative.parts)
    ):
        raise ValueError(f"unsafe release path: {relative}")


def validate_existing_path_components(path: Path) -> None:
    """Reject links, reparse points, and non-directories in an output path."""
    if not path.is_absolute() or ".." in path.parts:
        raise ValueError(f"unsafe release output path: {path}")

    current = Path(path.anchor)
    for part in path.parts[1:]:
        current /= part
        try:
            metadata = current.lstat()
        except FileNotFoundError:
            break
        except OSError as exc:
            raise ValueError(f"cannot inspect release output path {current}: {exc}") from exc
        reject_link_or_reparse(current, metadata)
        if current != path and not stat.S_ISDIR(metadata.st_mode):
            raise ValueError(f"release output path component is not a directory: {current}")


def validate_output_directory(output: Path) -> Path:
    validate_existing_path_components(output)
    metadata = inspect_path(output)
    reject_link_or_reparse(output, metadata)
    if not stat.S_ISDIR(metadata.st_mode):
        raise ValueError(f"release output is not a directory: {output}")
    return resolve_strict(output)


def prepare_output_directory(requested: Path) -> Path:
    resolved_repository = validate_repository_root(ROOT)
    if requested.is_absolute():
        output = requested
    else:
        validate_relative_path(requested)
        output = ROOT / requested

    try:
        relative = output.relative_to(ROOT)
    except ValueError as exc:
        raise ValueError(f"release output {output} is outside repository root {ROOT}") from exc
    validate_relative_path(relative)
    if not relative.parts:
        raise ValueError("release output must be a subdirectory of the repository root")

    # Check existing ancestors before mkdir so a nested junction cannot redirect creation.
    validate_existing_path_components(output)
    try:
        output.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ValueError(f"cannot create release output directory {output}: {exc}") from exc
    resolved_output = validate_output_directory(output)
    require_contained(resolved_output, resolved_repository, label="release output")
    return resolved_output


def validate_output_filename(filename: str) -> None:
    candidate = Path(filename)
    if (
        not filename
        or "/" in filename
        or "\\" in filename
        or candidate.is_absolute()
        or candidate.drive
        or len(candidate.parts) != 1
        or filename in {".", ".."}
    ):
        raise ValueError(f"unsafe release archive filename: {filename}")


def archive_filename(plugin: dict) -> str:
    name = plugin.get("name")
    version = plugin.get("version")
    if not isinstance(name, str) or not name:
        raise ValueError("release plugin name must be a non-empty string")
    if not isinstance(version, str) or not version:
        raise ValueError(f"release plugin version must be a non-empty string: {name}")
    filename = f"{name}-{version}.zip"
    validate_output_filename(filename)
    return filename


def validate_release_plugins(catalog: object) -> list[dict]:
    if not isinstance(catalog, dict):
        raise ValueError("release catalog root must be an object")
    plugins = catalog.get("plugins")
    if not isinstance(plugins, list) or not plugins:
        raise ValueError("release catalog plugins must be a non-empty array")

    destinations: set[str] = set()
    for index, plugin in enumerate(plugins):
        if not isinstance(plugin, dict):
            raise ValueError(f"release catalog plugin {index} must be an object")
        plugin_path = plugin.get("path")
        if not isinstance(plugin_path, str) or not plugin_path:
            raise ValueError(f"release catalog plugin {index} path must be a non-empty string")
        validate_relative_path(Path(plugin_path))
        filename = archive_filename(plugin)
        if filename in destinations:
            raise ValueError(f"duplicate release archive destination: {filename}")
        destinations.add(filename)
    return plugins


def validate_output_destination(path: Path) -> None:
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return
    except OSError as exc:
        raise ValueError(f"cannot inspect release output file {path}: {exc}") from exc
    reject_link_or_reparse(path, metadata)
    if not stat.S_ISREG(metadata.st_mode):
        raise ValueError(f"release output path is not a regular file: {path}")


def commit_temporary_output(
    temporary: Path, destination: Path, created: os.stat_result
) -> None:
    metadata = inspect_path(temporary)
    reject_link_or_reparse(temporary, metadata)
    if not stat.S_ISREG(metadata.st_mode):
        raise ValueError(f"temporary release output is not a regular file: {temporary}")
    if (metadata.st_dev, metadata.st_ino) != (created.st_dev, created.st_ino):
        raise ValueError(f"temporary release output changed before publication: {temporary}")
    validate_output_destination(destination)
    try:
        os.replace(temporary, destination)
    except OSError as exc:
        raise ValueError(f"cannot publish release output {destination}: {exc}") from exc


def write_atomic_output(output: Path, filename: str, data: bytes) -> Path:
    resolved_output = validate_output_directory(output)
    validate_output_filename(filename)
    destination = resolved_output / filename
    validate_output_destination(destination)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=resolved_output, prefix=f".{filename}.", suffix=".tmp"
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            created = os.fstat(handle.fileno())
            handle.write(data)
            handle.flush()
        commit_temporary_output(temporary, destination, created)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
    return destination


def remove_existing_release_outputs(output: Path) -> None:
    try:
        with os.scandir(output) as entries:
            candidates = sorted(
                (
                    entry
                    for entry in entries
                    if entry.name.endswith(".zip") or entry.name == "SHA256SUMS"
                ),
                key=lambda entry: entry.name,
            )
    except OSError as exc:
        raise ValueError(f"cannot scan release output directory {output}: {exc}") from exc

    for entry in candidates:
        path = output / entry.name
        try:
            metadata = entry.stat(follow_symlinks=False)
        except OSError as exc:
            raise ValueError(f"cannot inspect release output file {path}: {exc}") from exc
        reject_link_or_reparse(path, metadata)
        if not stat.S_ISREG(metadata.st_mode):
            raise ValueError(f"release output path is not a regular file: {path}")
        try:
            path.unlink()
        except OSError as exc:
            raise ValueError(f"cannot remove previous release output {path}: {exc}") from exc


def remove_generated_outputs(paths: list[Path]) -> list[str]:
    errors: list[str] = []
    for path in paths:
        try:
            metadata = path.lstat()
        except FileNotFoundError:
            continue
        except OSError as exc:
            errors.append(f"cannot inspect generated release output {path}: {exc}")
            continue

        try:
            reject_link_or_reparse(path, metadata)
            if not stat.S_ISREG(metadata.st_mode):
                raise ValueError(f"generated release output is not a regular file: {path}")
            path.unlink()
        except (OSError, ValueError) as exc:
            errors.append(str(exc))
    return errors


def validate_repository_root(repository_root: Path) -> Path:
    metadata = inspect_path(repository_root)
    reject_link_or_reparse(repository_root, metadata)
    if not stat.S_ISDIR(metadata.st_mode):
        raise ValueError(f"release repository root is not a directory: {repository_root}")
    resolved = resolve_strict(repository_root)
    return resolved


def validate_plugin_root(plugin_root: Path, repository_root: Path) -> Path:
    resolved_repository = validate_repository_root(repository_root)
    try:
        relative = plugin_root.relative_to(repository_root)
    except ValueError as exc:
        raise ValueError(
            f"release plugin root {plugin_root} is outside repository root {repository_root}"
        ) from exc
    validate_relative_path(relative)
    if not relative.parts:
        raise ValueError(f"release plugin root names the repository root: {plugin_root}")

    current = repository_root
    for part in relative.parts:
        current /= part
        metadata = inspect_path(current)
        reject_link_or_reparse(current, metadata)
        if not stat.S_ISDIR(metadata.st_mode):
            raise ValueError(f"release plugin path component is not a directory: {current}")

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
    resolved_output = validate_output_directory(output)
    archive_name = archive_filename(plugin)
    archive = resolved_output / archive_name
    validate_output_destination(archive)
    resource_references = packaged_resources.validate_source_plugin(
        plugin_root,
        plugin["name"],
        repository_root=ROOT,
    )
    files = safe_files(plugin_root, repository_root=ROOT)
    required = {
        Path("plugin.json"),
        Path(".codex-plugin/plugin.json"),
        Path(".claude-plugin/plugin.json"),
    }
    required.update(REQUIRED_PLUGIN_FILES.get(plugin["name"], set()))
    relative_files = {path.relative_to(plugin_root) for path in files}
    generated_python_cache = {
        path
        for path in relative_files
        if "__pycache__" in path.parts or path.suffix in {".pyc", ".pyo"}
    }
    if generated_python_cache:
        raise ValueError(
            f"{plugin['name']} contains generated Python cache files: "
            f"{sorted(map(str, generated_python_cache))}"
        )
    missing = required - relative_files
    if missing:
        raise ValueError(f"{plugin['name']} missing package files: {sorted(map(str, missing))}")
    if not any(path.parts[:1] == ("skills",) and path.name == "SKILL.md" for path in relative_files):
        raise ValueError(f"{plugin['name']} has no packaged skill")

    descriptor, temporary_name = tempfile.mkstemp(
        dir=resolved_output, prefix=f".{archive_name}.", suffix=".tmp"
    )
    temporary = Path(temporary_name)
    try:
        # The packages are tiny. Store entries without DEFLATE so archive bytes do not depend on
        # platform-specific zlib builds or Python patch releases.
        with os.fdopen(descriptor, "w+b") as handle:
            created = os.fstat(handle.fileno())
            with zipfile.ZipFile(handle, "w", compression=zipfile.ZIP_STORED) as zf:
                for path in files:
                    relative = path.relative_to(plugin_root).as_posix()
                    info = zipfile.ZipInfo(relative, FIXED_TIME)
                    # Plugin packages contain data/configuration files, not directly executed
                    # programs. Pin Unix metadata instead of using os.access(), whose X_OK
                    # behavior differs on Windows.
                    info.create_system = 3
                    info.external_attr = FIXED_FILE_MODE << 16
                    info.compress_type = zipfile.ZIP_STORED
                    zf.writestr(info, read_verified_file(path, plugin_root, ROOT))
            handle.flush()
            handle.seek(0)
            with zipfile.ZipFile(handle, "r") as built_archive:
                packaged_resources.validate_zip_closure(
                    plugin_root,
                    plugin["name"],
                    built_archive,
                    references=resource_references,
                    repository_root=ROOT,
                )
            handle.seek(0)
            digest = hashlib.sha256()
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)

        commit_temporary_output(temporary, archive, created)
        return archive, digest.hexdigest()
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("dist"))
    parser.add_argument("--check", action="store_true", help="Build twice and require byte-identical output.")
    args = parser.parse_args()
    built: list[tuple[Path, str]] = []
    checksum_path: Path | None = None
    try:
        output = prepare_output_directory(args.output)
        catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
        plugins = validate_release_plugins(catalog)
        remove_existing_release_outputs(output)
        for plugin in plugins:
            built.append(build_archive(plugin, output))
        checksum_path = write_atomic_output(
            output,
            "SHA256SUMS",
            "".join(f"{digest}  {path.name}\n" for path, digest in built).encode("utf-8")
        )
        if args.check:
            first = {path.name: path.read_bytes() for path, _ in built}
            for plugin in plugins:
                build_archive(plugin, output)
            for path, _ in built:
                if path.read_bytes() != first[path.name]:
                    raise ValueError(f"non-deterministic archive: {path.name}")
    except (OSError, TypeError, ValueError, KeyError, json.JSONDecodeError) as exc:
        generated = [path for path, _ in built]
        if checksum_path is not None:
            generated.append(checksum_path)
        cleanup_errors = remove_generated_outputs(generated)
        print(f"ERROR: {exc}")
        for cleanup_error in cleanup_errors:
            print(f"ERROR: failed to clean generated output: {cleanup_error}")
        return 1

    for path, digest in built:
        print(f"{digest}  {path.relative_to(ROOT)}")
    print("package build: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
