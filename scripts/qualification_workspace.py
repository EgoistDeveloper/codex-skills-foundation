#!/usr/bin/env python3
"""Allocate short, bounded, disposable workspaces for qualification harnesses."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import tempfile
import time
from pathlib import Path
from typing import Any, Callable

from console_output import atomic_write_utf8


WORKSPACE_ROOT_ENV = "FOUNDATION_QUALIFICATION_WORKSPACE_ROOT"
WORKSPACE_ROOT_NAME = "efq"
WINDOWS_CLASSIC_LIMIT = 260
POSIX_CONSERVATIVE_LIMIT = 4096
SAFETY_MARGIN = 20
FILE_ATTRIBUTE_REPARSE_POINT = 0x400
IDENTITY_VALUE_RE = re.compile(r"[A-Za-z0-9_.-]{1,64}\Z")
IDENTITY_FIELDS = (
    "campaign",
    "family",
    "case",
    "variant",
    "repetition",
    "attempt",
)
DEFAULT_SUFFIXES = {
    "git_object": Path("c") / ".git" / "objects" / "ff" / ("a" * 38),
    "git_pack_temp": (
        Path("c") / ".git" / "objects" / "pack" / ("tmp_pack_" + "a" * 40)
    ),
    "git_lock": Path("c") / ".git" / ("index.lock." + "a" * 32 + ".tmp"),
    "fixture_file": Path("c") / "completion-evidence.schema.json",
    "receipt": Path("c") / ("verifier-receipt.stderr.bin." + "a" * 32 + ".tmp"),
    "cleanup_temp": Path("c") / ("cleanup-" + "a" * 32 + ".tmp"),
}
_REGISTERED: list["WorkspaceLease"] = []
_PROBE_COUNTER = 0


class WorkspaceError(RuntimeError):
    """Fail-closed qualification workspace error."""


class WorkspacePathError(WorkspaceError):
    """A workspace or artifact path cannot satisfy the bounded path contract."""

    def __init__(
        self,
        message: str,
        *,
        label: str,
        measured: int | None = None,
        allowed: int | None = None,
    ) -> None:
        super().__init__(message)
        self.label = label
        self.measured = measured
        self.allowed = allowed

    def payload(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "outcome": "FAIL",
            "model_calls": 0,
            "error_code": "qualification_path_budget",
            "label": self.label,
            "measured": self.measured,
            "allowed": self.allowed,
            "message": str(self),
        }


def default_disposable_root() -> Path:
    configured = os.environ.get(WORKSPACE_ROOT_ENV)
    root = Path(configured) if configured else Path(tempfile.gettempdir()) / WORKSPACE_ROOT_NAME
    return Path(os.path.abspath(root))


def platform_path_limit() -> int:
    return WINDOWS_CLASSIC_LIMIT if os.name == "nt" else POSIX_CONSERVATIVE_LIMIT


def _path_length(path: Path) -> int:
    return len(str(Path(os.path.abspath(path))))


def _is_reparse(metadata: os.stat_result) -> bool:
    attributes = getattr(metadata, "st_file_attributes", 0)
    return bool(attributes & FILE_ATTRIBUTE_REPARSE_POINT)


def _reject_link_or_reparse(path: Path, *, label: str) -> None:
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return
    if stat.S_ISLNK(metadata.st_mode) or _is_reparse(metadata):
        raise WorkspacePathError(
            f"{label} is a symlink, junction, or reparse point",
            label=label,
        )


def _existing_components(path: Path) -> list[Path]:
    absolute = Path(os.path.abspath(path))
    components = [absolute, *absolute.parents]
    return [component for component in reversed(components) if component.exists()]


def reject_linked_components(path: Path, *, label: str) -> None:
    for component in _existing_components(path):
        _reject_link_or_reparse(component, label=label)


def _relative_to(path: Path, root: Path, *, label: str) -> Path:
    lexical_path = Path(os.path.abspath(path))
    lexical_root = Path(os.path.abspath(root))
    try:
        return lexical_path.relative_to(lexical_root)
    except ValueError as exc:
        raise WorkspacePathError(
            f"{label} is outside the qualification disposable root",
            label=label,
        ) from exc


def _resolved_relative_to(path: Path, root: Path, *, label: str) -> Path:
    try:
        resolved_path = path.resolve(strict=True)
        resolved_root = root.resolve(strict=True)
        return resolved_path.relative_to(resolved_root)
    except (OSError, ValueError) as exc:
        raise WorkspacePathError(
            f"{label} is outside the qualification disposable root",
            label=label,
        ) from exc


def _clean_identity(identity: dict[str, object]) -> dict[str, str | int]:
    if not isinstance(identity, dict):
        raise WorkspaceError("workspace identity must be an object")
    cleaned: dict[str, str | int] = {}
    for field in IDENTITY_FIELDS:
        value = identity.get(field)
        if value is None:
            continue
        if field in {"repetition", "attempt"}:
            if type(value) is not int or value < 0 or value > 999:
                raise WorkspaceError(f"workspace identity {field} is invalid")
            cleaned[field] = value
            continue
        if not isinstance(value, str) or not IDENTITY_VALUE_RE.fullmatch(value):
            raise WorkspaceError(f"workspace identity {field} is invalid")
        cleaned[field] = value
    if "campaign" not in cleaned or "family" not in cleaned:
        raise WorkspaceError("workspace identity requires campaign and family")
    extra = sorted(set(identity) - set(IDENTITY_FIELDS))
    if extra:
        raise WorkspaceError("workspace identity has unsupported fields: " + ", ".join(extra))
    return cleaned


def workspace_id(identity: dict[str, object]) -> str:
    cleaned = _clean_identity(identity)
    encoded = json.dumps(
        cleaned,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")
    return "w" + hashlib.sha256(encoded).hexdigest()[:15]


def path_budget(
    base: Path,
    *,
    suffixes: dict[str, Path] | None = None,
    effective_limit: int | None = None,
    safety_margin: int = SAFETY_MARGIN,
) -> dict[str, Any]:
    limit = effective_limit or platform_path_limit()
    if limit < 80 or safety_margin < 1 or safety_margin >= limit:
        raise WorkspacePathError(
            "qualification path limit or safety margin is invalid",
            label="path_budget",
            allowed=limit,
        )
    allowed = limit - safety_margin
    inventory = suffixes or DEFAULT_SUFFIXES
    lengths = {
        label: _path_length(base / suffix)
        for label, suffix in sorted(inventory.items())
    }
    longest_label, longest = max(lengths.items(), key=lambda item: item[1])
    if longest > allowed:
        raise WorkspacePathError(
            f"qualification path budget exceeded for {longest_label}: "
            f"{longest} > {allowed}",
            label=longest_label,
            measured=longest,
            allowed=allowed,
        )
    return {
        "effective_limit": limit,
        "safety_margin": safety_margin,
        "allowed": allowed,
        "maximum": longest,
        "maximum_label": longest_label,
        "measurements": lengths,
    }


def validate_artifact_paths(
    paths: dict[str, Path],
    *,
    effective_limit: int | None = None,
    safety_margin: int = SAFETY_MARGIN,
) -> dict[str, Any]:
    limit = effective_limit or platform_path_limit()
    allowed = limit - safety_margin
    measurements = {label: _path_length(path) for label, path in sorted(paths.items())}
    longest_label, longest = max(measurements.items(), key=lambda item: item[1])
    if longest > allowed:
        raise WorkspacePathError(
            f"qualification artifact path budget exceeded for {longest_label}: "
            f"{longest} > {allowed}",
            label=longest_label,
            measured=longest,
            allowed=allowed,
        )
    return {
        "effective_limit": limit,
        "safety_margin": safety_margin,
        "allowed": allowed,
        "maximum": longest,
        "maximum_label": longest_label,
        "measurements": measurements,
    }


def _prepare_mapping_path(path: Path, artifact_root: Path) -> tuple[Path, Path]:
    artifact = Path(os.path.abspath(artifact_root))
    mapping = Path(os.path.abspath(path))
    _relative_to(mapping, artifact, label="workspace mapping")
    reject_linked_components(artifact, label="workspace mapping artifact root")
    reject_linked_components(mapping.parent, label="workspace mapping parent")
    mapping.parent.mkdir(parents=True, exist_ok=True)
    reject_linked_components(mapping.parent, label="workspace mapping parent")
    resolved_artifact = artifact.resolve(strict=True)
    resolved_parent = mapping.parent.resolve(strict=True)
    try:
        resolved_parent.relative_to(resolved_artifact)
    except ValueError as exc:
        raise WorkspacePathError(
            "workspace mapping parent resolves outside the artifact root",
            label="workspace_mapping_containment",
        ) from exc
    if mapping.exists() or mapping.is_symlink():
        metadata = mapping.lstat()
        if stat.S_ISLNK(metadata.st_mode) or _is_reparse(metadata):
            raise WorkspacePathError(
                "workspace mapping is a symlink, junction, or reparse point",
                label="workspace_mapping",
            )
        if not stat.S_ISREG(metadata.st_mode):
            raise WorkspacePathError(
                "workspace mapping is not a regular file",
                label="workspace_mapping",
            )
    return mapping, resolved_artifact


def _write_mapping(
    path: Path,
    payload: dict[str, Any],
    *,
    artifact_root: Path,
) -> None:
    mapping, resolved_artifact = _prepare_mapping_path(path, artifact_root)
    atomic_write_utf8(
        mapping,
        json.dumps(
            payload,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n",
    )
    reject_linked_components(mapping.parent, label="workspace mapping parent")
    resolved = mapping.resolve(strict=True)
    try:
        resolved.relative_to(resolved_artifact)
    except ValueError as exc:
        raise WorkspacePathError(
            "workspace mapping resolved outside the artifact root after publication",
            label="workspace_mapping_containment",
        ) from exc
    metadata = mapping.lstat()
    if not stat.S_ISREG(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode) or _is_reparse(metadata):
        raise WorkspacePathError(
            "workspace mapping publication is not a regular unlinked file",
            label="workspace_mapping",
        )


def _remove_readonly_entry(
    function: Callable[[str], object],
    path: str,
    error: tuple[type[BaseException], BaseException, object],
) -> None:
    """Retry deletion only for a read-only entry inside a validated workspace."""
    exception = error[1]
    if not isinstance(exception, PermissionError):
        raise exception
    os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
    function(path)


class WorkspaceLease:
    def __init__(
        self,
        *,
        path: Path,
        disposable_root: Path,
        artifact_root: Path,
        mapping_path: Path,
        identity: dict[str, str | int],
        budget: dict[str, Any],
    ) -> None:
        self.path = path
        self.disposable_root = disposable_root
        self.artifact_root = artifact_root
        self.mapping_path = mapping_path
        self.identity = identity
        self.budget = budget
        self.workspace_id = path.name
        self.cleaned = False

    def __enter__(self) -> "WorkspaceLease":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> bool:
        self.cleanup()
        return False

    def child(self, segment: str) -> Path:
        if not re.fullmatch(r"[a-z0-9]{1,8}", segment):
            raise WorkspaceError("workspace child segment must be 1-8 lowercase characters")
        child = self.path / segment
        path_budget(child)
        return child

    def mapping(self, status: str, error: str | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema_version": 1,
            "workspace_id": self.workspace_id,
            "root_alias": "qualification-disposable-root",
            "identity": self.identity,
            "path_budget": self.budget,
            "cleanup_status": status,
            "model_calls": 0,
        }
        if error:
            payload["cleanup_error"] = error
        return payload

    def cleanup(self, *, attempts: int = 40, delay_seconds: float = 0.25) -> None:
        """Remove the workspace after bounded retries for transient Windows handles."""
        if self.cleaned:
            return
        _relative_to(self.path, self.disposable_root, label="workspace cleanup")
        if self.path.exists() or self.path.is_symlink():
            _reject_link_or_reparse(self.path, label="workspace cleanup")
        last_error: OSError | None = None
        for attempt in range(attempts):
            try:
                if self.path.exists():
                    shutil.rmtree(self.path, onerror=_remove_readonly_entry)
                last_error = None
                break
            except OSError as exc:
                last_error = exc
                if attempt + 1 < attempts:
                    time.sleep(delay_seconds)
        if last_error is not None or self.path.exists():
            message = str(last_error or "workspace still exists after cleanup")
            _write_mapping(
                self.mapping_path,
                self.mapping("ERROR", message),
                artifact_root=self.artifact_root,
            )
            raise WorkspaceError(
                f"qualification workspace cleanup failed for {self.workspace_id}: {message}"
            )
        self.cleaned = True
        _write_mapping(
            self.mapping_path,
            self.mapping("CLEANED"),
            artifact_root=self.artifact_root,
        )
        if self in _REGISTERED:
            _REGISTERED.remove(self)


def allocate_workspace(
    *,
    artifact_root: Path,
    identity: dict[str, object],
    disposable_root: Path | None = None,
    mapping_path: Path | None = None,
    requested_path: Path | None = None,
    effective_limit: int | None = None,
) -> WorkspaceLease:
    cleaned = _clean_identity(identity)
    root = Path(os.path.abspath(disposable_root or default_disposable_root()))
    reject_linked_components(root, label="qualification disposable root")
    root.mkdir(parents=True, exist_ok=True)
    _reject_link_or_reparse(root, label="qualification disposable root")
    identifier = workspace_id(cleaned)
    expected = root / identifier
    path = Path(os.path.abspath(requested_path)) if requested_path is not None else expected
    _relative_to(path, root, label="qualification workspace")
    if requested_path is None and path != expected:
        raise WorkspacePathError(
            "qualification workspace differs from its deterministic identity",
            label="workspace_identity",
        )
    budget = path_budget(path, effective_limit=effective_limit)
    reject_linked_components(path.parent, label="qualification workspace parent")
    if path.exists() or path.is_symlink():
        _reject_link_or_reparse(path, label="qualification workspace")
        raise WorkspacePathError(
            "qualification workspace already exists",
            label="workspace_exists",
        )
    artifact = Path(os.path.abspath(artifact_root))
    reject_linked_components(artifact, label="workspace mapping artifact root")
    artifact.mkdir(parents=True, exist_ok=True)
    reject_linked_components(artifact, label="workspace mapping artifact root")
    mapping = mapping_path or artifact / f"workspace-{identifier}.json"
    mapping = Path(os.path.abspath(mapping))
    mapping, _ = _prepare_mapping_path(mapping, artifact)
    if mapping.exists() or mapping.is_symlink():
        raise WorkspacePathError(
            "qualification workspace mapping already exists",
            label="workspace_mapping_exists",
        )
    path.mkdir(parents=False, exist_ok=False)
    lease = WorkspaceLease(
        path=path,
        disposable_root=root,
        artifact_root=artifact,
        mapping_path=mapping,
        identity=cleaned,
        budget=budget,
    )
    try:
        _write_mapping(
            mapping,
            lease.mapping("ACTIVE"),
            artifact_root=artifact,
        )
    except BaseException:
        shutil.rmtree(path, ignore_errors=True)
        raise
    _REGISTERED.append(lease)
    return lease


def managed_workspace_root(path: Path, *, disposable_root: Path | None = None) -> Path:
    root = Path(os.path.abspath(disposable_root or default_disposable_root()))
    candidate = Path(os.path.abspath(path))
    reject_linked_components(root, label="qualification disposable root")
    reject_linked_components(candidate, label="managed qualification workspace")
    _resolved_relative_to(candidate, root, label="managed qualification workspace")
    if not candidate.is_dir():
        raise WorkspacePathError(
            "managed qualification workspace is not a directory",
            label="managed_workspace",
        )
    path_budget(candidate)
    return candidate.resolve(strict=True)


def allocate_probe_workspace(*, repository_root: Path, family: str) -> WorkspaceLease:
    global _PROBE_COUNTER
    _PROBE_COUNTER += 1
    campaign = f"p{os.getpid():x}{_PROBE_COUNTER:x}"
    artifact_root = repository_root / ".eval-runs" / "qualification-probes"
    return allocate_workspace(
        artifact_root=artifact_root,
        identity={"campaign": campaign, "family": family},
    )


def cleanup_registered() -> None:
    errors: list[str] = []
    for lease in list(reversed(_REGISTERED)):
        try:
            lease.cleanup()
        except WorkspaceError as exc:
            errors.append(str(exc))
    if errors:
        raise WorkspaceError(" | ".join(errors))


def run_with_cleanup(main: Callable[[], int]) -> int:
    result: int | None = None
    active_error: BaseException | None = None
    try:
        result = main()
    except BaseException as exc:
        active_error = exc
    try:
        cleanup_registered()
    except WorkspaceError as cleanup_error:
        if active_error is not None:
            raise WorkspaceError(
                f"{active_error} | cleanup failed: {cleanup_error}"
            ) from active_error
        raise
    if active_error is not None:
        raise active_error
    return int(result or 0)
