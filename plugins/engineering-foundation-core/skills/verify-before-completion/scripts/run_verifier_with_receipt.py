#!/usr/bin/env python3
"""Run one verifier without a shell and emit one bound execution receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = 1
RECEIPT_TYPE = "foundation.verifier-execution"
RECEIPT_PREFIX = "FOUNDATION_VERIFIER_RECEIPT_V1="
WINDOWS_REPARSE_POINT = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x0400)
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
IDENTITY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


class RunnerError(RuntimeError):
    """The runner could not produce trustworthy execution evidence."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _is_reparse_point(metadata: os.stat_result) -> bool:
    return bool(
        getattr(metadata, "st_file_attributes", 0) & WINDOWS_REPARSE_POINT
    )


def _inspect_unlinked(path: Path, *, label: str) -> os.stat_result:
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise RunnerError(f"cannot inspect {label}: {path}: {exc}") from exc
    if stat.S_ISLNK(metadata.st_mode) or _is_reparse_point(metadata):
        raise RunnerError(f"{label} must not be a symlink, junction, or reparse point: {path}")
    return metadata


def _inspect_existing_chain(path: Path, *, label: str) -> None:
    lexical = Path(os.path.abspath(path))
    current = Path(lexical.anchor)
    for part in lexical.parts[1:]:
        current /= part
        _inspect_unlinked(current, label=f"{label} path component")


def _regular_file(path: Path, *, label: str) -> Path:
    lexical = Path(os.path.abspath(path))
    _inspect_existing_chain(lexical, label=label)
    metadata = _inspect_unlinked(lexical, label=label)
    if not stat.S_ISREG(metadata.st_mode):
        raise RunnerError(f"{label} must be a regular file: {lexical}")
    try:
        resolved = lexical.resolve(strict=True)
    except OSError as exc:
        raise RunnerError(f"cannot resolve {label}: {lexical}: {exc}") from exc
    if resolved != lexical.resolve(strict=False):
        raise RunnerError(f"{label} resolution is unstable: {lexical}")
    return resolved


def _real_directory(path: Path, *, label: str) -> Path:
    lexical = Path(os.path.abspath(path))
    _inspect_existing_chain(lexical, label=label)
    metadata = _inspect_unlinked(lexical, label=label)
    if not stat.S_ISDIR(metadata.st_mode):
        raise RunnerError(f"{label} must be a directory: {lexical}")
    try:
        return lexical.resolve(strict=True)
    except OSError as exc:
        raise RunnerError(f"cannot resolve {label}: {lexical}: {exc}") from exc


def _require_under(path: Path, root: Path, *, label: str) -> None:
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise RunnerError(f"{label} is outside the bounded run root: {path}") from exc


def _validate_directory_chain(root: Path, destination_parent: Path) -> None:
    root_lexical = Path(os.path.abspath(root))
    parent_lexical = Path(os.path.abspath(destination_parent))
    try:
        relative = parent_lexical.relative_to(root_lexical)
    except ValueError as exc:
        raise RunnerError(
            f"output directory parent is outside the bounded run root: {parent_lexical}"
        ) from exc
    current = root_lexical
    root_resolved = _real_directory(current, label="run root")
    for part in relative.parts:
        current /= part
        metadata = _inspect_unlinked(current, label="output parent component")
        if not stat.S_ISDIR(metadata.st_mode):
            raise RunnerError(f"output parent component is not a directory: {current}")
    parent_resolved = _real_directory(parent_lexical, label="output directory parent")
    _require_under(parent_resolved, root_resolved, label="resolved output directory parent")


def _create_output_directory(run_root: Path, requested: Path) -> tuple[Path, Path]:
    root_lexical = Path(os.path.abspath(run_root))
    output_lexical = Path(os.path.abspath(requested))
    try:
        relative = output_lexical.relative_to(root_lexical)
    except ValueError as exc:
        raise RunnerError(f"output directory is outside the bounded run root: {requested}") from exc
    if not relative.parts:
        raise RunnerError("output directory must be below, not equal to, the run root")
    _validate_directory_chain(root_lexical, output_lexical.parent)
    if output_lexical.exists() or output_lexical.is_symlink():
        raise RunnerError(f"output directory must be fresh: {output_lexical}")
    try:
        output_lexical.mkdir()
    except OSError as exc:
        raise RunnerError(f"cannot create output directory {output_lexical}: {exc}") from exc
    output_resolved = _real_directory(output_lexical, label="output directory")
    run_resolved = _real_directory(root_lexical, label="run root")
    _require_under(output_resolved, run_resolved, label="resolved output directory")
    return run_resolved, output_resolved


def _atomic_write(path: Path, value: bytes, *, run_root: Path) -> None:
    output_directory = _real_directory(path.parent, label="receipt output directory")
    _require_under(output_directory, run_root, label="receipt output directory")
    if path.exists() or path.is_symlink():
        raise RunnerError(f"receipt artifact already exists: {path}")
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_BINARY"):
        flags |= os.O_BINARY
    descriptor: int | None = None
    try:
        descriptor = os.open(temporary, flags, 0o600)
        with os.fdopen(descriptor, "wb", closefd=True) as stream:
            descriptor = None
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
        _real_directory(path.parent, label="receipt output directory")
        os.link(temporary, path, follow_symlinks=False)
        temporary.unlink()
        metadata = _inspect_unlinked(path, label="receipt artifact")
        if not stat.S_ISREG(metadata.st_mode):
            raise RunnerError(f"receipt artifact is not a regular file: {path}")
        if path.read_bytes() != value:
            raise RunnerError(f"receipt artifact changed during publication: {path}")
    except OSError as exc:
        raise RunnerError(f"cannot publish receipt artifact {path}: {exc}") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
        try:
            if temporary.exists() or temporary.is_symlink():
                temporary.unlink()
        except OSError:
            pass


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _resolve_executable(value: str) -> Path:
    candidate = Path(value)
    if not candidate.is_absolute():
        discovered = shutil.which(value)
        if not discovered:
            raise RunnerError(f"child executable was not found: {value}")
        candidate = Path(discovered)
    return _regular_file(candidate, label="child executable")


def _validated_identity(value: str, *, label: str) -> str:
    if not IDENTITY_RE.fullmatch(value):
        raise RunnerError(f"{label} has an invalid identity format")
    return value


def build_receipt(args: argparse.Namespace) -> dict[str, object]:
    run_id = _validated_identity(args.run_id, label="run id")
    command_id = _validated_identity(args.command_id, label="command id")
    campaign_id = _validated_identity(args.campaign_id, label="campaign id")
    turn_binding = _validated_identity(args.turn_binding, label="turn binding")
    if not SHA256_RE.fullmatch(args.candidate_manifest_sha256):
        raise RunnerError("candidate manifest SHA-256 is invalid")
    child_argv = list(args.child_argv)
    if child_argv and child_argv[0] == "--":
        child_argv.pop(0)
    if len(child_argv) < 2:
        raise RunnerError("child argv must contain an executable and verifier path")

    run_root, output_directory = _create_output_directory(
        args.run_root,
        args.output_directory,
    )
    cwd = _real_directory(args.cwd, label="child cwd")
    executable = _resolve_executable(child_argv[0])
    verifier_requested = Path(child_argv[1])
    if not verifier_requested.is_absolute():
        raise RunnerError("verifier path must be absolute")
    verifier = _regular_file(verifier_requested, label="verifier")
    _require_under(verifier, cwd, label="verifier")
    runner = _regular_file(Path(__file__), label="receipt runner")
    exact_argv = [str(executable), str(verifier), *child_argv[2:]]
    runner_sha256 = _hash_file(runner)
    executable_sha256 = _hash_file(executable)
    verifier_sha256 = _hash_file(verifier)
    if _hash_file(_regular_file(executable, label="child executable")) != executable_sha256:
        raise RunnerError("child executable changed before execution")
    if _hash_file(_regular_file(verifier, label="verifier")) != verifier_sha256:
        raise RunnerError("verifier changed before execution")

    started_at = utc_now()
    started = time.monotonic_ns()
    try:
        child = subprocess.run(
            exact_argv,
            cwd=str(cwd),
            shell=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise RunnerError(f"cannot execute verifier child: {exc}") from exc
    finished = time.monotonic_ns()
    finished_at = utc_now()
    if _hash_file(_regular_file(executable, label="child executable")) != executable_sha256:
        raise RunnerError("child executable changed during execution")
    if _hash_file(_regular_file(verifier, label="verifier")) != verifier_sha256:
        raise RunnerError("verifier changed during execution")
    if _hash_file(_regular_file(runner, label="receipt runner")) != runner_sha256:
        raise RunnerError("receipt runner changed during execution")
    stdout = bytes(child.stdout)
    stderr = bytes(child.stderr)
    stdout_path = output_directory / "stdout.bin"
    stderr_path = output_directory / "stderr.bin"
    _atomic_write(stdout_path, stdout, run_root=run_root)
    _atomic_write(stderr_path, stderr, run_root=run_root)

    payload: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "receipt_type": RECEIPT_TYPE,
        "run_id": run_id,
        "command_id": command_id,
        "candidate_manifest_sha256": args.candidate_manifest_sha256,
        "campaign_id": campaign_id,
        "turn_binding": turn_binding,
        "runner": {
            "path": "scripts/run_verifier_with_receipt.py",
            "sha256": runner_sha256,
        },
        "child": {
            "resolved_executable": str(executable),
            "executable_sha256": executable_sha256,
            "argv": exact_argv,
            "cwd": str(cwd),
            "verifier_path": str(verifier),
            "verifier_sha256": verifier_sha256,
            "exit_code": int(child.returncode),
        },
        "stdout": {
            "relative_path": stdout_path.relative_to(run_root).as_posix(),
            "sha256": sha256_bytes(stdout),
            "byte_size": len(stdout),
        },
        "stderr": {
            "relative_path": stderr_path.relative_to(run_root).as_posix(),
            "sha256": sha256_bytes(stderr),
            "byte_size": len(stderr),
        },
        "started_at": started_at,
        "finished_at": finished_at,
        "duration_ms": max(0, (finished - started) // 1_000_000),
    }
    payload["payload_sha256"] = sha256_bytes(canonical_json_bytes(payload))
    return payload


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--command-id", required=True)
    parser.add_argument("--candidate-manifest-sha256", required=True)
    parser.add_argument("--campaign-id", required=True)
    parser.add_argument("--turn-binding", required=True)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    parser.add_argument("--cwd", type=Path, required=True)
    parser.add_argument("child_argv", nargs=argparse.REMAINDER)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    try:
        receipt = build_receipt(parse_args(argv))
    except (RunnerError, OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(RECEIPT_PREFIX + canonical_json_bytes(receipt).decode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
