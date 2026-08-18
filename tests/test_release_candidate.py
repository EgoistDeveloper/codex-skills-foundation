from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

import jsonschema


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts/release_candidate.py"
QUALIFICATION_PATH = ROOT / "scripts/run_exact_artifact_qualification.py"


def load_module():
    if not MODULE_PATH.is_file():
        raise AssertionError(
            "B02-H04 release-candidate identity verifier is not implemented"
        )
    spec = importlib.util.spec_from_file_location("release_candidate", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


def load_qualification_module():
    spec = importlib.util.spec_from_file_location(
        "run_exact_artifact_qualification_test", QUALIFICATION_PATH
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader
    spec.loader.exec_module(module)
    return module


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(repository: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout.strip()


def write_zip(path: Path, plugin_name: str, version: str) -> None:
    plugin = {
        "name": plugin_name,
        "version": version,
    }
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_STORED) as archive:
        archive.writestr("plugin.json", json.dumps(plugin) + "\n")
        archive.writestr(".codex-plugin/plugin.json", json.dumps(plugin) + "\n")
        archive.writestr(".claude-plugin/plugin.json", json.dumps(plugin) + "\n")
        archive.writestr(
            "skills/example/SKILL.md",
            "---\nname: example\ndescription: example\n---\n",
        )


def rewrite_zip_json(path: Path, member: str, value: dict) -> None:
    with zipfile.ZipFile(path, "r") as source:
        members = {info.filename: source.read(info) for info in source.infolist()}
    members[member] = (json.dumps(value) + "\n").encode("utf-8")
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_STORED) as archive:
        for name, payload in members.items():
            archive.writestr(name, payload)


class CandidateFixture:
    def __init__(self, root: Path) -> None:
        self.repository = root / "repository"
        self.artifacts = self.repository / "dist"
        self.repository.mkdir()
        self.artifacts.mkdir()
        (self.repository / ".gitignore").write_text("dist/\n", encoding="utf-8")
        plugin_root = self.repository / "plugins/example"
        plugin_root.mkdir(parents=True)
        plugin = {
            "name": "example",
            "version": "1.2.3-beta.1",
        }
        (plugin_root / "plugin.json").write_text(
            json.dumps(plugin) + "\n", encoding="utf-8", newline="\n"
        )
        for provider in (".codex-plugin", ".claude-plugin"):
            provider_root = plugin_root / provider
            provider_root.mkdir()
            (provider_root / "plugin.json").write_text(
                json.dumps(plugin) + "\n", encoding="utf-8", newline="\n"
            )
        (self.repository / "catalog").mkdir()
        (self.repository / "catalog/plugins.json").write_text(
            json.dumps(
                {
                    "marketplace": {
                        "name": "fixture-marketplace",
                        "repository": "https://github.com/example/project",
                    },
                    "plugins": [
                        {
                            "name": "example",
                            "version": "1.2.3-beta.1",
                            "path": "plugins/example",
                        }
                    ],
                }
            )
            + "\n",
            encoding="utf-8",
        )
        (self.repository / ".agents/plugins").mkdir(parents=True)
        (self.repository / ".agents/plugins/marketplace.json").write_text(
            json.dumps(
                {
                    "name": "fixture-marketplace",
                    "plugins": [
                        {
                            "name": "example",
                            "source": {
                                "source": "local",
                                "path": "./plugins/example",
                            },
                        }
                    ],
                }
            )
            + "\n",
            encoding="utf-8",
        )
        (self.repository / ".claude-plugin").mkdir()
        (self.repository / ".claude-plugin/marketplace.json").write_text(
            json.dumps(
                {
                    "name": "fixture-marketplace",
                    "plugins": [
                        {
                            "name": "example",
                            "version": "1.2.3-beta.1",
                            "source": "./plugins/example",
                        }
                    ],
                }
            )
            + "\n",
            encoding="utf-8",
        )
        self.archive = self.artifacts / "example-1.2.3-beta.1.zip"
        write_zip(self.archive, "example", "1.2.3-beta.1")
        (self.artifacts / "SHA256SUMS").write_text(
            f"{sha256(self.archive)}  {self.archive.name}\n",
            encoding="utf-8",
            newline="\n",
        )
        git(self.repository, "init", "-q", "-b", "main")
        git(self.repository, "config", "user.name", "Candidate Tests")
        git(self.repository, "config", "user.email", "candidate@example.invalid")
        git(self.repository, "add", ".")
        git(self.repository, "commit", "-q", "-m", "fixture")
        self.commit = git(self.repository, "rev-parse", "HEAD")

    def manifest(self, module):
        payload = module.create_candidate_manifest(
            repository=self.repository,
            artifact_dir=self.artifacts,
            intended_tag="v1.2.3-beta.1",
            expected_commit=self.commit,
            expected_repository="example/project",
            expected_hashes={"example": sha256(self.archive)},
        )
        path = self.artifacts / "release-candidate.json"
        module.write_json(path, payload)
        return path, payload


class ReleaseCandidateRedTests(unittest.TestCase):
    """The initial run is intentionally RED until the H04 boundary exists."""

    def setUp(self) -> None:
        self.module = load_module()
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.fixture = CandidateFixture(Path(self.temporary.name))

    def test_package_evidence_from_wrong_commit_is_rejected(self) -> None:
        manifest, _ = self.fixture.manifest(self.module)
        with self.assertRaisesRegex(self.module.CandidateError, "commit"):
            self.module.verify_candidate_manifest(
                manifest,
                self.fixture.artifacts,
                repository=self.fixture.repository,
                expected_commit="0" * 40,
            )

    def test_correct_filename_with_wrong_bytes_is_rejected(self) -> None:
        manifest, _ = self.fixture.manifest(self.module)
        self.fixture.archive.write_bytes(self.fixture.archive.read_bytes() + b"tamper")
        with self.assertRaisesRegex(self.module.CandidateError, "digest"):
            self.module.verify_candidate_manifest(
                manifest,
                self.fixture.artifacts,
                repository=self.fixture.repository,
                expected_commit=self.fixture.commit,
            )

    def test_correct_bytes_paired_with_wrong_version_is_rejected(self) -> None:
        manifest, payload = self.fixture.manifest(self.module)
        payload["packages"][0]["version"] = "9.9.9"
        self.module.write_json(manifest, payload)
        with self.assertRaisesRegex(self.module.CandidateError, "version"):
            self.module.verify_candidate_manifest(
                manifest,
                self.fixture.artifacts,
                repository=self.fixture.repository,
                expected_commit=self.fixture.commit,
            )

    def test_lifecycle_source_tree_fallback_is_rejected(self) -> None:
        manifest, payload = self.fixture.manifest(self.module)
        evidence = self.valid_lifecycle(manifest, payload)
        evidence["artifact_source"] = "source_tree"
        with self.assertRaisesRegex(self.module.CandidateError, "exact artifact"):
            self.module.verify_lifecycle_evidence(payload, evidence)

    def test_live_evidence_without_package_digest_is_rejected(self) -> None:
        manifest, payload = self.fixture.manifest(self.module)
        row = {
            "variant": "candidate",
            "candidate_repository": payload["repository"],
            "subject_commit": payload["subject_commit_sha"],
            "subject_version": payload["release_version"],
            "candidate_manifest_sha256": sha256(manifest),
        }
        with self.assertRaisesRegex(self.module.CandidateError, "package.*sha"):
            self.module.verify_live_row(payload, row, sha256(manifest))

    def test_mixed_candidate_manifests_are_rejected(self) -> None:
        manifest, payload = self.fixture.manifest(self.module)
        rows = [
            {
                "variant": "candidate",
                "candidate_repository": payload["repository"],
                "provider": "openai",
                "client": "codex-cli",
                "client_version": "fixture",
                "harness_commit": payload["subject_commit_sha"],
                "subject_commit": payload["subject_commit_sha"],
                "subject_version": payload["release_version"],
                "candidate_manifest_sha256": sha256(manifest),
                "package_sha256": payload["packages"][0]["sha256"],
            },
            {
                "variant": "candidate",
                "candidate_repository": payload["repository"],
                "provider": "openai",
                "client": "codex-cli",
                "client_version": "fixture",
                "harness_commit": payload["subject_commit_sha"],
                "subject_commit": payload["subject_commit_sha"],
                "subject_version": payload["release_version"],
                "candidate_manifest_sha256": "f" * 64,
                "package_sha256": payload["packages"][0]["sha256"],
            },
        ]
        with self.assertRaisesRegex(self.module.CandidateError, "mixed"):
            self.module.verify_live_rows(payload, rows, sha256(manifest))

    def test_stale_candidate_manifest_is_rejected(self) -> None:
        manifest, _ = self.fixture.manifest(self.module)
        (self.fixture.repository / "new.txt").write_text("new\n", encoding="utf-8")
        git(self.fixture.repository, "add", "new.txt")
        git(self.fixture.repository, "commit", "-q", "-m", "new head")
        with self.assertRaisesRegex(self.module.CandidateError, "stale|commit"):
            self.module.verify_candidate_manifest(
                manifest,
                self.fixture.artifacts,
                repository=self.fixture.repository,
                expected_commit=git(self.fixture.repository, "rev-parse", "HEAD"),
            )

    def test_missing_expected_release_asset_is_rejected(self) -> None:
        manifest, payload = self.fixture.manifest(self.module)
        frozen_digest = sha256(manifest)
        self.fixture.archive.unlink()
        with self.assertRaisesRegex(self.module.CandidateError, "missing"):
            self.module.verify_release_assets(
                payload,
                self.fixture.artifacts,
                repository="example/project",
                tag="v1.2.3-beta.1",
                tag_target=self.fixture.commit,
                prerelease=True,
                source_repository=self.fixture.repository,
                expected_manifest_sha256=frozen_digest,
            )

    def test_unexpected_release_asset_is_rejected(self) -> None:
        manifest, payload = self.fixture.manifest(self.module)
        frozen_digest = sha256(manifest)
        (self.fixture.artifacts / "unexpected.txt").write_text(
            "unexpected\n", encoding="utf-8"
        )
        with self.assertRaisesRegex(self.module.CandidateError, "unexpected"):
            self.module.verify_release_assets(
                payload,
                self.fixture.artifacts,
                repository="example/project",
                tag="v1.2.3-beta.1",
                tag_target=self.fixture.commit,
                prerelease=True,
                source_repository=self.fixture.repository,
                expected_manifest_sha256=frozen_digest,
            )

    def test_tag_pointing_at_wrong_commit_is_rejected(self) -> None:
        manifest, payload = self.fixture.manifest(self.module)
        frozen_digest = sha256(manifest)
        with self.assertRaisesRegex(self.module.CandidateError, "tag.*commit"):
            self.module.verify_release_assets(
                payload,
                self.fixture.artifacts,
                repository="example/project",
                tag="v1.2.3-beta.1",
                tag_target="f" * 40,
                prerelease=True,
                source_repository=self.fixture.repository,
                expected_manifest_sha256=frozen_digest,
            )

    def test_valid_exact_candidate_manifest_is_accepted(self) -> None:
        manifest, payload = self.fixture.manifest(self.module)
        verified = self.module.verify_candidate_manifest(
            manifest,
            self.fixture.artifacts,
            repository=self.fixture.repository,
            expected_commit=self.fixture.commit,
        )
        self.assertEqual(verified, payload)
        self.assertEqual(verified["candidate_state"], "UNRELEASED")

    def test_candidate_manifest_conforms_to_canonical_schema(self) -> None:
        _, payload = self.fixture.manifest(self.module)
        schema = json.loads(
            (ROOT / "schemas/release-candidate.schema.json").read_text(
                encoding="utf-8"
            )
        )
        jsonschema.Draft202012Validator(schema).validate(payload)

    def test_production_candidate_rejects_wrong_intended_tag(self) -> None:
        with mock.patch.object(
            self.module,
            "DEFAULT_REPOSITORY",
            self.fixture.repository.name,
        ), mock.patch.object(
            self.module,
            "EXPECTED_PACKAGE_HASHES",
            {"example": sha256(self.fixture.archive)},
        ):
            with self.assertRaisesRegex(self.module.CandidateError, "intended"):
                self.module.create_candidate_manifest(
                    repository=self.fixture.repository,
                    artifact_dir=self.fixture.artifacts,
                    intended_tag="v9.9.9",
                    expected_commit=self.fixture.commit,
                    expected_repository=self.fixture.repository.name,
                )

    def test_candidate_manifest_output_is_deterministic(self) -> None:
        first_path, first = self.fixture.manifest(self.module)
        first_bytes = first_path.read_bytes()
        second_path, second = self.fixture.manifest(self.module)
        self.assertEqual(first, second)
        self.assertEqual(first_bytes, second_path.read_bytes())

    def test_dirty_source_tree_is_rejected(self) -> None:
        (self.fixture.repository / "dirty.txt").write_text("dirty\n", encoding="utf-8")
        with self.assertRaisesRegex(self.module.CandidateError, "dirty"):
            self.fixture.manifest(self.module)

    def test_existing_intended_tag_on_another_commit_is_rejected(self) -> None:
        git(self.fixture.repository, "tag", "v1.2.3-beta.1", self.fixture.commit)
        (self.fixture.repository / "new.txt").write_text("new\n", encoding="utf-8")
        git(self.fixture.repository, "add", "new.txt")
        git(self.fixture.repository, "commit", "-q", "-m", "new")
        current = git(self.fixture.repository, "rev-parse", "HEAD")
        with self.assertRaisesRegex(self.module.CandidateError, "tag.*commit"):
            self.module.create_candidate_manifest(
                repository=self.fixture.repository,
                artifact_dir=self.fixture.artifacts,
                intended_tag="v1.2.3-beta.1",
                expected_commit=current,
                expected_repository="example/project",
                expected_hashes={"example": sha256(self.fixture.archive)},
            )

    def commit_catalog_repository(self, value: object, *, remove: bool = False) -> None:
        path = self.fixture.repository / "catalog/plugins.json"
        catalog = json.loads(path.read_text(encoding="utf-8"))
        if remove:
            catalog["marketplace"].pop("repository", None)
        else:
            catalog["marketplace"]["repository"] = value
        path.write_text(json.dumps(catalog) + "\n", encoding="utf-8", newline="\n")
        git(self.fixture.repository, "add", "catalog/plugins.json")
        git(self.fixture.repository, "commit", "-q", "-m", "catalog repository fixture")
        self.fixture.commit = git(self.fixture.repository, "rev-parse", "HEAD")

    def test_missing_catalog_repository_identity_is_rejected(self) -> None:
        self.commit_catalog_repository(None, remove=True)
        with self.assertRaisesRegex(self.module.CandidateError, "repository identity"):
            self.fixture.manifest(self.module)

    def test_non_string_catalog_repository_identity_is_rejected(self) -> None:
        self.commit_catalog_repository({"owner": "example", "name": "project"})
        with self.assertRaisesRegex(self.module.CandidateError, "repository identity"):
            self.fixture.manifest(self.module)

    def test_wrong_host_catalog_repository_identity_is_rejected(self) -> None:
        self.commit_catalog_repository("https://evil.invalid/example/project")
        with self.assertRaisesRegex(self.module.CandidateError, "repository identity"):
            self.fixture.manifest(self.module)

    def test_current_candidate_inventory_names_exactly_five_packages(self) -> None:
        catalog = self.module.load_catalog(ROOT)
        names = [item["name"] for item in self.module.catalog_plugins(catalog)]
        self.assertEqual(names, list(self.module.EXPECTED_PACKAGE_HASHES))
        self.assertEqual(len(names), 5)

    def test_missing_checksum_manifest_is_rejected(self) -> None:
        (self.fixture.artifacts / "SHA256SUMS").unlink()
        with self.assertRaisesRegex(self.module.CandidateError, "SHA256SUMS"):
            self.fixture.manifest(self.module)

    def test_missing_candidate_archive_is_rejected(self) -> None:
        digest = sha256(self.fixture.archive)
        self.fixture.archive.unlink()
        with self.assertRaisesRegex(self.module.CandidateError, "missing expected"):
            self.module.create_candidate_manifest(
                repository=self.fixture.repository,
                artifact_dir=self.fixture.artifacts,
                intended_tag="v1.2.3-beta.1",
                expected_commit=self.fixture.commit,
                expected_repository="example/project",
                expected_hashes={"example": digest},
            )

    def test_unexpected_candidate_archive_is_rejected(self) -> None:
        (self.fixture.artifacts / "unexpected.zip").write_bytes(b"not a package")
        with self.assertRaisesRegex(self.module.CandidateError, "unexpected"):
            self.fixture.manifest(self.module)

    def test_wrong_archive_size_is_rejected(self) -> None:
        manifest, payload = self.fixture.manifest(self.module)
        payload["packages"][0]["size_bytes"] += 1
        self.module.write_json(manifest, payload)
        with self.assertRaisesRegex(self.module.CandidateError, "packages|size"):
            self.module.verify_candidate_manifest(
                manifest,
                self.fixture.artifacts,
                repository=self.fixture.repository,
                expected_commit=self.fixture.commit,
            )

    def test_wrong_archive_filename_version_is_rejected(self) -> None:
        manifest, payload = self.fixture.manifest(self.module)
        payload["packages"][0]["archive_filename"] = "example-9.9.9.zip"
        self.module.write_json(manifest, payload)
        with self.assertRaisesRegex(self.module.CandidateError, "filename/version"):
            self.module.verify_candidate_manifest(
                manifest,
                self.fixture.artifacts,
                repository=self.fixture.repository,
                expected_commit=self.fixture.commit,
            )

    def test_codex_embedded_manifest_version_drift_is_rejected(self) -> None:
        rewrite_zip_json(
            self.fixture.archive,
            ".codex-plugin/plugin.json",
            {"name": "example", "version": "9.9.9"},
        )
        digest = sha256(self.fixture.archive)
        (self.fixture.artifacts / "SHA256SUMS").write_text(
            f"{digest}  {self.fixture.archive.name}\n",
            encoding="utf-8",
            newline="\n",
        )
        with self.assertRaisesRegex(self.module.CandidateError, "Codex|manifest|version"):
            self.module.create_candidate_manifest(
                repository=self.fixture.repository,
                artifact_dir=self.fixture.artifacts,
                intended_tag="v1.2.3-beta.1",
                expected_commit=self.fixture.commit,
                expected_repository="example/project",
                expected_hashes={"example": digest},
            )

    def test_claude_embedded_manifest_name_drift_is_rejected(self) -> None:
        rewrite_zip_json(
            self.fixture.archive,
            ".claude-plugin/plugin.json",
            {"name": "substituted", "version": "1.2.3-beta.1"},
        )
        digest = sha256(self.fixture.archive)
        (self.fixture.artifacts / "SHA256SUMS").write_text(
            f"{digest}  {self.fixture.archive.name}\n",
            encoding="utf-8",
            newline="\n",
        )
        with self.assertRaisesRegex(self.module.CandidateError, "Claude|manifest|name"):
            self.module.create_candidate_manifest(
                repository=self.fixture.repository,
                artifact_dir=self.fixture.artifacts,
                intended_tag="v1.2.3-beta.1",
                expected_commit=self.fixture.commit,
                expected_repository="example/project",
                expected_hashes={"example": digest},
            )

    def test_openai_marketplace_source_inventory_drift_is_rejected(self) -> None:
        path = self.fixture.repository / ".agents/plugins/marketplace.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["plugins"][0]["source"]["path"] = "./plugins/substituted"
        path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
        git(self.fixture.repository, "add", str(path.relative_to(self.fixture.repository)))
        git(self.fixture.repository, "commit", "-q", "-m", "marketplace drift")
        current = git(self.fixture.repository, "rev-parse", "HEAD")
        with self.assertRaisesRegex(self.module.CandidateError, "marketplace|source"):
            self.module.create_candidate_manifest(
                repository=self.fixture.repository,
                artifact_dir=self.fixture.artifacts,
                intended_tag="v1.2.3-beta.1",
                expected_commit=current,
                expected_repository="example/project",
                expected_hashes={"example": sha256(self.fixture.archive)},
            )

    def test_claude_marketplace_version_inventory_drift_is_rejected(self) -> None:
        path = self.fixture.repository / ".claude-plugin/marketplace.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["plugins"][0]["version"] = "9.9.9"
        path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
        git(self.fixture.repository, "add", str(path.relative_to(self.fixture.repository)))
        git(self.fixture.repository, "commit", "-q", "-m", "marketplace drift")
        current = git(self.fixture.repository, "rev-parse", "HEAD")
        with self.assertRaisesRegex(self.module.CandidateError, "marketplace|version"):
            self.module.create_candidate_manifest(
                repository=self.fixture.repository,
                artifact_dir=self.fixture.artifacts,
                intended_tag="v1.2.3-beta.1",
                expected_commit=current,
                expected_repository="example/project",
                expected_hashes={"example": sha256(self.fixture.archive)},
            )

    def test_sha256sums_mismatch_is_rejected(self) -> None:
        (self.fixture.artifacts / "SHA256SUMS").write_text(
            f"{'0' * 64}  {self.fixture.archive.name}\n",
            encoding="utf-8",
            newline="\n",
        )
        with self.assertRaisesRegex(self.module.CandidateError, "SHA256SUMS"):
            self.fixture.manifest(self.module)

    def test_candidate_manifest_tampering_is_rejected(self) -> None:
        manifest, payload = self.fixture.manifest(self.module)
        payload["catalog_sha256"] = "f" * 64
        self.module.write_json(manifest, payload)
        with self.assertRaisesRegex(self.module.CandidateError, "catalog_sha256"):
            self.module.verify_candidate_manifest(
                manifest,
                self.fixture.artifacts,
                repository=self.fixture.repository,
                expected_commit=self.fixture.commit,
            )

    def valid_lifecycle(self, manifest: Path, payload: dict) -> dict:
        return {
            "outcome": "PASS",
            "artifact_source": "exact_archive",
            "candidate_manifest_sha256": sha256(manifest),
            "subject_commit_sha": payload["subject_commit_sha"],
            "package_sha256": {
                item["name"]: item["sha256"] for item in payload["packages"]
            },
            "installed_content_sha256": {
                item["name"]: item["content_sha256"]
                for item in payload["packages"]
            },
            "model_calls": 0,
            "state_restored": True,
            "loopback_only": True,
            "isolated_config_clean": True,
            "installed_plugins_remaining": [],
            "marketplace_remaining": False,
        }

    def test_lifecycle_exact_artifact_provenance_is_accepted(self) -> None:
        manifest, payload = self.fixture.manifest(self.module)
        self.module.verify_lifecycle_evidence(
            payload, self.valid_lifecycle(manifest, payload)
        )

    def test_lifecycle_binds_installed_core_receipt_runner_identity(self) -> None:
        manifest, payload = self.fixture.manifest(self.module)
        payload["packages"][0]["name"] = "engineering-foundation-core"
        payload["packages"][0]["verifier_runner_sha256"] = "a" * 64
        evidence = self.valid_lifecycle(manifest, payload)
        evidence["candidate_manifest_sha256"] = self.module.sha256_bytes(
            self.module.canonical_json_bytes(payload)
        )
        evidence["installed_verifier_runner_sha256"] = "a" * 64
        self.module.verify_lifecycle_evidence(payload, evidence)

        evidence.pop("installed_verifier_runner_sha256")
        with self.assertRaisesRegex(self.module.CandidateError, "verifier runner"):
            self.module.verify_lifecycle_evidence(payload, evidence)

    def test_lifecycle_candidate_manifest_digest_is_required(self) -> None:
        manifest, payload = self.fixture.manifest(self.module)
        evidence = self.valid_lifecycle(manifest, payload)
        evidence.pop("candidate_manifest_sha256")
        with self.assertRaisesRegex(self.module.CandidateError, "manifest"):
            self.module.verify_lifecycle_evidence(payload, evidence)

    def test_lifecycle_wrong_candidate_manifest_digest_is_rejected(self) -> None:
        manifest, payload = self.fixture.manifest(self.module)
        evidence = self.valid_lifecycle(manifest, payload)
        evidence["candidate_manifest_sha256"] = "0" * 64
        with self.assertRaisesRegex(self.module.CandidateError, "manifest"):
            self.module.verify_lifecycle_evidence(payload, evidence)

    def test_lifecycle_non_pass_outcome_is_rejected(self) -> None:
        manifest, payload = self.fixture.manifest(self.module)
        evidence = self.valid_lifecycle(manifest, payload)
        evidence["outcome"] = "HARNESS_ERROR"
        with self.assertRaisesRegex(self.module.CandidateError, "PASS"):
            self.module.verify_lifecycle_evidence(payload, evidence)

    def test_lifecycle_installed_content_digest_is_required(self) -> None:
        manifest, payload = self.fixture.manifest(self.module)
        evidence = self.valid_lifecycle(manifest, payload)
        evidence.pop("installed_content_sha256")
        with self.assertRaisesRegex(self.module.CandidateError, "installed content"):
            self.module.verify_lifecycle_evidence(payload, evidence)

    def test_lifecycle_wrong_installed_content_digest_is_rejected(self) -> None:
        manifest, payload = self.fixture.manifest(self.module)
        evidence = self.valid_lifecycle(manifest, payload)
        evidence["installed_content_sha256"]["example"] = "0" * 64
        with self.assertRaisesRegex(self.module.CandidateError, "installed content"):
            self.module.verify_lifecycle_evidence(payload, evidence)

    def test_lifecycle_installed_cleanup_is_required(self) -> None:
        manifest, payload = self.fixture.manifest(self.module)
        evidence = self.valid_lifecycle(manifest, payload)
        evidence["installed_plugins_remaining"] = ["example"]
        with self.assertRaisesRegex(self.module.CandidateError, "left installed"):
            self.module.verify_lifecycle_evidence(payload, evidence)

    def test_lifecycle_zero_model_calls_is_required(self) -> None:
        manifest, payload = self.fixture.manifest(self.module)
        evidence = self.valid_lifecycle(manifest, payload)
        evidence["model_calls"] = 1
        with self.assertRaisesRegex(self.module.CandidateError, "zero model"):
            self.module.verify_lifecycle_evidence(payload, evidence)

    def test_lifecycle_loopback_only_is_required(self) -> None:
        manifest, payload = self.fixture.manifest(self.module)
        evidence = self.valid_lifecycle(manifest, payload)
        evidence["loopback_only"] = False
        with self.assertRaisesRegex(self.module.CandidateError, "loopback"):
            self.module.verify_lifecycle_evidence(payload, evidence)

    def extracted_plugin(self, payload: dict) -> Path:
        destination = Path(self.temporary.name) / "extracted"
        self.module.extract_archive_exact(self.fixture.archive, destination)
        self.assertEqual(
            self.module.directory_content_sha256(destination),
            payload["packages"][0]["content_sha256"],
        )
        return destination

    def test_installed_version_is_bound_to_candidate(self) -> None:
        _, payload = self.fixture.manifest(self.module)
        installed = self.extracted_plugin(payload)
        with self.assertRaisesRegex(self.module.CandidateError, "version mismatch"):
            self.module.verify_installed_plugin(
                payload,
                plugin_name="example",
                installed_version="9.9.9",
                installed_root=installed,
            )

    def test_installed_content_is_bound_to_archive(self) -> None:
        _, payload = self.fixture.manifest(self.module)
        installed = self.extracted_plugin(payload)
        (installed / "tampered.txt").write_text("tampered\n", encoding="utf-8")
        with self.assertRaisesRegex(self.module.CandidateError, "content mismatch"):
            self.module.verify_installed_plugin(
                payload,
                plugin_name="example",
                installed_version="1.2.3-beta.1",
                installed_root=installed,
            )

    def test_candidate_plugin_cache_substitution_is_rejected(self) -> None:
        _, payload = self.fixture.manifest(self.module)
        installed = self.extracted_plugin(payload)
        cache = installed / "__pycache__"
        cache.mkdir()
        (cache / "helper.pyc").write_bytes(b"cache")
        with self.assertRaisesRegex(self.module.CandidateError, "content mismatch"):
            self.module.verify_installed_plugin(
                payload,
                plugin_name="example",
                installed_version="1.2.3-beta.1",
                installed_root=installed,
            )

    def test_installed_root_symlink_is_rejected_where_supported(self) -> None:
        _, payload = self.fixture.manifest(self.module)
        installed = self.extracted_plugin(payload)
        linked = Path(self.temporary.name) / "linked-installed"
        try:
            linked.symlink_to(installed, target_is_directory=True)
        except (NotImplementedError, OSError) as exc:
            self.skipTest(f"real directory symlinks are unavailable: {exc}")
        try:
            with self.assertRaisesRegex(self.module.CandidateError, "linked"):
                self.module.verify_installed_plugin(
                    payload,
                    plugin_name="example",
                    installed_version="1.2.3-beta.1",
                    installed_root=linked,
                )
        finally:
            if linked.is_symlink():
                linked.unlink()

    @unittest.skipUnless(os.name == "nt", "real Windows junctions require Windows")
    def test_installed_root_windows_junction_is_rejected(self) -> None:
        _, payload = self.fixture.manifest(self.module)
        installed = self.extracted_plugin(payload)
        junction = Path(self.temporary.name) / "junction-installed"
        result = subprocess.run(
            ["cmd.exe", "/d", "/c", "mklink", "/J", str(junction), str(installed)],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            self.fail(
                "failed to create real Windows junction: "
                f"stdout={result.stdout!r} stderr={result.stderr!r}"
            )
        try:
            self.assertFalse(junction.is_symlink())
            with self.assertRaisesRegex(self.module.CandidateError, "linked"):
                self.module.verify_installed_plugin(
                    payload,
                    plugin_name="example",
                    installed_version="1.2.3-beta.1",
                    installed_root=junction,
                )
        finally:
            if junction.exists():
                os.rmdir(junction)

    def test_current_skill_counts_are_exact(self) -> None:
        expected = {
            "engineering-foundation-core": 9,
            "engineering-foundation-laravel": 1,
            "engineering-foundation-design": 2,
            "engineering-foundation-cloud": 1,
            "engineering-foundation-authoring": 1,
        }
        actual = {}
        for plugin in self.module.catalog_plugins(self.module.load_catalog(ROOT)):
            actual[plugin["name"]] = len(
                list((ROOT / plugin["path"] / "skills").glob("*/SKILL.md"))
            )
        self.assertEqual(actual, expected)

    def test_current_core_archive_receipt_runner_hash_is_exact(self) -> None:
        catalog = json.loads((ROOT / "catalog/plugins.json").read_text(encoding="utf-8"))
        core = next(
            item
            for item in catalog["plugins"]
            if item["name"] == "engineering-foundation-core"
        )
        package_spec = importlib.util.spec_from_file_location(
            "package_plugins_for_release_runner_identity",
            ROOT / "scripts/package_plugins.py",
        )
        package_module = importlib.util.module_from_spec(package_spec)
        assert package_spec.loader
        package_spec.loader.exec_module(package_module)
        with tempfile.TemporaryDirectory() as tmp:
            archive, _ = package_module.build_archive(core, Path(tmp))
            member_hash = self.module.archive_member_sha256(
                archive,
                self.module.VERIFIER_RUNNER_MEMBER,
            )
        runner = (
            ROOT
            / "plugins/engineering-foundation-core/skills/verify-before-completion"
            / self.module.VERIFIER_RUNNER_MEMBER.removeprefix(
                "skills/verify-before-completion/"
            )
        )
        self.assertEqual(member_hash, sha256(runner))

    def valid_live_row(self, manifest: Path, payload: dict) -> dict:
        package = payload["packages"][0]
        return {
            "variant": "candidate",
            "candidate_repository": payload["repository"],
            "provider": "openai",
            "client": "codex-cli",
            "client_version": "fixture",
            "harness_commit": payload["subject_commit_sha"],
            "subject_commit": payload["subject_commit_sha"],
            "subject_version": package["version"],
            "candidate_manifest_sha256": sha256(manifest),
            "package_sha256": package["sha256"],
        }

    def test_evidence_refusal_live_row_requires_structured_receipt_identity(self) -> None:
        manifest, payload = self.fixture.manifest(self.module)
        row = self.valid_live_row(manifest, payload)
        row["case_id"] = "required-evidence-refusal"
        with self.assertRaisesRegex(self.module.CandidateError, "verifier_receipt"):
            self.module.verify_live_row(payload, row, sha256(manifest))

        row.update(
            {
                "verifier_receipt_run_id": "run-1",
                "verifier_receipt_command_id": "command-1",
                "verifier_receipt_payload_sha256": "a" * 64,
                "verifier_receipt_event_id": "event-1",
            }
        )
        self.module.verify_live_row(payload, row, sha256(manifest))
        row["verifier_receipt_payload_sha256"] = "invalid"
        with self.assertRaisesRegex(self.module.CandidateError, "payload SHA-256"):
            self.module.verify_live_row(payload, row, sha256(manifest))

    def test_live_rows_reject_cross_campaign_identity_drift(self) -> None:
        manifest, payload = self.fixture.manifest(self.module)
        digest = sha256(manifest)
        for field in ("provider", "client", "client_version", "harness_commit"):
            with self.subTest(field=field):
                first = self.valid_live_row(manifest, payload)
                second = dict(first)
                second[field] = "substituted"
                with self.assertRaisesRegex(self.module.CandidateError, field):
                    self.module.verify_live_rows(payload, [first, second], digest)

    def test_live_subject_commit_is_required(self) -> None:
        manifest, payload = self.fixture.manifest(self.module)
        row = self.valid_live_row(manifest, payload)
        row["subject_commit"] = None
        with self.assertRaisesRegex(self.module.CandidateError, "subject commit"):
            self.module.verify_live_row(payload, row, sha256(manifest))

    def test_live_candidate_manifest_digest_is_required(self) -> None:
        manifest, payload = self.fixture.manifest(self.module)
        row = self.valid_live_row(manifest, payload)
        row.pop("candidate_manifest_sha256")
        with self.assertRaisesRegex(self.module.CandidateError, "manifest SHA"):
            self.module.verify_live_row(payload, row, sha256(manifest))

    def test_stale_live_artifact_identity_is_rejected(self) -> None:
        manifest, payload = self.fixture.manifest(self.module)
        row = self.valid_live_row(manifest, payload)
        row["package_sha256"] = "0" * 64
        with self.assertRaisesRegex(self.module.CandidateError, "package sha"):
            self.module.verify_live_row(payload, row, sha256(manifest))

    def test_artifact_path_must_remain_under_bounded_run(self) -> None:
        run_root = Path(self.temporary.name) / "run"
        run_root.mkdir()
        outside = Path(self.temporary.name) / "outside.json"
        outside.write_text("{}\n", encoding="utf-8")
        with self.assertRaisesRegex(self.module.CandidateError, "outside"):
            self.module.verify_bounded_artifact(outside, run_root)

    def test_release_asset_digest_mismatch_is_rejected(self) -> None:
        manifest, payload = self.fixture.manifest(self.module)
        frozen_digest = sha256(manifest)
        self.fixture.archive.write_bytes(self.fixture.archive.read_bytes() + b"tamper")
        with self.assertRaisesRegex(self.module.CandidateError, "digest"):
            self.module.verify_release_assets(
                payload,
                self.fixture.artifacts,
                repository="example/project",
                tag="v1.2.3-beta.1",
                tag_target=self.fixture.commit,
                prerelease=True,
                source_repository=self.fixture.repository,
                expected_manifest_sha256=frozen_digest,
            )

    def test_release_assets_reject_substituted_manifest_identity(self) -> None:
        manifest, payload = self.fixture.manifest(self.module)
        frozen_digest = sha256(manifest)
        payload["catalog_sha256"] = "f" * 64
        payload["marketplace_identity"] = {
            "openai_sha256": "e" * 64,
            "claude_sha256": "d" * 64,
        }
        self.module.write_json(manifest, payload)
        with self.assertRaisesRegex(
            self.module.CandidateError, "manifest|catalog|marketplace"
        ):
            self.module.verify_release_assets(
                payload,
                self.fixture.artifacts,
                repository="example/project",
                tag="v1.2.3-beta.1",
                tag_target=self.fixture.commit,
                prerelease=True,
                source_repository=self.fixture.repository,
                expected_manifest_sha256=frozen_digest,
            )

    def test_beta1_immutable_fixture_contract(self) -> None:
        asset_dir = Path(self.temporary.name) / "beta1"
        asset_dir.mkdir()
        archive = asset_dir / "legacy.zip"
        archive.write_bytes(b"legacy")
        digest = sha256(archive)
        (asset_dir / "SHA256SUMS").write_text(
            f"{digest}  legacy.zip\n", encoding="utf-8", newline="\n"
        )
        with mock.patch.object(
            self.module, "BETA1_PACKAGE_HASHES", {"legacy.zip": digest}
        ):
            self.module.verify_legacy_beta1_assets(
                asset_dir,
                repository=self.module.DEFAULT_REPOSITORY,
                tag="v0.3.0-beta.1",
                tag_target=self.module.BETA1_TAG_COMMIT,
                prerelease=True,
            )

    def test_h04_tool_has_no_tag_or_release_mutation_command(self) -> None:
        source = MODULE_PATH.read_text(encoding="utf-8")
        self.assertNotIn("gh release create", source)
        self.assertNotIn("gh release upload", source)
        self.assertNotIn("git tag", source)
        self.assertNotIn("git push --force", source)

    def test_candidate_cli_failure_is_machine_readable(self) -> None:
        missing = Path(self.temporary.name) / "missing.json"
        result = subprocess.run(
            [
                sys.executable,
                str(MODULE_PATH),
                "verify",
                "--repository",
                str(self.fixture.repository),
                "--artifacts",
                str(self.fixture.artifacts),
                "--expected-commit",
                self.fixture.commit,
                "--manifest",
                str(missing),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env={**os.environ, "PYTHONUTF8": "1"},
        )
        self.assertEqual(result.returncode, 1)
        failure = json.loads(result.stderr)
        self.assertEqual(failure["outcome"], "FAIL")
        self.assertEqual(failure["operation"], "verify")
        self.assertIn("candidate manifest", failure["error"])

    def test_timed_out_child_gets_interrupt_and_restores_state(self) -> None:
        qualification = load_qualification_module()
        state = Path(self.temporary.name) / "timeout-state.txt"
        transcript = Path(self.temporary.name) / "timeout-transcript.txt"
        script = (
            "import pathlib,signal,time\n"
            f"state=pathlib.Path({str(state)!r})\n"
            "sig=getattr(signal,'SIGBREAK',signal.SIGINT)\n"
            "def interrupt(*_): raise KeyboardInterrupt()\n"
            "signal.signal(sig,interrupt)\n"
            "try:\n"
            " try:\n"
            "  state.write_text('mutated',encoding='utf-8')\n"
            "  while True: time.sleep(0.05)\n"
            " except KeyboardInterrupt: pass\n"
            "finally:\n"
            " state.write_text('restored',encoding='utf-8')\n"
        )
        with self.assertRaisesRegex(qualification.QualificationError, "timed out"):
            qualification.run_process(
                [sys.executable, "-c", script],
                transcript=transcript,
                timeout=0.5,
            )
        self.assertEqual(state.read_text(encoding="utf-8"), "restored")
        self.assertTrue(transcript.is_file())

    def test_nonzero_child_cleanup_completes_before_failure(self) -> None:
        qualification = load_qualification_module()
        state = Path(self.temporary.name) / "nonzero-state.txt"
        transcript = Path(self.temporary.name) / "nonzero-transcript.txt"
        script = (
            "import pathlib,sys\n"
            f"state=pathlib.Path({str(state)!r})\n"
            "try:\n"
            " state.write_text('mutated',encoding='utf-8')\n"
            "finally:\n"
            " state.write_text('restored',encoding='utf-8')\n"
            "sys.exit(7)\n"
        )
        with self.assertRaisesRegex(qualification.QualificationError, "returned 7"):
            qualification.run_process(
                [sys.executable, "-c", script],
                transcript=transcript,
                timeout=10,
            )
        self.assertEqual(state.read_text(encoding="utf-8"), "restored")
        self.assertTrue(transcript.is_file())

    def test_qualification_cli_failure_is_machine_readable(self) -> None:
        missing = Path(self.temporary.name) / "missing.json"
        result = subprocess.run(
            [
                sys.executable,
                str(QUALIFICATION_PATH),
                "--candidate-manifest",
                str(missing),
                "--artifacts",
                str(self.fixture.artifacts),
                "--lifecycle-only",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env={**os.environ, "PYTHONUTF8": "1"},
        )
        self.assertEqual(result.returncode, 1)
        failure = json.loads(result.stderr)
        self.assertEqual(failure["outcome"], "FAIL")
        self.assertEqual(failure["operation"], "exact-artifact-qualification")

    def test_qualification_output_rejects_tracked_repository_path(self) -> None:
        qualification = load_qualification_module()
        with self.assertRaisesRegex(qualification.QualificationError, r"\.eval-runs"):
            qualification.bounded_output_root(ROOT / "docs/h04-raw-evidence")

    def test_qualification_output_rejects_linked_component(self) -> None:
        qualification = load_qualification_module()
        ignored = ROOT / ".eval-runs"
        ignored.mkdir(exist_ok=True)
        target = Path(self.temporary.name) / "outside-output"
        target.mkdir()
        linked = ignored / f"linked-output-{Path(self.temporary.name).name}"
        if os.name == "nt":
            result = subprocess.run(
                ["cmd.exe", "/d", "/c", "mklink", "/J", str(linked), str(target)],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                self.fail(
                    "failed to create real Windows output junction: "
                    f"stdout={result.stdout!r} stderr={result.stderr!r}"
                )
        else:
            linked.symlink_to(target, target_is_directory=True)
        try:
            with self.assertRaisesRegex(
                qualification.QualificationError, "linked|unsafe"
            ):
                qualification.bounded_output_root(linked / "campaigns")
        finally:
            if os.name == "nt" and linked.exists():
                os.rmdir(linked)
            elif linked.is_symlink():
                linked.unlink()

    def test_shareable_provenance_rejects_absolute_user_path(self) -> None:
        with self.assertRaisesRegex(self.module.CandidateError, "absolute path"):
            self.module.validate_shareable_provenance(
                {"artifact": "C:/Users/Example/private/result.json"}
            )

    def test_shareable_provenance_rejects_credentials(self) -> None:
        with self.assertRaisesRegex(self.module.CandidateError, "credential field"):
            self.module.validate_shareable_provenance({"access_token": "not-a-real-token"})

    def test_materialized_marketplace_comes_from_archive_content(self) -> None:
        manifest, payload = self.fixture.manifest(self.module)
        marketplace = Path(self.temporary.name) / "marketplace"
        roots = self.module.materialize_candidate_marketplace(
            manifest,
            self.fixture.artifacts,
            marketplace,
            repository=self.fixture.repository,
            expected_commit=self.fixture.commit,
            marketplace_name="fixture-marketplace",
        )
        self.assertEqual(set(roots), {"example"})
        self.assertEqual(
            self.module.directory_content_sha256(roots["example"]),
            payload["packages"][0]["content_sha256"],
        )
        self.assertFalse((marketplace / "catalog").exists())

    def test_materialized_marketplace_preserves_archive_bytes_through_git(self) -> None:
        manifest, payload = self.fixture.manifest(self.module)
        marketplace = Path(self.temporary.name) / "marketplace-git-source"
        self.module.materialize_candidate_marketplace(
            manifest,
            self.fixture.artifacts,
            marketplace,
            repository=self.fixture.repository,
            expected_commit=self.fixture.commit,
            marketplace_name="fixture-marketplace",
        )
        git(marketplace, "init", "-q", "-b", "main")
        git(marketplace, "config", "user.name", "Candidate Tests")
        git(marketplace, "config", "user.email", "candidate@example.invalid")
        git(marketplace, "config", "core.autocrlf", "true")
        git(marketplace, "add", ".")
        git(marketplace, "commit", "-q", "-m", "candidate")

        checkout = Path(self.temporary.name) / "marketplace-git-checkout"
        subprocess.run(
            [
                "git",
                "-c",
                "core.autocrlf=true",
                "clone",
                "-q",
                str(marketplace),
                str(checkout),
            ],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        self.assertEqual(
            self.module.directory_content_sha256(checkout / "plugins/example"),
            payload["packages"][0]["content_sha256"],
        )

    def test_candidate_context_rejects_path_outside_bounded_run(self) -> None:
        manifest, _ = self.fixture.manifest(self.module)
        run_root = Path(self.temporary.name) / "run"
        run_root.mkdir()
        marketplace = run_root / "marketplace"
        marketplace.mkdir()
        with self.assertRaisesRegex(self.module.CandidateError, "outside"):
            self.module.create_live_runtime_context(
                manifest_path=manifest,
                artifact_dir=self.fixture.artifacts,
                run_root=run_root,
                marketplace_root=marketplace,
                marketplace_name="egoist-engineering-foundation-h04-fixture",
                repository=self.fixture.repository,
                expected_commit=self.fixture.commit,
            )


if __name__ == "__main__":
    unittest.main()
