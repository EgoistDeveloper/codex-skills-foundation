#!/usr/bin/env python3
"""Build and verify one exact, unreleased plugin release candidate identity.

The deterministic candidate manifest deliberately contains no timestamp or
machine-specific path. Runtime qualification refers to the manifest by SHA-256
instead of placing volatile evidence inside the stable identity document.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import zipfile
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = 1
CREATION_CONTRACT = "b02-h04r-v1"
DEFAULT_REPOSITORY = "EgoistDeveloper/codex-skills-foundation"
DEFAULT_INTENDED_TAG = "v0.3.0-beta.2"
MANIFEST_FILENAME = "release-candidate.json"
CHECKSUM_FILENAME = "SHA256SUMS"
LIVE_CONTEXT_ENV = "ENGINEERING_FOUNDATION_CANDIDATE_CONTEXT"
VERIFIER_RUNNER_MEMBER = (
    "skills/verify-before-completion/scripts/run_verifier_with_receipt.py"
)
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
WINDOWS_REPARSE_POINT = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x0400)

EXPECTED_PACKAGE_HASHES = {
    "engineering-foundation-core": (
        "69444e865337c823312a6882b6373c9682e479f9c72a60a8f4a03f0bbeaae1a0"
    ),
    "engineering-foundation-laravel": (
        "64fb34691d66b7051c77c0a90058631ef7e0b308cd010878777642696d65a79c"
    ),
    "engineering-foundation-design": (
        "3f7d5f37d264e7aa1d2ab94dea12a62806e5cef1728225319845429a33a63296"
    ),
    "engineering-foundation-cloud": (
        "4fe88385d98e3ef2b36aa2b304b891c76db61db99f88480e211efb6b7a575982"
    ),
    "engineering-foundation-authoring": (
        "cbd7906aa03af50e850b253f4ecf17ced202b126f4fa33ba120036f5f196f07b"
    ),
}
BETA1_TAG_COMMIT = "474f946ab6d34dc05802551a6165e5007888b783"
BETA1_PACKAGE_HASHES = {
    "engineering-foundation-core-0.3.0-beta.1.zip": (
        "2eb3327e0a1288cdc55627a8feaa4315f39d59071de853b02ebe62bca1f1e0ac"
    ),
    "engineering-foundation-laravel-0.2.1.zip": EXPECTED_PACKAGE_HASHES[
        "engineering-foundation-laravel"
    ],
    "engineering-foundation-design-0.2.1.zip": EXPECTED_PACKAGE_HASHES[
        "engineering-foundation-design"
    ],
    "engineering-foundation-cloud-0.2.1.zip": EXPECTED_PACKAGE_HASHES[
        "engineering-foundation-cloud"
    ],
    "engineering-foundation-authoring-0.2.1.zip": EXPECTED_PACKAGE_HASHES[
        "engineering-foundation-authoring"
    ],
}


class CandidateError(RuntimeError):
    """Fail-closed release-candidate identity error."""


def failure_payload(operation: str, error: BaseException | str) -> dict[str, Any]:
    """Return the stable machine-readable failure shape for H04 entry points."""
    return {
        "schema_version": 1,
        "outcome": "FAIL",
        "operation": operation,
        "error": str(error),
    }


def canonical_json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(canonical_json_bytes(value))
    os.replace(temporary, path)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise CandidateError(f"cannot hash candidate artifact {path}: {exc}") from exc
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CandidateError(f"cannot read candidate JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise CandidateError(f"candidate JSON must contain an object: {path}")
    return value


def run_git(
    repository: Path,
    *args: str,
    expected: set[int] | None = None,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", *args],
        cwd=repository,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    expected_codes = expected or {0}
    if result.returncode not in expected_codes:
        detail = "\n".join(
            part.strip() for part in (result.stdout, result.stderr) if part.strip()
        )
        raise CandidateError(
            f"git {' '.join(args)} returned {result.returncode}; "
            f"expected {sorted(expected_codes)}{': ' + detail if detail else ''}"
        )
    return result


def git_text(repository: Path, *args: str) -> str:
    return run_git(repository, *args).stdout.strip()


def require_clean_commit(repository: Path, expected_commit: str) -> str:
    if not COMMIT_RE.fullmatch(expected_commit):
        raise CandidateError(f"expected commit is not a full Git SHA: {expected_commit!r}")
    branch = git_text(repository, "symbolic-ref", "--quiet", "--short", "HEAD")
    if not branch:
        raise CandidateError("candidate subject commit is detached or ambiguous")
    head = git_text(repository, "rev-parse", "HEAD")
    if head != expected_commit:
        raise CandidateError(
            f"candidate commit mismatch: HEAD={head}, expected={expected_commit}"
        )
    status = git_text(repository, "status", "--porcelain", "--untracked-files=all")
    if status:
        raise CandidateError(f"candidate source tree is dirty:\n{status}")
    return head


def require_tag_compatible(
    repository: Path,
    intended_tag: str,
    expected_commit: str,
) -> None:
    if not intended_tag or any(character.isspace() for character in intended_tag):
        raise CandidateError(f"invalid intended release tag: {intended_tag!r}")
    result = run_git(
        repository,
        "rev-parse",
        "--verify",
        f"refs/tags/{intended_tag}^{{commit}}",
        expected={0, 128},
    )
    if result.returncode == 0:
        target = result.stdout.strip()
        if target != expected_commit:
            raise CandidateError(
                f"intended tag {intended_tag} targets commit {target}, "
                f"not candidate commit {expected_commit}"
            )


def validate_relative_name(value: str, *, label: str) -> None:
    posix = PurePosixPath(value)
    windows = PureWindowsPath(value)
    if (
        not value
        or posix.is_absolute()
        or windows.is_absolute()
        or windows.drive
        or ".." in posix.parts
        or ".." in windows.parts
        or "\\" in value
    ):
        raise CandidateError(f"unsafe {label}: {value!r}")


def load_catalog(repository: Path) -> dict[str, Any]:
    path = repository / "catalog/plugins.json"
    catalog = load_json(path)
    plugins = catalog.get("plugins")
    if not isinstance(plugins, list) or not plugins:
        raise CandidateError("catalog/plugins.json contains no plugin inventory")
    return catalog


def catalog_plugins(catalog: dict[str, Any]) -> list[dict[str, Any]]:
    plugins = catalog.get("plugins")
    if not isinstance(plugins, list):
        raise CandidateError("candidate catalog plugins field is invalid")
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in plugins:
        if not isinstance(item, dict):
            raise CandidateError("candidate catalog contains a non-object plugin")
        name = item.get("name")
        version = item.get("version")
        path = item.get("path")
        if not all(isinstance(value, str) and value for value in (name, version, path)):
            raise CandidateError("candidate catalog plugin has invalid name/version/path")
        if name in seen:
            raise CandidateError(f"candidate catalog contains duplicate plugin {name}")
        validate_relative_name(path, label="catalog plugin path")
        seen.add(name)
        result.append(item)
    return result


def validate_provider_marketplaces(
    repository: Path,
    catalog: dict[str, Any],
    plugins: list[dict[str, Any]],
) -> tuple[Path, Path]:
    marketplace = catalog.get("marketplace")
    marketplace_name = marketplace.get("name") if isinstance(marketplace, dict) else None
    if not isinstance(marketplace_name, str) or not marketplace_name:
        raise CandidateError("catalog marketplace name is invalid")
    expected = {
        str(plugin["name"]): {
            "version": str(plugin["version"]),
            "source": f"./{plugin['path']}",
        }
        for plugin in plugins
    }
    openai_path = repository / ".agents/plugins/marketplace.json"
    claude_path = repository / ".claude-plugin/marketplace.json"
    openai = load_json(openai_path)
    claude = load_json(claude_path)
    if openai.get("name") != marketplace_name:
        raise CandidateError("OpenAI marketplace name differs from catalog")
    if claude.get("name") != marketplace_name:
        raise CandidateError("Claude marketplace name differs from catalog")
    openai_rows = openai.get("plugins")
    claude_rows = claude.get("plugins")
    if not isinstance(openai_rows, list) or not isinstance(claude_rows, list):
        raise CandidateError("provider marketplace plugin inventory is invalid")

    def unique_rows(rows: list[Any], provider: str) -> dict[str, dict[str, Any]]:
        result: dict[str, dict[str, Any]] = {}
        for row in rows:
            if not isinstance(row, dict) or not isinstance(row.get("name"), str):
                raise CandidateError(f"{provider} marketplace contains an invalid plugin row")
            name = str(row["name"])
            if name in result:
                raise CandidateError(f"{provider} marketplace contains duplicate plugin {name}")
            result[name] = row
        if set(result) != set(expected):
            raise CandidateError(
                f"{provider} marketplace package inventory differs from catalog"
            )
        return result

    openai_by_name = unique_rows(openai_rows, "OpenAI")
    claude_by_name = unique_rows(claude_rows, "Claude")
    for name, identity in expected.items():
        source = openai_by_name[name].get("source")
        if (
            not isinstance(source, dict)
            or source.get("source") != "local"
            or source.get("path") != identity["source"]
        ):
            raise CandidateError(f"OpenAI marketplace source differs for {name}")
        claude_row = claude_by_name[name]
        if claude_row.get("source") != identity["source"]:
            raise CandidateError(f"Claude marketplace source differs for {name}")
        if claude_row.get("version") != identity["version"]:
            raise CandidateError(f"Claude marketplace version differs for {name}")
    return openai_path, claude_path


def archive_filename(plugin: dict[str, Any]) -> str:
    filename = f"{plugin['name']}-{plugin['version']}.zip"
    validate_relative_name(filename, label="archive filename")
    return filename


def _zip_member_mode(info: zipfile.ZipInfo) -> int:
    return (info.external_attr >> 16) & 0xFFFF


def inspect_archive(
    archive_path: Path,
    *,
    expected_name: str,
    expected_version: str,
) -> dict[str, Any]:
    members: list[tuple[str, bytes]] = []
    try:
        with zipfile.ZipFile(archive_path, "r") as archive:
            infos = archive.infolist()
            names = [info.filename for info in infos]
            if len(names) != len(set(names)):
                raise CandidateError(f"archive contains duplicate members: {archive_path.name}")
            for info in infos:
                validate_relative_name(info.filename, label="archive member")
                mode = _zip_member_mode(info)
                if stat.S_ISLNK(mode):
                    raise CandidateError(
                        f"archive contains a linked member: {archive_path.name}:{info.filename}"
                    )
                if info.is_dir():
                    raise CandidateError(
                        f"archive contains an unexpected directory entry: "
                        f"{archive_path.name}:{info.filename}"
                    )
                members.append((info.filename, archive.read(info)))
    except (OSError, zipfile.BadZipFile) as exc:
        raise CandidateError(f"cannot inspect candidate archive {archive_path}: {exc}") from exc

    by_name = dict(members)
    required = {"plugin.json", ".codex-plugin/plugin.json", ".claude-plugin/plugin.json"}
    missing = required - set(by_name)
    if missing:
        raise CandidateError(
            f"candidate archive {archive_path.name} is missing manifests: {sorted(missing)}"
        )
    manifest_members = {
        "root": "plugin.json",
        "codex": ".codex-plugin/plugin.json",
        "claude": ".claude-plugin/plugin.json",
    }
    manifest_hashes: dict[str, str] = {}
    for provider, member in manifest_members.items():
        try:
            plugin = json.loads(by_name[member].decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise CandidateError(
                f"invalid embedded {provider} plugin manifest in {archive_path.name}"
            ) from exc
        if not isinstance(plugin, dict):
            raise CandidateError(
                f"embedded {provider} plugin manifest is not an object: "
                f"{archive_path.name}"
            )
        if plugin.get("name") != expected_name:
            raise CandidateError(
                f"archive/{provider} manifest name mismatch for {archive_path.name}: "
                f"{plugin.get('name')!r}"
            )
        if plugin.get("version") != expected_version:
            raise CandidateError(
                f"archive/{provider} manifest version mismatch for {archive_path.name}: "
                f"{plugin.get('version')!r} != {expected_version!r}"
            )
        manifest_hashes[provider] = sha256_bytes(by_name[member])
    skill_count = sum(
        1
        for name, _ in members
        if len(PurePosixPath(name).parts) == 3
        and PurePosixPath(name).parts[0] == "skills"
        and PurePosixPath(name).name == "SKILL.md"
    )
    if skill_count < 1:
        raise CandidateError(f"candidate archive contains no skill: {archive_path.name}")
    content_digest = hashlib.sha256()
    for name, data in sorted(members):
        encoded = name.encode("utf-8")
        content_digest.update(len(encoded).to_bytes(4, "big"))
        content_digest.update(encoded)
        content_digest.update(len(data).to_bytes(8, "big"))
        content_digest.update(hashlib.sha256(data).digest())
    return {
        "skill_count": skill_count,
        "content_sha256": content_digest.hexdigest(),
        "plugin_manifest_sha256": manifest_hashes["root"],
        "provider_manifest_sha256": {
            "codex": manifest_hashes["codex"],
            "claude": manifest_hashes["claude"],
        },
        "members": [name for name, _ in sorted(members)],
    }


def archive_member_sha256(archive_path: Path, member_name: str) -> str:
    """Hash one exact regular ZIP member, rejecting absence or duplication."""
    validate_relative_name(member_name, label="archive member")
    try:
        with zipfile.ZipFile(archive_path, "r") as archive:
            matches = [
                info for info in archive.infolist() if info.filename == member_name
            ]
            if len(matches) != 1:
                raise CandidateError(
                    f"archive must contain exactly one {member_name}: {archive_path.name}"
                )
            info = matches[0]
            if info.is_dir() or stat.S_ISLNK(_zip_member_mode(info)):
                raise CandidateError(
                    f"archive verifier runner is not a regular file: {archive_path.name}"
                )
            return sha256_bytes(archive.read(info))
    except (OSError, zipfile.BadZipFile) as exc:
        raise CandidateError(
            f"cannot inspect candidate archive member {archive_path}: {exc}"
        ) from exc


def expected_checksum_bytes(packages: list[dict[str, Any]]) -> bytes:
    return "".join(
        f"{package['sha256']}  {package['archive_filename']}\n"
        for package in packages
    ).encode("utf-8")


def _production_hashes_for(repository_name: str) -> dict[str, str] | None:
    return EXPECTED_PACKAGE_HASHES if repository_name == DEFAULT_REPOSITORY else None


def create_candidate_manifest(
    *,
    repository: Path,
    artifact_dir: Path,
    intended_tag: str,
    expected_commit: str,
    expected_repository: str,
    expected_hashes: dict[str, str] | None = None,
) -> dict[str, Any]:
    repository = repository.resolve(strict=True)
    artifact_dir = artifact_dir.resolve(strict=True)
    require_clean_commit(repository, expected_commit)
    require_tag_compatible(repository, intended_tag, expected_commit)
    catalog_path = repository / "catalog/plugins.json"
    catalog = load_catalog(repository)
    plugins = catalog_plugins(catalog)
    openai_marketplace, claude_marketplace = validate_provider_marketplaces(
        repository, catalog, plugins
    )
    if expected_repository == DEFAULT_REPOSITORY:
        if intended_tag != DEFAULT_INTENDED_TAG:
            raise CandidateError(
                f"wrong intended release tag: {intended_tag!r}; "
                f"expected {DEFAULT_INTENDED_TAG!r}"
            )
        actual_names = {str(plugin["name"]) for plugin in plugins}
        expected_names = set(EXPECTED_PACKAGE_HASHES)
        if actual_names != expected_names:
            raise CandidateError(
                "production candidate package inventory differs: "
                f"actual={sorted(actual_names)}, expected={sorted(expected_names)}"
            )
    marketplace = catalog.get("marketplace")
    if not isinstance(marketplace, dict):
        raise CandidateError("catalog marketplace identity is invalid")
    repository_url = marketplace.get("repository")
    expected_repository_url = f"https://github.com/{expected_repository}"
    if (
        not isinstance(repository_url, str)
        or repository_url.rstrip("/") != expected_repository_url
    ):
        raise CandidateError(
            f"catalog repository identity {repository_url!r} does not match "
            f"{expected_repository_url!r}"
        )

    allowed = {CHECKSUM_FILENAME, MANIFEST_FILENAME}
    allowed.update(archive_filename(plugin) for plugin in plugins)
    actual_release_files = {
        path.name
        for path in artifact_dir.iterdir()
        if path.is_file() and (path.suffix == ".zip" or path.name in {CHECKSUM_FILENAME, MANIFEST_FILENAME})
    }
    unexpected = actual_release_files - allowed
    if unexpected:
        raise CandidateError(f"unexpected candidate artifact: {sorted(unexpected)}")

    hashes = expected_hashes
    if hashes is None:
        hashes = _production_hashes_for(expected_repository)
    package_rows: list[dict[str, Any]] = []
    for plugin in plugins:
        name = str(plugin["name"])
        version = str(plugin["version"])
        filename = archive_filename(plugin)
        archive = artifact_dir / filename
        if not archive.exists():
            raise CandidateError(f"missing expected candidate archive: {filename}")
        _require_regular_artifact(archive, artifact_dir, label="candidate archive")
        digest = sha256_file(archive)
        if hashes is not None:
            expected_digest = hashes.get(name)
            if expected_digest is None:
                raise CandidateError(f"no expected digest is defined for package {name}")
            if digest != expected_digest:
                raise CandidateError(
                    f"candidate archive digest mismatch for {filename}: "
                    f"{digest} != {expected_digest}"
                )
        inspected = inspect_archive(
            archive,
            expected_name=name,
            expected_version=version,
        )
        source_plugin_manifest = repository / str(plugin["path"]) / "plugin.json"
        if not source_plugin_manifest.is_file():
            raise CandidateError(f"source plugin manifest is missing: {source_plugin_manifest}")
        if inspected["plugin_manifest_sha256"] != sha256_file(source_plugin_manifest):
            raise CandidateError(
                f"archive plugin manifest differs from source for package {name}"
            )
        provider_sources = {
            "codex": repository / str(plugin["path"]) / ".codex-plugin/plugin.json",
            "claude": repository / str(plugin["path"]) / ".claude-plugin/plugin.json",
        }
        for provider, source in provider_sources.items():
            if not source.is_file():
                raise CandidateError(
                    f"source {provider} plugin manifest is missing: {source}"
                )
            if inspected["provider_manifest_sha256"][provider] != sha256_file(source):
                raise CandidateError(
                    f"archive {provider} plugin manifest differs from source for {name}"
                )
        package_rows.append(
            {
                "name": name,
                "version": version,
                "archive_filename": filename,
                "sha256": digest,
                "size_bytes": archive.stat().st_size,
                "skill_count": inspected["skill_count"],
                "content_sha256": inspected["content_sha256"],
                "plugin_manifest_sha256": inspected["plugin_manifest_sha256"],
                "provider_manifest_sha256": inspected[
                    "provider_manifest_sha256"
                ],
                "verifier_runner_sha256": (
                    archive_member_sha256(archive, VERIFIER_RUNNER_MEMBER)
                    if name == "engineering-foundation-core"
                    else None
                ),
            }
        )

    checksum_path = artifact_dir / CHECKSUM_FILENAME
    if not checksum_path.exists():
        raise CandidateError(f"missing expected candidate artifact: {CHECKSUM_FILENAME}")
    _require_regular_artifact(
        checksum_path, artifact_dir, label="candidate checksum manifest"
    )
    expected_sums = expected_checksum_bytes(package_rows)
    actual_sums = checksum_path.read_bytes()
    if actual_sums != expected_sums:
        raise CandidateError("SHA256SUMS does not exactly match candidate package inventory")

    core = [row for row in package_rows if row["name"] == "engineering-foundation-core"]
    release_version = core[0]["version"] if core else package_rows[0]["version"]
    return {
        "schema_version": SCHEMA_VERSION,
        "repository": expected_repository,
        "subject_commit_sha": expected_commit,
        "intended_release_tag": intended_tag,
        "release_version": release_version,
        "candidate_state": "UNRELEASED",
        "creation_contract": CREATION_CONTRACT,
        "catalog_sha256": sha256_file(catalog_path),
        "marketplace_identity": {
            "openai_sha256": sha256_file(openai_marketplace),
            "claude_sha256": sha256_file(claude_marketplace),
        },
        "packages": package_rows,
        "checksums": {
            "filename": CHECKSUM_FILENAME,
            "sha256": sha256_file(checksum_path),
            "size_bytes": checksum_path.stat().st_size,
        },
    }


def _require_manifest_shape(manifest: dict[str, Any]) -> None:
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise CandidateError("candidate manifest schema_version is unsupported")
    if manifest.get("candidate_state") != "UNRELEASED":
        raise CandidateError("candidate manifest must remain UNRELEASED")
    if manifest.get("creation_contract") != CREATION_CONTRACT:
        raise CandidateError("candidate manifest creation contract is unsupported")
    if not COMMIT_RE.fullmatch(str(manifest.get("subject_commit_sha", ""))):
        raise CandidateError("candidate manifest subject commit is invalid")
    packages = manifest.get("packages")
    if not isinstance(packages, list) or not packages:
        raise CandidateError("candidate manifest package inventory is invalid")
    required_package = {
        "name",
        "version",
        "archive_filename",
        "sha256",
        "size_bytes",
        "skill_count",
        "content_sha256",
        "plugin_manifest_sha256",
        "provider_manifest_sha256",
        "verifier_runner_sha256",
    }
    names: set[str] = set()
    for package in packages:
        if not isinstance(package, dict) or set(package) != required_package:
            raise CandidateError("candidate manifest package row has invalid fields")
        if package["name"] in names:
            raise CandidateError("candidate manifest contains a duplicate package")
        names.add(str(package["name"]))
        validate_relative_name(str(package["archive_filename"]), label="archive filename")
        for field in ("sha256", "content_sha256", "plugin_manifest_sha256"):
            if not SHA256_RE.fullmatch(str(package[field])):
                raise CandidateError(f"candidate manifest {field} is invalid")
        provider_hashes = package["provider_manifest_sha256"]
        if not isinstance(provider_hashes, dict) or set(provider_hashes) != {
            "codex",
            "claude",
        }:
            raise CandidateError("candidate manifest provider hashes are invalid")
        for digest in provider_hashes.values():
            if not SHA256_RE.fullmatch(str(digest)):
                raise CandidateError("candidate manifest provider hash is invalid")
        runner_digest = package["verifier_runner_sha256"]
        if package["name"] == "engineering-foundation-core":
            if not SHA256_RE.fullmatch(str(runner_digest)):
                raise CandidateError("candidate manifest verifier runner hash is invalid")
        elif runner_digest is not None:
            raise CandidateError("optional package declares a verifier runner hash")


def verify_candidate_manifest(
    manifest_path: Path,
    artifact_dir: Path,
    *,
    repository: Path | None = None,
    expected_commit: str | None = None,
) -> dict[str, Any]:
    artifact_dir = artifact_dir.resolve(strict=True)
    _require_regular_artifact(
        manifest_path, artifact_dir, label="candidate manifest"
    )
    manifest_path = manifest_path.resolve(strict=True)
    manifest = load_json(manifest_path)
    _require_manifest_shape(manifest)
    subject_commit = str(manifest["subject_commit_sha"])
    if expected_commit is not None and subject_commit != expected_commit:
        raise CandidateError(
            f"candidate manifest is stale: subject commit {subject_commit} "
            f"!= expected commit {expected_commit}"
        )
    if repository is None:
        repository = ROOT
    repository = repository.resolve(strict=True)
    require_clean_commit(repository, expected_commit or subject_commit)
    catalog_versions = {
        str(plugin["name"]): str(plugin["version"])
        for plugin in catalog_plugins(load_catalog(repository))
    }
    for package in manifest["packages"]:
        name = str(package["name"])
        version = str(package["version"])
        if catalog_versions.get(name) != version:
            raise CandidateError(
                f"candidate package version mismatch for {name}: "
                f"{version!r} != {catalog_versions.get(name)!r}"
            )
        if package["archive_filename"] != f"{name}-{version}.zip":
            raise CandidateError(f"candidate archive filename/version mismatch for {name}")
    rebuilt = create_candidate_manifest(
        repository=repository,
        artifact_dir=artifact_dir,
        intended_tag=str(manifest.get("intended_release_tag", "")),
        expected_commit=subject_commit,
        expected_repository=str(manifest.get("repository", "")),
        expected_hashes=(
            _production_hashes_for(str(manifest.get("repository")))
            or {
                str(package["name"]): str(package["sha256"])
                for package in manifest["packages"]
            }
        ),
    )
    if rebuilt != manifest:
        for key in sorted(set(rebuilt) | set(manifest)):
            if rebuilt.get(key) != manifest.get(key):
                raise CandidateError(f"candidate manifest tampering or drift in field {key}")
        raise CandidateError("candidate manifest tampering or drift")
    return manifest


def core_package(manifest: dict[str, Any]) -> dict[str, Any]:
    matches = [
        package
        for package in manifest.get("packages", [])
        if isinstance(package, dict)
        and package.get("name") == "engineering-foundation-core"
    ]
    if len(matches) == 1:
        return matches[0]
    if len(manifest.get("packages", [])) == 1:
        return manifest["packages"][0]
    raise CandidateError("candidate manifest Core package identity is ambiguous")


def verify_lifecycle_evidence(
    manifest: dict[str, Any], evidence: dict[str, Any]
) -> None:
    if evidence.get("outcome") != "PASS":
        raise CandidateError("lifecycle outcome is not PASS")
    expected_manifest_sha256 = sha256_bytes(canonical_json_bytes(manifest))
    if evidence.get("candidate_manifest_sha256") != expected_manifest_sha256:
        raise CandidateError("lifecycle candidate manifest SHA-256 differs")
    if evidence.get("artifact_source") != "exact_archive":
        raise CandidateError("lifecycle did not use the exact artifact set")
    if evidence.get("subject_commit_sha") != manifest.get("subject_commit_sha"):
        raise CandidateError("lifecycle subject commit differs from candidate manifest")
    if evidence.get("model_calls") != 0:
        raise CandidateError("lifecycle must record zero model calls")
    if evidence.get("state_restored") is not True:
        raise CandidateError("lifecycle state restoration did not pass")
    if evidence.get("loopback_only") is not True:
        raise CandidateError("lifecycle was not loopback-only")
    if evidence.get("isolated_config_clean") is not True:
        raise CandidateError("lifecycle isolated configuration was not clean")
    if evidence.get("installed_plugins_remaining") != []:
        raise CandidateError("lifecycle left installed candidate plugins")
    if evidence.get("marketplace_remaining") is not False:
        raise CandidateError("lifecycle left the candidate marketplace configured")
    actual_hashes = evidence.get("package_sha256")
    expected_hashes = {
        package["name"]: package["sha256"] for package in manifest["packages"]
    }
    if actual_hashes != expected_hashes:
        raise CandidateError("lifecycle exact package SHA-256 inventory differs")
    actual_content = evidence.get("installed_content_sha256")
    expected_content = {
        package["name"]: package["content_sha256"]
        for package in manifest["packages"]
    }
    if actual_content != expected_content:
        raise CandidateError("lifecycle installed content SHA-256 inventory differs")
    expected_runner = core_package(manifest).get("verifier_runner_sha256")
    if evidence.get("installed_verifier_runner_sha256") != expected_runner:
        raise CandidateError("lifecycle installed verifier runner SHA-256 differs")


def verify_installed_plugin(
    manifest: dict[str, Any],
    *,
    plugin_name: str,
    installed_version: str,
    installed_root: Path,
) -> None:
    matches = [
        package
        for package in manifest.get("packages", [])
        if isinstance(package, dict) and package.get("name") == plugin_name
    ]
    if len(matches) != 1:
        raise CandidateError(f"installed plugin identity is ambiguous: {plugin_name}")
    package = matches[0]
    if installed_version != package.get("version"):
        raise CandidateError(
            f"installed plugin version mismatch for {plugin_name}: "
            f"{installed_version!r} != {package.get('version')!r}"
        )
    digest = directory_content_sha256(installed_root)
    if digest != package.get("content_sha256"):
        raise CandidateError(
            f"installed plugin content mismatch for {plugin_name}"
        )


def verify_live_row(
    manifest: dict[str, Any],
    row: dict[str, Any],
    candidate_manifest_sha256: str,
) -> None:
    if row.get("variant") != "candidate":
        return
    core = core_package(manifest)
    if row.get("candidate_repository") != manifest.get("repository"):
        raise CandidateError("live row repository differs from candidate")
    if row.get("subject_commit") != manifest.get("subject_commit_sha"):
        raise CandidateError("live row subject commit differs from candidate")
    if row.get("subject_version") != core.get("version"):
        raise CandidateError("live row subject version differs from candidate")
    if row.get("candidate_manifest_sha256") != candidate_manifest_sha256:
        raise CandidateError("live row candidate manifest SHA-256 differs")
    package_digest = row.get("package_sha256")
    if package_digest is None:
        raise CandidateError("live row package sha256 is required")
    if package_digest != core.get("sha256"):
        raise CandidateError("live row package sha256 differs from candidate")
    if row.get("case_id") == "required-evidence-refusal":
        for field in (
            "verifier_receipt_run_id",
            "verifier_receipt_command_id",
            "verifier_receipt_payload_sha256",
            "verifier_receipt_event_id",
        ):
            value = row.get(field)
            if not isinstance(value, str) or not value:
                raise CandidateError(
                    f"evidence-refusal live row omitted {field}"
                )
        if not SHA256_RE.fullmatch(
            str(row.get("verifier_receipt_payload_sha256"))
        ):
            raise CandidateError(
                "evidence-refusal live row receipt payload SHA-256 is invalid"
            )


def verify_live_rows(
    manifest: dict[str, Any],
    rows: Iterable[dict[str, Any]],
    candidate_manifest_sha256: str,
) -> None:
    candidate_rows = [row for row in rows if row.get("variant") == "candidate"]
    stable_fields = (
        "candidate_repository",
        "provider",
        "client",
        "client_version",
        "harness_commit",
    )
    for field in stable_fields:
        values = {str(row.get(field)) for row in candidate_rows if row.get(field)}
        if len(values) != 1 or any(not row.get(field) for row in candidate_rows):
            raise CandidateError(f"live evidence has mixed or missing {field} identity")
    observed_manifest_hashes = {
        str(row.get("candidate_manifest_sha256")) for row in candidate_rows
    }
    if len(observed_manifest_hashes) > 1:
        raise CandidateError("mixed candidate manifests were combined in live evidence")
    count = 0
    for row in candidate_rows:
        count += 1
        verify_live_row(manifest, row, candidate_manifest_sha256)
    if count == 0:
        raise CandidateError("live evidence contains no candidate rows")
    if observed_manifest_hashes != {candidate_manifest_sha256}:
        raise CandidateError("mixed candidate manifests were combined in live evidence")


def verify_release_assets(
    manifest: dict[str, Any],
    asset_dir: Path,
    *,
    repository: str,
    tag: str,
    tag_target: str,
    prerelease: bool,
    source_repository: Path,
    expected_manifest_sha256: str,
) -> None:
    _require_manifest_shape(manifest)
    if not SHA256_RE.fullmatch(expected_manifest_sha256):
        raise CandidateError("expected frozen candidate manifest SHA-256 is invalid")
    _reject_link_or_reparse(asset_dir)
    asset_dir = asset_dir.resolve(strict=True)
    if repository != manifest.get("repository"):
        raise CandidateError("release repository identity differs from candidate")
    if tag != manifest.get("intended_release_tag"):
        raise CandidateError("release tag differs from intended candidate tag")
    if tag_target != manifest.get("subject_commit_sha"):
        raise CandidateError("release tag target commit differs from candidate")
    if prerelease is not True:
        raise CandidateError("candidate release must remain a prerelease")
    actual_manifest_sha256 = sha256_bytes(canonical_json_bytes(manifest))
    if actual_manifest_sha256 != expected_manifest_sha256:
        raise CandidateError(
            "release candidate manifest differs from the independently frozen digest"
        )
    expected = {
        str(package["archive_filename"]) for package in manifest["packages"]
    } | {CHECKSUM_FILENAME, MANIFEST_FILENAME}
    entries = list(asset_dir.iterdir())
    for path in entries:
        _require_regular_artifact(path, asset_dir, label="release asset")
    actual = {path.name for path in entries}
    missing = expected - actual
    unexpected = actual - expected
    if missing:
        raise CandidateError(f"missing expected release asset: {sorted(missing)}")
    if unexpected:
        raise CandidateError(f"unexpected release asset: {sorted(unexpected)}")
    for package in manifest["packages"]:
        archive = asset_dir / str(package["archive_filename"])
        if sha256_file(archive) != package["sha256"]:
            raise CandidateError(f"release asset digest mismatch: {archive.name}")
        if archive.stat().st_size != package["size_bytes"]:
            raise CandidateError(f"release asset size mismatch: {archive.name}")
        inspect_archive(
            archive,
            expected_name=str(package["name"]),
            expected_version=str(package["version"]),
        )
    sums = asset_dir / CHECKSUM_FILENAME
    if sums.read_bytes() != expected_checksum_bytes(manifest["packages"]):
        raise CandidateError("release SHA256SUMS differs from candidate inventory")
    if sha256_file(sums) != manifest["checksums"]["sha256"]:
        raise CandidateError("release SHA256SUMS digest differs from candidate")
    candidate_asset = asset_dir / MANIFEST_FILENAME
    if candidate_asset.read_bytes() != canonical_json_bytes(manifest):
        raise CandidateError("release candidate manifest asset differs from qualified manifest")
    verified = verify_candidate_manifest(
        candidate_asset,
        asset_dir,
        repository=source_repository,
        expected_commit=tag_target,
    )
    if verified != manifest:
        raise CandidateError("release candidate manifest differs from tagged source identity")


def verify_legacy_beta1_assets(
    asset_dir: Path,
    *,
    repository: str,
    tag: str,
    tag_target: str,
    prerelease: bool,
) -> None:
    _reject_link_or_reparse(asset_dir)
    asset_dir = asset_dir.resolve(strict=True)
    if repository != DEFAULT_REPOSITORY:
        raise CandidateError("beta.1 release repository identity differs")
    if tag != "v0.3.0-beta.1" or tag_target != BETA1_TAG_COMMIT:
        raise CandidateError("beta.1 immutable tag/commit identity differs")
    if prerelease is not True:
        raise CandidateError("beta.1 release is no longer marked prerelease")
    expected = set(BETA1_PACKAGE_HASHES) | {CHECKSUM_FILENAME}
    entries = list(asset_dir.iterdir())
    for path in entries:
        _require_regular_artifact(path, asset_dir, label="beta.1 release asset")
    actual = {path.name for path in entries}
    if actual != expected:
        raise CandidateError(
            f"beta.1 release asset inventory differs: actual={sorted(actual)}"
        )
    for filename, digest in BETA1_PACKAGE_HASHES.items():
        if sha256_file(asset_dir / filename) != digest:
            raise CandidateError(f"beta.1 immutable asset digest differs: {filename}")
    expected_sums = "".join(
        f"{digest}  {filename}\n"
        for filename, digest in BETA1_PACKAGE_HASHES.items()
    ).encode("utf-8")
    if (asset_dir / CHECKSUM_FILENAME).read_bytes() != expected_sums:
        raise CandidateError("beta.1 SHA256SUMS differs from immutable history")


def validate_shareable_provenance(value: object) -> None:
    forbidden_key_fragments = {
        "token",
        "secret",
        "credential",
        "authorization",
        "auth_material",
    }

    def walk(item: object, trail: tuple[str, ...] = ()) -> None:
        if isinstance(item, dict):
            for key, child in item.items():
                normalized = str(key).lower()
                if any(fragment in normalized for fragment in forbidden_key_fragments):
                    raise CandidateError(
                        f"shareable provenance contains credential field: {'.'.join((*trail, str(key)))}"
                    )
                walk(child, (*trail, str(key)))
            return
        if isinstance(item, list):
            for index, child in enumerate(item):
                walk(child, (*trail, str(index)))
            return
        if not isinstance(item, str):
            return
        windows = PureWindowsPath(item)
        posix = PurePosixPath(item)
        if windows.is_absolute() or windows.drive or posix.is_absolute():
            raise CandidateError(
                f"shareable provenance contains an absolute path at {'.'.join(trail)}"
            )

    walk(value)


def verify_bounded_artifact(path: Path, run_root: Path) -> str:
    resolved = _require_path_under(path, run_root, label="evidence artifact")
    if not resolved.is_file():
        raise CandidateError(f"evidence artifact is not a regular file: {resolved}")
    return resolved.relative_to(run_root.resolve(strict=True)).as_posix()


def regular_file_sha256(path: Path, root: Path, *, label: str) -> str:
    """Hash one unchanged, unlinked regular file below an exact root."""
    lexical_root = Path(os.path.abspath(root))
    lexical_path = Path(os.path.abspath(path))
    try:
        relative = lexical_path.relative_to(lexical_root)
    except ValueError as exc:
        raise CandidateError(f"{label} escapes its artifact directory: {path}") from exc

    for component in reversed((lexical_root, *lexical_root.parents)):
        _reject_link_or_reparse(component)
    current = lexical_root
    for part in relative.parts:
        current /= part
        _reject_link_or_reparse(current)

    resolved_root = lexical_root.resolve(strict=True)
    resolved = _require_regular_artifact(lexical_path, resolved_root, label=label)
    before = resolved.stat()
    digest = sha256_file(resolved)
    current_file = _require_regular_artifact(lexical_path, resolved_root, label=label)
    after = current_file.stat()
    if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
        after.st_dev,
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
    ):
        raise CandidateError(f"{label} changed while being hashed: {path}")
    return digest


def _reject_link_or_reparse(path: Path) -> None:
    metadata = path.lstat()
    if stat.S_ISLNK(metadata.st_mode) or (
        getattr(metadata, "st_file_attributes", 0) & WINDOWS_REPARSE_POINT
    ):
        raise CandidateError(f"linked runtime path is not allowed: {path}")


def _require_regular_artifact(path: Path, root: Path, *, label: str) -> Path:
    try:
        _reject_link_or_reparse(path)
        metadata = path.lstat()
        if not stat.S_ISREG(metadata.st_mode):
            raise CandidateError(f"{label} is not a regular file: {path}")
        resolved = path.resolve(strict=True)
        resolved.relative_to(root.resolve(strict=True))
    except ValueError as exc:
        raise CandidateError(f"{label} escapes its artifact directory: {path}") from exc
    except OSError as exc:
        raise CandidateError(f"cannot inspect {label} {path}: {exc}") from exc
    return resolved


def extract_archive_exact(archive_path: Path, destination: Path) -> None:
    if destination.exists():
        raise CandidateError(f"candidate extraction destination already exists: {destination}")
    destination.mkdir(parents=True)
    root = destination.resolve(strict=True)
    try:
        with zipfile.ZipFile(archive_path, "r") as archive:
            for info in archive.infolist():
                validate_relative_name(info.filename, label="archive member")
                target = destination.joinpath(*PurePosixPath(info.filename).parts)
                resolved_parent = target.parent.resolve(strict=False)
                try:
                    resolved_parent.relative_to(root)
                except ValueError as exc:
                    raise CandidateError(
                        f"candidate archive member escapes extraction root: {info.filename}"
                    ) from exc
                mode = _zip_member_mode(info)
                if info.is_dir() or stat.S_ISLNK(mode):
                    raise CandidateError(
                        f"unsupported candidate archive member: {info.filename}"
                    )
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(info, "r") as source, target.open("xb") as output:
                    while chunk := source.read(1024 * 1024):
                        output.write(chunk)
    except (OSError, zipfile.BadZipFile) as exc:
        raise CandidateError(f"cannot extract candidate archive {archive_path}: {exc}") from exc


def directory_content_sha256(root: Path) -> str:
    lexical_root = Path(os.path.abspath(root))
    for component in reversed((lexical_root, *lexical_root.parents)):
        _reject_link_or_reparse(component)
    root = lexical_root.resolve(strict=True)
    digest = hashlib.sha256()
    files: list[Path] = []
    for directory, dirnames, filenames in os.walk(root, followlinks=False):
        directory_path = Path(directory)
        _reject_link_or_reparse(directory_path)
        dirnames.sort()
        filenames.sort()
        for name in dirnames:
            _reject_link_or_reparse(directory_path / name)
        for name in filenames:
            path = directory_path / name
            _reject_link_or_reparse(path)
            if not stat.S_ISREG(path.lstat().st_mode):
                raise CandidateError(f"installed plugin contains a special file: {path}")
            files.append(path)
    for path in sorted(files, key=lambda item: item.relative_to(root).as_posix()):
        name = path.relative_to(root).as_posix().encode("utf-8")
        data = path.read_bytes()
        digest.update(len(name).to_bytes(4, "big"))
        digest.update(name)
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(hashlib.sha256(data).digest())
    return digest.hexdigest()


def materialize_candidate_marketplace(
    manifest_path: Path,
    artifact_dir: Path,
    destination: Path,
    *,
    repository: Path,
    expected_commit: str,
    marketplace_name: str,
) -> dict[str, Path]:
    if not marketplace_name or any(character.isspace() for character in marketplace_name):
        raise CandidateError("runtime marketplace name is invalid")
    manifest = verify_candidate_manifest(
        manifest_path,
        artifact_dir,
        repository=repository,
        expected_commit=expected_commit,
    )
    if destination.exists():
        raise CandidateError(f"runtime marketplace destination already exists: {destination}")
    (destination / ".agents/plugins").mkdir(parents=True)
    (destination / ".gitattributes").write_text(
        "* -text\n",
        encoding="utf-8",
        newline="\n",
    )
    plugin_roots: dict[str, Path] = {}
    entries: list[dict[str, Any]] = []
    for package in manifest["packages"]:
        name = str(package["name"])
        plugin_root = destination / "plugins" / name
        extract_archive_exact(
            artifact_dir / str(package["archive_filename"]),
            plugin_root,
        )
        if directory_content_sha256(plugin_root) != package["content_sha256"]:
            raise CandidateError(f"extracted package content mismatch: {name}")
        plugin_roots[name] = plugin_root
        entries.append(
            {
                "name": name,
                "source": {"source": "local", "path": f"./plugins/{name}"},
                "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
                "category": "Developer Tools",
            }
        )
    write_json(
        destination / ".agents/plugins/marketplace.json",
        {
            "name": marketplace_name,
            "interface": {"displayName": "Engineering Foundation H04 Candidate"},
            "plugins": entries,
        },
    )
    return plugin_roots


def _require_path_under(path: Path, root: Path, *, label: str) -> Path:
    resolved = path.resolve(strict=True)
    resolved_root = root.resolve(strict=True)
    try:
        resolved.relative_to(resolved_root)
    except ValueError as exc:
        raise CandidateError(f"{label} is outside the bounded candidate run: {path}") from exc
    return resolved


def create_live_runtime_context(
    *,
    manifest_path: Path,
    artifact_dir: Path,
    run_root: Path,
    marketplace_root: Path,
    marketplace_name: str,
    repository: Path,
    expected_commit: str,
) -> dict[str, Any]:
    run_root = run_root.resolve(strict=True)
    manifest_path = _require_path_under(
        manifest_path, run_root, label="candidate manifest"
    )
    artifact_dir = _require_path_under(
        artifact_dir, run_root, label="candidate artifact directory"
    )
    marketplace_root = _require_path_under(
        marketplace_root, run_root, label="candidate marketplace"
    )
    manifest = verify_candidate_manifest(
        manifest_path,
        artifact_dir,
        repository=repository,
        expected_commit=expected_commit,
    )
    if not marketplace_name.startswith("egoist-engineering-foundation-h04-"):
        raise CandidateError("candidate live marketplace name is not H04-bounded")
    content_by_name = {
        str(package["name"]): str(package["content_sha256"])
        for package in manifest["packages"]
    }
    for name, expected_content in content_by_name.items():
        plugin_root = marketplace_root / "plugins" / name
        if directory_content_sha256(plugin_root) != expected_content:
            raise CandidateError(
                f"candidate marketplace content differs from archive: {name}"
            )
    return {
        "schema_version": 1,
        "run_root": str(run_root),
        "manifest_path": str(manifest_path),
        "artifact_dir": str(artifact_dir),
        "marketplace_root": str(marketplace_root),
        "marketplace_name": marketplace_name,
        "candidate_manifest_sha256": sha256_file(manifest_path),
        "repository": manifest["repository"],
        "subject_commit_sha": manifest["subject_commit_sha"],
        "release_version": manifest["release_version"],
        "core_package_sha256": core_package(manifest)["sha256"],
        "core_content_sha256": core_package(manifest)["content_sha256"],
        "core_verifier_runner_sha256": core_package(manifest)[
            "verifier_runner_sha256"
        ],
    }


def load_live_runtime_context(
    context_path: Path,
    *,
    repository: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    context_path = context_path.resolve(strict=True)
    context = load_json(context_path)
    if context.get("schema_version") != 1:
        raise CandidateError("candidate live context schema is unsupported")
    run_root_value = context.get("run_root")
    if not isinstance(run_root_value, str):
        raise CandidateError("candidate live context omitted run_root")
    run_root = Path(run_root_value).resolve(strict=True)
    _require_path_under(context_path, run_root, label="candidate context")
    paths: dict[str, Path] = {}
    for field in ("manifest_path", "artifact_dir", "marketplace_root"):
        value = context.get(field)
        if not isinstance(value, str):
            raise CandidateError(f"candidate live context omitted {field}")
        paths[field] = _require_path_under(Path(value), run_root, label=field)
    expected_commit = git_text(repository, "rev-parse", "HEAD")
    manifest = verify_candidate_manifest(
        paths["manifest_path"],
        paths["artifact_dir"],
        repository=repository,
        expected_commit=expected_commit,
    )
    expected = create_live_runtime_context(
        manifest_path=paths["manifest_path"],
        artifact_dir=paths["artifact_dir"],
        run_root=run_root,
        marketplace_root=paths["marketplace_root"],
        marketplace_name=str(context.get("marketplace_name", "")),
        repository=repository,
        expected_commit=expected_commit,
    )
    if context != expected:
        raise CandidateError("candidate live context was modified or mixed")
    return context, manifest


def _build_command(args: argparse.Namespace) -> int:
    repository = args.repository.resolve()
    artifact_dir = args.artifacts.resolve()
    expected_commit = args.expected_commit or git_text(repository, "rev-parse", "HEAD")
    manifest = create_candidate_manifest(
        repository=repository,
        artifact_dir=artifact_dir,
        intended_tag=args.intended_tag,
        expected_commit=expected_commit,
        expected_repository=args.repository_name,
    )
    output = args.output.resolve() if args.output else artifact_dir / MANIFEST_FILENAME
    write_json(output, manifest)
    verified = verify_candidate_manifest(
        output,
        artifact_dir,
        repository=repository,
        expected_commit=expected_commit,
    )
    print(f"candidate manifest: {output}")
    print(f"candidate manifest sha256: {sha256_file(output)}")
    print(f"subject commit: {verified['subject_commit_sha']}")
    print("release candidate build: PASS (UNRELEASED)")
    return 0


def _verify_command(args: argparse.Namespace) -> int:
    repository = args.repository.resolve()
    expected_commit = args.expected_commit or git_text(repository, "rev-parse", "HEAD")
    manifest = verify_candidate_manifest(
        args.manifest,
        args.artifacts,
        repository=repository,
        expected_commit=expected_commit,
    )
    print(f"candidate manifest sha256: {sha256_file(args.manifest)}")
    print(f"subject commit: {manifest['subject_commit_sha']}")
    print("release candidate verification: PASS (UNRELEASED)")
    return 0


def _verify_assets_command(args: argparse.Namespace) -> int:
    manifest = load_json(args.manifest.resolve())
    verify_release_assets(
        manifest,
        args.artifacts.resolve(),
        repository=args.repository_name,
        tag=args.tag,
        tag_target=args.tag_target,
        prerelease=args.prerelease,
        source_repository=args.repository.resolve(),
        expected_manifest_sha256=args.expected_manifest_sha256,
    )
    print(f"release asset candidate manifest sha256: {sha256_file(args.manifest)}")
    print("release asset verification: PASS (read-only)")
    return 0


def _verify_beta1_assets_command(args: argparse.Namespace) -> int:
    verify_legacy_beta1_assets(
        args.artifacts.resolve(),
        repository=args.repository_name,
        tag=args.tag,
        tag_target=args.tag_target,
        prerelease=args.prerelease,
    )
    print("v0.3.0-beta.1 immutable asset verification: PASS (read-only)")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("build", "verify"):
        command = subparsers.add_parser(name)
        command.add_argument("--repository", type=Path, default=ROOT)
        command.add_argument("--artifacts", type=Path, required=True)
        command.add_argument("--expected-commit")
        if name == "build":
            command.add_argument("--output", type=Path)
            command.add_argument("--intended-tag", default=DEFAULT_INTENDED_TAG)
            command.add_argument("--repository-name", default=DEFAULT_REPOSITORY)
        else:
            command.add_argument("--manifest", type=Path, required=True)
    assets = subparsers.add_parser("verify-assets")
    assets.add_argument("--manifest", type=Path, required=True)
    assets.add_argument("--artifacts", type=Path, required=True)
    assets.add_argument("--repository", type=Path, default=ROOT)
    assets.add_argument("--repository-name", default=DEFAULT_REPOSITORY)
    assets.add_argument("--tag", required=True)
    assets.add_argument("--tag-target", required=True)
    assets.add_argument("--expected-manifest-sha256", required=True)
    assets.add_argument("--prerelease", action="store_true")
    beta1 = subparsers.add_parser("verify-beta1-assets")
    beta1.add_argument("--artifacts", type=Path, required=True)
    beta1.add_argument("--repository-name", default=DEFAULT_REPOSITORY)
    beta1.add_argument("--tag", default="v0.3.0-beta.1")
    beta1.add_argument("--tag-target", default=BETA1_TAG_COMMIT)
    beta1.add_argument("--prerelease", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.command == "build":
            return _build_command(args)
        if args.command == "verify":
            return _verify_command(args)
        if args.command == "verify-assets":
            return _verify_assets_command(args)
        return _verify_beta1_assets_command(args)
    except (CandidateError, OSError, KeyError, TypeError, ValueError) as exc:
        print(
            json.dumps(
                failure_payload(str(args.command), exc),
                ensure_ascii=False,
                separators=(",", ":"),
            ),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
