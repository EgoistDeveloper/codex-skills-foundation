#!/usr/bin/env python3
"""Keep canonical UTF-8 artifacts separate from safe console presentation."""

from __future__ import annotations

import codecs
import hashlib
import json
import os
import uuid
from pathlib import Path
from typing import TextIO


FALLBACK_ENCODING = "ascii"


def usable_stream_encoding(stream: TextIO) -> str:
    """Return the declared stream encoding or one deterministic fallback."""
    encoding = getattr(stream, "encoding", None)
    if not isinstance(encoding, str) or not encoding.strip():
        return FALLBACK_ENCODING
    try:
        codecs.lookup(encoding)
    except LookupError:
        return FALLBACK_ENCODING
    return encoding


def render_for_console(text: str, encoding: str) -> str:
    """Escape only characters that the selected console cannot represent."""
    try:
        codecs.lookup(encoding)
    except LookupError:
        encoding = FALLBACK_ENCODING
    return text.encode(encoding, errors="backslashreplace").decode(encoding)


def write_console_safe(stream: TextIO, text: str) -> int:
    """Write presentation text without changing its canonical source value."""
    rendered = render_for_console(text, usable_stream_encoding(stream))
    try:
        return stream.write(rendered)
    except UnicodeEncodeError:
        # A stream may misreport its real codec. Retry once with ASCII-only
        # presentation, while allowing every non-encoding I/O error to escape.
        fallback = render_for_console(text, FALLBACK_ENCODING)
        return stream.write(fallback)


def atomic_write_bytes(path: Path, value: bytes) -> None:
    """Publish one byte-exact artifact atomically with no default encoding."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(
        f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp"
    )
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
        os.replace(temporary, path)
    finally:
        if descriptor is not None:
            os.close(descriptor)
        try:
            if temporary.exists() or temporary.is_symlink():
                temporary.unlink()
        except OSError:
            pass


def atomic_write_utf8(path: Path, text: str) -> bytes:
    """Encode canonical text as UTF-8 and publish the exact bytes atomically."""
    value = text.encode("utf-8")
    atomic_write_bytes(path, value)
    return value


def raw_stream_path(transcript: Path, stream_name: str) -> Path:
    """Return the bounded sibling path for one captured raw child stream."""
    if stream_name not in {"stdout", "stderr"}:
        raise ValueError(f"unsupported child stream: {stream_name}")
    return transcript.with_name(f"{transcript.stem}.{stream_name}.bin")


def transcript_identity_path(transcript: Path) -> Path:
    """Return the completion manifest path for one transcript bundle."""
    return transcript.with_name(f"{transcript.stem}.artifacts.json")


def _artifact_identity(path: Path, value: bytes) -> dict[str, object]:
    return {
        "filename": path.name,
        "sha256": hashlib.sha256(value).hexdigest(),
        "byte_size": len(value),
    }


def write_transcript_bundle(
    transcript: Path,
    canonical_text: str,
    stdout: bytes,
    stderr: bytes,
) -> dict[str, object]:
    """Publish raw streams, canonical UTF-8 text, then their exact identity."""
    stdout_path = raw_stream_path(transcript, "stdout")
    stderr_path = raw_stream_path(transcript, "stderr")
    canonical = canonical_text.encode("utf-8")
    atomic_write_bytes(stdout_path, stdout)
    atomic_write_bytes(stderr_path, stderr)
    atomic_write_bytes(transcript, canonical)
    identity: dict[str, object] = {
        "schema_version": 1,
        "decoding": {"encoding": "utf-8", "errors": "replace"},
        "artifacts": {
            "transcript": _artifact_identity(transcript, canonical),
            "stdout": _artifact_identity(stdout_path, stdout),
            "stderr": _artifact_identity(stderr_path, stderr),
        },
    }
    atomic_write_utf8(
        transcript_identity_path(transcript),
        json.dumps(
            identity,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n",
    )
    return identity
