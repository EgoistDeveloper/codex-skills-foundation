#!/usr/bin/env python3
"""Validate the public beta install, upgrade, discovery, and removal lifecycle.

This maintainer smoke makes no model calls. It creates a disposable CODEX_HOME,
serves a temporary Git marketplace over loopback HTTP, installs the previous
Core version, advances the marketplace to the current beta candidate, upgrades
and reinstalls Core, installs every optional package, verifies namespaced skill
discovery, then removes every plugin and the marketplace. The user's real Codex
home is never read or changed.
"""
from __future__ import annotations

import argparse
import contextlib
import functools
import http.server
import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import run_codex_live_smoke as base
import release_candidate

ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "catalog" / "plugins.json"
RELEASE_VERSION = "0.3.0-beta.2"
PREVIOUS_CORE_VERSION = "0.2.2"
PREVIOUS_MARKETPLACE_COMMIT = "578d9836c040b27ed54ebf68291990cfeca288d4"
LIFECYCLE_BRANCH = "beta-lifecycle"
OUTPUT_ROOT = ROOT / ".eval-runs" / "public-beta-lifecycle"


class LifecycleError(RuntimeError):
    """Expected public-beta lifecycle failure."""


def run_process(
    args: list[str] | tuple[str, ...],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    expected: set[int] | None = None,
    text: bool = True,
    timeout: int = 180,
) -> subprocess.CompletedProcess[Any]:
    result = subprocess.run(
        list(args),
        cwd=str(cwd) if cwd else None,
        env=env,
        capture_output=True,
        text=text,
        encoding="utf-8" if text else None,
        errors="replace" if text else None,
        timeout=timeout,
    )
    expected_codes = expected or {0}
    if result.returncode not in expected_codes:
        stdout = result.stdout if text else "<binary stdout>"
        stderr = result.stderr if text else "<binary stderr>"
        detail = "\n".join(
            str(part).strip() for part in (stdout, stderr) if part
        )
        raise LifecycleError(
            f"command returned {result.returncode}; expected {sorted(expected_codes)}: "
            f"{' '.join(map(str, args))}\n{detail}"
        )
    return result


def git(
    args: list[str],
    *,
    cwd: Path,
    expected: set[int] | None = None,
) -> str:
    return str(
        run_process(["git", *args], cwd=cwd, expected=expected).stdout
    ).rstrip("\r\n")


def load_catalog(path: Path = CATALOG_PATH) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise LifecycleError("catalog/plugins.json must contain an object.")
    plugins = value.get("plugins")
    if not isinstance(plugins, list) or not plugins:
        raise LifecycleError("catalog/plugins.json contains no plugins.")
    return value


def plugin_versions(catalog: dict[str, Any]) -> dict[str, str]:
    versions: dict[str, str] = {}
    for plugin in catalog["plugins"]:
        if not isinstance(plugin, dict):
            raise LifecycleError("catalog plugin entry is not an object.")
        name = plugin.get("name")
        version = plugin.get("version")
        if not isinstance(name, str) or not isinstance(version, str):
            raise LifecycleError("catalog plugin entry has an invalid name/version.")
        versions[name] = version
    return versions


def expected_skill_names(root: Path, plugin_names: set[str]) -> set[str]:
    names: set[str] = set()
    for plugin_name in sorted(plugin_names):
        skills_root = root / "plugins" / plugin_name / "skills"
        if not skills_root.is_dir():
            raise LifecycleError(f"skills directory is missing: {skills_root}")
        for skill_file in sorted(skills_root.glob("*/SKILL.md")):
            names.add(f"{plugin_name}:{skill_file.parent.name}")
    if not names:
        raise LifecycleError("no expected skills were discovered from the source tree.")
    return names


def safe_extract_tar(payload: bytes, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    root = destination.resolve()
    with tarfile.open(fileobj=io.BytesIO(payload), mode="r:") as archive:
        members = archive.getmembers()
        for member in members:
            target = (destination / member.name).resolve()
            try:
                target.relative_to(root)
            except ValueError as error:
                raise LifecycleError(
                    f"git archive contains an unsafe path: {member.name}"
                ) from error
        archive.extractall(destination, members=members)


def archive_commit(repository: Path, revision: str, destination: Path) -> None:
    result = run_process(
        ["git", "archive", "--format=tar", revision],
        cwd=repository,
        text=False,
    )
    safe_extract_tar(bytes(result.stdout), destination)


def clear_worktree_except_git(worktree: Path) -> None:
    for child in worktree.iterdir():
        if child.name == ".git":
            continue
        if child.is_dir() and not child.is_symlink():
            shutil.rmtree(child)
        else:
            child.unlink()


def create_marketplace_remote(
    *,
    repository: Path,
    temporary_root: Path,
) -> tuple[Path, Path]:
    source = temporary_root / "marketplace-source"
    bare = temporary_root / "marketplace.git"
    archive_commit(repository, PREVIOUS_MARKETPLACE_COMMIT, source)
    git(["init", "-q"], cwd=source)
    git(["config", "user.name", "Engineering Foundation Lifecycle"], cwd=source)
    git(
        ["config", "user.email", "lifecycle@example.invalid"],
        cwd=source,
    )
    git(["add", "."], cwd=source)
    git(["commit", "-q", "-m", "test: previous marketplace snapshot"], cwd=source)
    git(["branch", "-M", LIFECYCLE_BRANCH], cwd=source)
    git(["init", "--bare", "-q", str(bare)], cwd=temporary_root)
    git(["remote", "add", "origin", str(bare)], cwd=source)
    git(["push", "-q", "-u", "origin", LIFECYCLE_BRANCH], cwd=source)
    run_process(["git", "--git-dir", str(bare), "update-server-info"])
    return source, bare


def advance_marketplace_to_candidate(
    *,
    repository: Path,
    source: Path,
    bare: Path,
    candidate_snapshot: Path | None = None,
) -> None:
    clear_worktree_except_git(source)
    if candidate_snapshot is None:
        archive_commit(repository, "HEAD", source)
    else:
        for child in candidate_snapshot.iterdir():
            target = source / child.name
            if child.is_dir():
                shutil.copytree(child, target)
            else:
                shutil.copy2(child, target)
    git(["add", "-A"], cwd=source)
    changed = run_process(
        ["git", "diff", "--cached", "--quiet"],
        cwd=source,
        expected={0, 1},
    )
    if changed.returncode != 1:
        raise LifecycleError(
            "candidate marketplace snapshot does not differ from the previous snapshot."
        )
    git(["commit", "-q", "-m", "test: candidate marketplace snapshot"], cwd=source)
    git(["push", "-q", "origin", LIFECYCLE_BRANCH], cwd=source)
    run_process(["git", "--git-dir", str(bare), "update-server-info"])


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, _format: str, *args: object) -> None:
        return


@contextlib.contextmanager
def loopback_git_server(root: Path) -> Iterator[str]:
    handler = functools.partial(QuietHandler, directory=str(root))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address[:2]
        yield f"http://{host}:{port}/marketplace.git"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def isolated_environment(codex_home: Path) -> dict[str, str]:
    codex_home.mkdir(parents=True, exist_ok=True)
    (codex_home / "config.toml").write_text(
        """[features]
plugins = true
remote_plugin = false
recommended_plugins = false
plugin_sharing = false
apps = false
memories = false
js_repl = false
""",
        encoding="utf-8",
        newline="\n",
    )
    env = os.environ.copy()
    env["CODEX_HOME"] = str(codex_home)
    env["HOME"] = str(codex_home)
    env["USERPROFILE"] = str(codex_home)
    env["NO_COLOR"] = "1"
    return env


def cli_json(
    launchers: base.CodexLaunchers,
    env: dict[str, str],
    *args: str,
) -> Any:
    result = run_process([*launchers.cli_prefix, *args], env=env)
    text = str(result.stdout).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError as error:
        raise LifecycleError(
            f"Codex command returned invalid JSON: {' '.join(args)}\n{text}"
        ) from error


def installed_rows(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        raise LifecycleError("plugin list returned a non-object JSON value.")
    rows = payload.get("installed")
    if not isinstance(rows, list):
        raise LifecycleError("plugin list returned no installed array.")
    return [row for row in rows if isinstance(row, dict)]


def marketplace_plugin_rows(
    payload: Any,
    *,
    marketplace_name: str,
) -> list[dict[str, Any]]:
    return [
        row
        for row in installed_rows(payload)
        if row.get("marketplaceName") == marketplace_name
    ]


@contextlib.contextmanager
def patched_process_environment(env: dict[str, str]) -> Iterator[None]:
    keys = ("CODEX_HOME", "HOME", "USERPROFILE", "NO_COLOR")
    original = {key: os.environ.get(key) for key in keys}
    try:
        for key in keys:
            if key in env:
                os.environ[key] = env[key]
            else:
                os.environ.pop(key, None)
        yield
    finally:
        for key, value in original.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def discover_namespaced_skills(
    *,
    launchers: base.CodexLaunchers,
    env: dict[str, str],
    workspace: Path,
    trace_path: Path,
    plugin_names: set[str],
    expected_codex_home: Path,
) -> tuple[set[str], dict[str, str]]:
    with patched_process_environment(env):
        with base.AppServer(
            command=launchers.app_server_command,
            node_executable=launchers.node_executable,
            cwd=workspace,
            trace_path=trace_path,
            timeout_seconds=120,
        ) as server:
            reported_home = server.initialize()
            if base.normalized_path(reported_home) != base.normalized_path(
                expected_codex_home
            ):
                raise LifecycleError(
                    f"app-server used the wrong CODEX_HOME: {reported_home}"
                )
            skills = server.skills_list(workspace)

    prefixes = tuple(f"{name}:" for name in sorted(plugin_names))
    discovered: set[str] = set()
    paths: dict[str, str] = {}
    for skill in skills:
        name = skill.get("name")
        path = skill.get("path")
        if not isinstance(name, str) or not name.startswith(prefixes):
            continue
        if skill.get("enabled") is not True:
            raise LifecycleError(f"discovered beta skill is disabled: {name}")
        if not isinstance(path, str) or not path:
            raise LifecycleError(f"discovered beta skill has no path: {name}")
        discovered.add(name)
        paths[name] = path
    return discovered, paths


def require_plugin_version(
    *,
    payload: Any,
    plugin_name: str,
    expected_version: str,
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise LifecycleError("plugin add returned a non-object JSON value.")
    if payload.get("name") != plugin_name:
        raise LifecycleError(
            f"plugin add returned the wrong plugin: {payload.get('name')!r}"
        )
    if payload.get("version") != expected_version:
        raise LifecycleError(
            f"{plugin_name} installed at {payload.get('version')!r}; "
            f"expected {expected_version!r}."
        )
    return payload


def require_installed_inventory(
    *,
    payload: Any,
    expected_versions: dict[str, str],
    marketplace_name: str,
) -> None:
    rows = marketplace_plugin_rows(payload, marketplace_name=marketplace_name)
    actual = {
        str(row.get("name")): str(row.get("version"))
        for row in rows
        if row.get("installed") is True
    }
    if actual != expected_versions:
        raise LifecycleError(
            f"installed plugin inventory mismatch: actual={actual}, "
            f"expected={expected_versions}"
        )
    if any(row.get("enabled") is not True for row in rows):
        raise LifecycleError("one or more lifecycle plugins are not enabled.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the zero-model public beta install/upgrade/remove lifecycle."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=OUTPUT_ROOT,
        help="Lifecycle artifact root.",
    )
    parser.add_argument(
        "--candidate-manifest",
        type=Path,
        help="Exact release-candidate manifest produced after packaging.",
    )
    parser.add_argument(
        "--artifacts",
        type=Path,
        help="Directory containing the exact five ZIPs and SHA256SUMS.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if bool(args.candidate_manifest) != bool(args.artifacts):
        raise LifecycleError(
            "--candidate-manifest and --artifacts must be supplied together."
        )
    catalog = load_catalog()
    versions = plugin_versions(catalog)
    core_name = base.PLUGIN_NAME
    if versions.get(core_name) != RELEASE_VERSION:
        raise LifecycleError(
            f"catalog core version is {versions.get(core_name)!r}; "
            f"expected {RELEASE_VERSION!r}."
        )
    if git(["status", "--porcelain"], cwd=ROOT):
        raise LifecycleError("foundation working tree must be clean.")
    if not git(["cat-file", "-e", f"{PREVIOUS_MARKETPLACE_COMMIT}^{{commit}}"], cwd=ROOT, expected={0}):
        pass

    launchers = base.resolve_codex_launchers()
    repository_head = git(["rev-parse", "HEAD"], cwd=ROOT)
    candidate_manifest: dict[str, Any] | None = None
    candidate_manifest_sha256: str | None = None
    package_sha256: dict[str, str] | None = None
    if args.candidate_manifest is not None and args.artifacts is not None:
        try:
            candidate_manifest = release_candidate.verify_candidate_manifest(
                args.candidate_manifest,
                args.artifacts,
                repository=ROOT,
                expected_commit=repository_head,
            )
        except release_candidate.CandidateError as exc:
            raise LifecycleError(str(exc)) from exc
        candidate_manifest_sha256 = release_candidate.sha256_file(
            args.candidate_manifest
        )
        package_sha256 = {
            str(package["name"]): str(package["sha256"])
            for package in candidate_manifest["packages"]
        }
    output_root = args.output.resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    campaign = output_root / f"{stamp}-{os.urandom(4).hex()}"
    campaign.mkdir(parents=True, exist_ok=False)
    artifact_path = campaign / "summary.json"

    result: dict[str, Any] = {
        "schema_version": 1,
        "outcome": "HARNESS_ERROR",
        "model_calls": 0,
        "repository_head": repository_head,
        "previous_marketplace_commit": PREVIOUS_MARKETPLACE_COMMIT,
        "previous_core_version": PREVIOUS_CORE_VERSION,
        "release_version": RELEASE_VERSION,
        "marketplace_name": base.MARKETPLACE_NAME,
        "codex_version": launchers.version_text,
        "steps": [],
        "artifact_source": (
            "exact_archive" if candidate_manifest is not None else "source_tree"
        ),
        "subject_commit_sha": (
            candidate_manifest["subject_commit_sha"]
            if candidate_manifest is not None
            else repository_head
        ),
        "candidate_manifest_sha256": candidate_manifest_sha256,
        "package_sha256": package_sha256,
        "state_restored": False,
    }

    try:
        with tempfile.TemporaryDirectory(
            prefix="engineering-foundation-beta-lifecycle-"
        ) as temporary:
            temporary_root = Path(temporary).resolve()
            source, bare = create_marketplace_remote(
                repository=ROOT,
                temporary_root=temporary_root,
            )
            candidate_snapshot: Path | None = None
            if candidate_manifest is not None:
                assert args.candidate_manifest is not None
                assert args.artifacts is not None
                candidate_snapshot = temporary_root / "candidate-artifact-marketplace"
                try:
                    release_candidate.materialize_candidate_marketplace(
                        args.candidate_manifest,
                        args.artifacts,
                        candidate_snapshot,
                        repository=ROOT,
                        expected_commit=repository_head,
                        marketplace_name=base.MARKETPLACE_NAME,
                    )
                except release_candidate.CandidateError as exc:
                    raise LifecycleError(str(exc)) from exc
            codex_home = temporary_root / "codex-home"
            env = isolated_environment(codex_home)
            workspace = temporary_root / "workspace"
            workspace.mkdir()
            previous_source = temporary_root / "previous-source"
            archive_commit(ROOT, PREVIOUS_MARKETPLACE_COMMIT, previous_source)
            previous_expected_skills = expected_skill_names(
                previous_source,
                {core_name},
            )
            candidate_plugin_names = set(versions)
            candidate_expected_skills = expected_skill_names(
                candidate_snapshot or ROOT,
                candidate_plugin_names,
            )

            with loopback_git_server(temporary_root) as marketplace_url:
                added_marketplace = cli_json(
                    launchers,
                    env,
                    "plugin",
                    "marketplace",
                    "add",
                    marketplace_url,
                    "--ref",
                    LIFECYCLE_BRANCH,
                    "--json",
                )
                if not isinstance(added_marketplace, dict) or added_marketplace.get(
                    "marketplaceName"
                ) != base.MARKETPLACE_NAME:
                    raise LifecycleError(
                        f"unexpected marketplace add result: {added_marketplace}"
                    )
                result["steps"].append("marketplace_add_previous:PASS")

                previous_core = require_plugin_version(
                    payload=cli_json(
                        launchers,
                        env,
                        "plugin",
                        "add",
                        base.PLUGIN_ID,
                        "--json",
                    ),
                    plugin_name=core_name,
                    expected_version=PREVIOUS_CORE_VERSION,
                )
                result["previous_core_install"] = previous_core
                previous_skills, previous_paths = discover_namespaced_skills(
                    launchers=launchers,
                    env=env,
                    workspace=workspace,
                    trace_path=campaign / "previous-skills-trace.jsonl",
                    plugin_names={core_name},
                    expected_codex_home=codex_home,
                )
                if previous_skills != previous_expected_skills:
                    raise LifecycleError(
                        "previous Core discovery mismatch: "
                        f"actual={sorted(previous_skills)}, "
                        f"expected={sorted(previous_expected_skills)}"
                    )
                result["previous_core_skill_count"] = len(previous_skills)
                result["previous_core_paths"] = previous_paths
                result["steps"].append("previous_core_install_discovery:PASS")

                advance_marketplace_to_candidate(
                    repository=ROOT,
                    source=source,
                    bare=bare,
                    candidate_snapshot=candidate_snapshot,
                )
                upgrade_output = cli_json(
                    launchers,
                    env,
                    "plugin",
                    "marketplace",
                    "upgrade",
                    base.MARKETPLACE_NAME,
                    "--json",
                )
                result["marketplace_upgrade"] = upgrade_output
                result["steps"].append("marketplace_upgrade:PASS")

                beta_core = require_plugin_version(
                    payload=cli_json(
                        launchers,
                        env,
                        "plugin",
                        "add",
                        base.PLUGIN_ID,
                        "--json",
                    ),
                    plugin_name=core_name,
                    expected_version=RELEASE_VERSION,
                )
                result["beta_core_install"] = beta_core
                installed_payloads: dict[str, dict[str, Any]] = {
                    core_name: beta_core
                }
                result["steps"].append("core_reinstall_update:PASS")

                for plugin_name in sorted(candidate_plugin_names - {core_name}):
                    selector = f"{plugin_name}@{base.MARKETPLACE_NAME}"
                    installed_payloads[plugin_name] = require_plugin_version(
                        payload=cli_json(
                            launchers,
                            env,
                            "plugin",
                            "add",
                            selector,
                            "--json",
                        ),
                        plugin_name=plugin_name,
                        expected_version=versions[plugin_name],
                    )
                if candidate_manifest is not None:
                    package_by_name = {
                        str(package["name"]): package
                        for package in candidate_manifest["packages"]
                    }
                    installed_content_sha256: dict[str, str] = {}
                    for plugin_name, payload in installed_payloads.items():
                        installed_path_value = payload.get("installedPath")
                        if not isinstance(installed_path_value, str):
                            raise LifecycleError(
                                f"{plugin_name} install result omitted installedPath."
                            )
                        installed_path = Path(installed_path_value)
                        try:
                            digest = release_candidate.directory_content_sha256(
                                installed_path
                            )
                        except release_candidate.CandidateError as exc:
                            raise LifecycleError(str(exc)) from exc
                        expected_content = package_by_name[plugin_name][
                            "content_sha256"
                        ]
                        if digest != expected_content:
                            raise LifecycleError(
                                f"installed plugin content differs from exact archive: "
                                f"{plugin_name}"
                            )
                        installed_content_sha256[plugin_name] = digest
                    result["installed_content_sha256"] = installed_content_sha256
                    result["steps"].append("exact_archive_content_identity:PASS")
                inventory = cli_json(
                    launchers,
                    env,
                    "plugin",
                    "list",
                    "--json",
                )
                require_installed_inventory(
                    payload=inventory,
                    expected_versions=versions,
                    marketplace_name=base.MARKETPLACE_NAME,
                )
                result["steps"].append("all_packages_install:PASS")

                discovered, discovered_paths = discover_namespaced_skills(
                    launchers=launchers,
                    env=env,
                    workspace=workspace,
                    trace_path=campaign / "candidate-skills-trace.jsonl",
                    plugin_names=candidate_plugin_names,
                    expected_codex_home=codex_home,
                )
                if discovered != candidate_expected_skills:
                    raise LifecycleError(
                        "candidate skill discovery mismatch: "
                        f"actual={sorted(discovered)}, "
                        f"expected={sorted(candidate_expected_skills)}"
                    )
                normalized_home = base.normalized_path(codex_home)
                outside_paths = {
                    name: path
                    for name, path in discovered_paths.items()
                    if os.path.commonpath(
                        [base.normalized_path(path), normalized_home]
                    )
                    != normalized_home
                }
                if outside_paths:
                    raise LifecycleError(
                        f"installed skills escaped isolated CODEX_HOME: {outside_paths}"
                    )
                result["candidate_skill_count"] = len(discovered)
                result["candidate_skills"] = sorted(discovered)
                result["steps"].append("all_packages_discovery:PASS")

                for plugin_name in sorted(candidate_plugin_names, reverse=True):
                    selector = f"{plugin_name}@{base.MARKETPLACE_NAME}"
                    removed = cli_json(
                        launchers,
                        env,
                        "plugin",
                        "remove",
                        selector,
                        "--json",
                    )
                    if not isinstance(removed, dict):
                        raise LifecycleError(
                            f"plugin remove returned invalid JSON for {plugin_name}."
                        )
                after_remove = cli_json(
                    launchers,
                    env,
                    "plugin",
                    "list",
                    "--json",
                )
                if marketplace_plugin_rows(
                    after_remove,
                    marketplace_name=base.MARKETPLACE_NAME,
                ):
                    raise LifecycleError("one or more beta plugins remain installed.")
                result["installed_plugins_remaining"] = []
                result["steps"].append("all_packages_remove:PASS")

                removed_marketplace = cli_json(
                    launchers,
                    env,
                    "plugin",
                    "marketplace",
                    "remove",
                    base.MARKETPLACE_NAME,
                    "--json",
                )
                if not isinstance(removed_marketplace, dict):
                    raise LifecycleError("marketplace remove returned invalid JSON.")
                marketplace_list = cli_json(
                    launchers,
                    env,
                    "plugin",
                    "marketplace",
                    "list",
                    "--json",
                )
                marketplaces = (
                    marketplace_list.get("marketplaces", [])
                    if isinstance(marketplace_list, dict)
                    else []
                )
                if any(
                    isinstance(row, dict)
                    and row.get("name") == base.MARKETPLACE_NAME
                    for row in marketplaces
                ):
                    raise LifecycleError("beta marketplace remains configured.")
                result["marketplace_remaining"] = False
                result["steps"].append("marketplace_remove:PASS")

            config_text = (codex_home / "config.toml").read_text(encoding="utf-8")
            forbidden_fragments = [
                base.MARKETPLACE_NAME,
                *candidate_plugin_names,
            ]
            leaked_fragments = [
                fragment for fragment in forbidden_fragments if fragment in config_text
            ]
            if leaked_fragments:
                raise LifecycleError(
                    f"isolated config retained lifecycle entries: {leaked_fragments}"
                )
            result["isolated_codex_home"] = str(codex_home)
            result["isolated_config_clean"] = True
            result["loopback_only"] = True
            result["state_restored"] = True
            result["outcome"] = "PASS"
    except Exception as error:
        result["error"] = str(error)
        artifact_path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        print("\nPUBLIC BETA LIFECYCLE FAILURE DIAGNOSTICS")
        print(f"  reason  : {error}")
        print(f"  artifact: {artifact_path}")
        return 1

    artifact_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    if candidate_manifest is not None:
        try:
            release_candidate.verify_lifecycle_evidence(candidate_manifest, result)
        except release_candidate.CandidateError as exc:
            result["outcome"] = "HARNESS_ERROR"
            result["error"] = str(exc)
            artifact_path.write_text(
                json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
                newline="\n",
            )
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
    print("\nPUBLIC BETA LIFECYCLE SUMMARY")
    print(f"  outcome             : {result['outcome']}")
    print(f"  model calls         : {result['model_calls']}")
    print(f"  previous Core       : {PREVIOUS_CORE_VERSION}")
    print(f"  beta Core           : {RELEASE_VERSION}")
    print(f"  packages installed  : {len(versions)}")
    print(f"  skills discovered   : {result['candidate_skill_count']}")
    print("  marketplace upgrade : PASS")
    print("  plugin removal      : PASS")
    print("  marketplace removal : PASS")
    print("  isolated config     : CLEAN")
    print(f"  artifact            : {artifact_path}")
    print("Result: PASS (public beta install, update, discovery, and removal lifecycle)")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("ERROR: interrupted.", file=sys.stderr)
        raise SystemExit(130)
    except (LifecycleError, OSError, subprocess.SubprocessError, json.JSONDecodeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
