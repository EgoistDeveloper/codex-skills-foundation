from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_MODULE = ROOT / "scripts" / "qualification_workspace.py"
QUALIFICATION_SCRIPT = ROOT / "scripts" / "run_exact_artifact_qualification.py"
VALIDATION_WORKFLOW = ROOT / ".github" / "workflows" / "validate.yml"
WINDOWS_CLASSIC_LIMIT = 260
SCRIPT_DIR = ROOT / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import qualification_workspace as workspace
import run_codex_bounded_delegation_smoke as delegation
import run_codex_evidence_refusal_smoke as evidence
import run_codex_live_smoke as positive
import run_codex_negative_smoke as negative


def load_workspace_module():
    spec = importlib.util.spec_from_file_location(
        "qualification_workspace_for_tests",
        WORKSPACE_MODULE,
    )
    if spec is None or spec.loader is None:
        raise AssertionError("qualification workspace module cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class QualificationWorkspaceTests(unittest.TestCase):
    def test_historical_nested_repeatability_shape_crosses_windows_limit(self) -> None:
        seed = (
            ROOT
            / ".eval-runs"
            / "h04rw-live-20260819-013659"
            / "20260819-013700-7a8ea604"
            / "live"
            / "repeatability"
            / "20260819-013711-981435dc"
            / "runs"
            / "positive"
            / "rep-01"
            / "attempt-01"
            / "20260819-013715-c28f718d"
            / "seed"
        )
        git_object = seed / ".git" / "objects" / "c2" / ("a" * 38)
        self.assertGreaterEqual(len(str(git_object)), WINDOWS_CLASSIC_LIMIT)

    @unittest.skipUnless(os.name == "nt", "real classic-path Git failure is Windows-only")
    def test_real_git_add_fails_under_reproducing_long_root(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ef-long-root-") as tmp:
            root = Path(tmp)
            while len(str(root / "seed" / ".git")) < 211:
                root /= "repeatability-segment"
            seed = root / "seed"
            seed.mkdir(parents=True)
            (seed / ".gitignore").write_text("node_modules/\n", encoding="utf-8")
            subprocess.run(
                ["git", "init", "-q"],
                cwd=seed,
                check=True,
                capture_output=True,
            )
            result = subprocess.run(
                ["git", "add", "."],
                cwd=seed,
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Filename too long", result.stderr)

    def test_allocator_rejects_over_budget_before_directory_creation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            disposable = Path(tmp) / "disposable"
            impossible = disposable / ("x" * 64)
            with self.assertRaises(workspace.WorkspacePathError) as raised:
                workspace.allocate_workspace(
                    disposable_root=disposable,
                    artifact_root=Path(tmp) / "artifacts",
                    identity={"campaign": "red", "family": "positive"},
                    requested_path=impossible,
                    effective_limit=120,
                )
            self.assertFalse(impossible.exists())
            self.assertEqual(raised.exception.payload()["model_calls"], 0)

    def test_exact_qualification_exposes_complete_zero_model_rehearsal(self) -> None:
        source = QUALIFICATION_SCRIPT.read_text(encoding="utf-8")
        self.assertIn('"--zero-model-rehearsal"', source)

    def allocate(self, root: Path, **identity: object):
        return workspace.allocate_workspace(
            disposable_root=root / "d",
            artifact_root=root / "a",
            identity={"campaign": "campaign", "family": "positive", **identity},
        )

    def test_short_workspace_and_deterministic_mapping(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            identity = {"campaign": "campaign", "family": "positive", "case": "case"}
            expected = workspace.workspace_id(identity)
            with workspace.allocate_workspace(
                disposable_root=root / "d",
                artifact_root=root / "a",
                identity=identity,
            ) as lease:
                self.assertEqual(lease.path.name, expected)
                self.assertLess(lease.budget["maximum"], lease.budget["allowed"] + 1)
                mapping = json.loads(lease.mapping_path.read_text(encoding="utf-8"))
                self.assertEqual(mapping["workspace_id"], expected)
                self.assertEqual(mapping["cleanup_status"], "ACTIVE")
            mapping = json.loads(lease.mapping_path.read_text(encoding="utf-8"))
            self.assertEqual(mapping["cleanup_status"], "CLEANED")

    def test_identity_dimensions_do_not_collide(self) -> None:
        base = {"campaign": "campaign", "family": "positive"}
        identities = [
            base,
            {**base, "campaign": "campaign2"},
            {**base, "case": "other"},
            {**base, "repetition": 1},
            {**base, "repetition": 2},
            {**base, "attempt": 1},
            {**base, "attempt": 2},
        ]
        self.assertEqual(len({workspace.workspace_id(item) for item in identities}), len(identities))

    def test_worst_case_budget_covers_required_suffixes(self) -> None:
        report = workspace.path_budget(Path(tempfile.gettempdir()) / "efq/w123")
        for label in (
            "git_object",
            "git_pack_temp",
            "git_lock",
            "receipt",
            "cleanup_temp",
        ):
            self.assertIn(label, report["measurements"])
        artifact_report = workspace.validate_artifact_paths(
            {
                "transcript": Path(tempfile.gettempdir()) / "transcript.artifacts.json",
                "receipt": Path(tempfile.gettempdir()) / "receipt.json",
                "state": Path(tempfile.gettempdir()) / "state-restoration.json",
            }
        )
        self.assertLessEqual(artifact_report["maximum"], artifact_report["allowed"])

    def test_existing_workspace_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            identity = {"campaign": "campaign", "family": "positive"}
            existing = root / "d" / workspace.workspace_id(identity)
            existing.mkdir(parents=True)
            with self.assertRaisesRegex(workspace.WorkspacePathError, "already exists"):
                workspace.allocate_workspace(
                    disposable_root=root / "d",
                    artifact_root=root / "a",
                    identity=identity,
                )

    def test_workspace_outside_disposable_root_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            outside = root / "outside"
            with self.assertRaisesRegex(workspace.WorkspacePathError, "outside"):
                workspace.allocate_workspace(
                    disposable_root=root / "d",
                    artifact_root=root / "a",
                    identity={"campaign": "campaign", "family": "positive"},
                    requested_path=outside,
                )
            self.assertFalse(outside.exists())

    def test_symlink_workspace_is_rejected_where_supported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "target"
            target.mkdir()
            disposable = root / "d"
            disposable.mkdir()
            identity = {"campaign": "campaign", "family": "positive"}
            link = disposable / workspace.workspace_id(identity)
            try:
                link.symlink_to(target, target_is_directory=True)
            except OSError as exc:
                self.skipTest(f"directory symlink unavailable: {exc}")
            with self.assertRaisesRegex(workspace.WorkspacePathError, "symlink"):
                workspace.allocate_workspace(
                    disposable_root=disposable,
                    artifact_root=root / "a",
                    identity=identity,
                )

    @unittest.skipUnless(os.name == "nt", "real directory junction exists on Windows")
    def test_real_windows_junction_workspace_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "target"
            target.mkdir()
            disposable = root / "d"
            disposable.mkdir()
            identity = {"campaign": "campaign", "family": "positive"}
            junction = disposable / workspace.workspace_id(identity)
            result = subprocess.run(
                ["cmd.exe", "/d", "/c", "mklink", "/J", str(junction), str(target)],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode != 0:
                self.skipTest(f"directory junction unavailable: {result.stderr}")
            try:
                with self.assertRaisesRegex(workspace.WorkspacePathError, "reparse"):
                    workspace.allocate_workspace(
                        disposable_root=disposable,
                        artifact_root=root / "a",
                        identity=identity,
                    )
            finally:
                os.rmdir(junction)

    def test_reparse_metadata_is_detected(self) -> None:
        self.assertTrue(
            workspace._is_reparse(
                SimpleNamespace(st_file_attributes=workspace.FILE_ATTRIBUTE_REPARSE_POINT)
            )
        )

    def test_linked_artifact_root_is_rejected_before_mapping_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "artifact-target"
            target.mkdir()
            link = root / "artifact-link"
            try:
                link.symlink_to(target, target_is_directory=True)
            except OSError as exc:
                self.skipTest(f"directory symlink unavailable: {exc}")
            with self.assertRaisesRegex(workspace.WorkspacePathError, "symlink"):
                workspace.allocate_workspace(
                    disposable_root=root / "d",
                    artifact_root=link,
                    identity={"campaign": "campaign", "family": "positive"},
                )
            self.assertEqual(list(target.iterdir()), [])

    def test_nested_symlink_mapping_parent_cannot_escape_artifact_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            artifact = root / "artifacts"
            outside = root / "outside"
            artifact.mkdir()
            outside.mkdir()
            linked_parent = artifact / "maps"
            try:
                linked_parent.symlink_to(outside, target_is_directory=True)
            except OSError as exc:
                self.skipTest(f"directory symlink unavailable: {exc}")
            with self.assertRaisesRegex(workspace.WorkspacePathError, "symlink"):
                workspace.allocate_workspace(
                    disposable_root=root / "d",
                    artifact_root=artifact,
                    mapping_path=linked_parent / "map.json",
                    identity={"campaign": "campaign", "family": "positive"},
                )
            self.assertFalse((outside / "map.json").exists())

    @unittest.skipUnless(os.name == "nt", "real directory junction exists on Windows")
    def test_real_windows_junction_mapping_parent_cannot_escape_artifact_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            artifact = root / "artifacts"
            outside = root / "outside"
            artifact.mkdir()
            outside.mkdir()
            junction = artifact / "maps"
            result = subprocess.run(
                ["cmd.exe", "/d", "/c", "mklink", "/J", str(junction), str(outside)],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode != 0:
                self.skipTest(f"directory junction unavailable: {result.stderr}")
            try:
                with self.assertRaisesRegex(workspace.WorkspacePathError, "reparse"):
                    workspace.allocate_workspace(
                        disposable_root=root / "d",
                        artifact_root=artifact,
                        mapping_path=junction / "map.json",
                        identity={"campaign": "campaign", "family": "positive"},
                    )
                self.assertFalse((outside / "map.json").exists())
            finally:
                os.rmdir(junction)

    def test_real_git_init_add_commit_succeeds_under_allocator(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.allocate(root) as lease:
                seed = lease.child("s")
                positive.create_fixture(seed)
                self.assertEqual(positive.git(["status", "--porcelain"], cwd=seed), "")
                local = subprocess.run(
                    ["git", "config", "--local", "--get", "core.longpaths"],
                    cwd=seed,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(local.returncode, 1)

    def test_all_live_fixture_families_use_real_git(self) -> None:
        families = (
            ("positive", positive.create_fixture, positive.clone_fixture),
            ("negative", negative.create_fixture, negative.clone_fixture),
            ("delegation", delegation.create_fixture, delegation.clone_fixture),
            ("evidence", evidence.create_fixture, evidence.clone_fixture),
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for index, (name, create, clone) in enumerate(families):
                with workspace.allocate_workspace(
                    disposable_root=root / "d",
                    artifact_root=root / "a",
                    mapping_path=root / "a" / f"{name}.json",
                    identity={"campaign": "campaign", "family": name, "attempt": index},
                ) as lease:
                    seed, candidate = lease.child("s"), lease.child("c")
                    create(seed)
                    clone(seed, candidate)
                    self.assertEqual(positive.git(["status", "--porcelain"], cwd=candidate), "")

    def test_cleanup_removes_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            lease = self.allocate(root)
            path = lease.path
            lease.cleanup()
            self.assertFalse(path.exists())

    def test_locked_cleanup_failure_is_visible_and_restoration_still_runs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            lease = self.allocate(root)
            restored = False
            try:
                with mock.patch.object(workspace.shutil, "rmtree", side_effect=PermissionError("locked")):
                    with self.assertRaisesRegex(workspace.WorkspaceError, "cleanup failed"):
                        lease.cleanup(attempts=1, delay_seconds=0)
            finally:
                restored = True
                shutil.rmtree(lease.path)
                if lease in workspace._REGISTERED:
                    workspace._REGISTERED.remove(lease)
            self.assertTrue(restored)
            payload = json.loads(lease.mapping_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["cleanup_status"], "ERROR")

    def test_global_git_config_is_unchanged(self) -> None:
        before = subprocess.run(
            ["git", "config", "--global", "--list", "--show-origin"],
            capture_output=True,
            check=False,
        )
        with tempfile.TemporaryDirectory() as tmp:
            with self.allocate(Path(tmp)) as lease:
                positive.create_fixture(lease.child("s"))
        after = subprocess.run(
            ["git", "config", "--global", "--list", "--show-origin"],
            capture_output=True,
            check=False,
        )
        self.assertEqual((before.returncode, before.stdout, before.stderr), (after.returncode, after.stdout, after.stderr))

    def test_human_artifact_root_and_short_workspace_are_separate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            artifact = root / "human-readable-qualification-campaign-artifacts"
            with workspace.allocate_workspace(
                disposable_root=root / "d",
                artifact_root=artifact,
                identity={"campaign": "campaign", "family": "positive"},
            ) as lease:
                self.assertNotEqual(lease.path.parent, artifact)
                self.assertLess(len(lease.path.name), 18)

    def test_mapping_is_path_private_and_secret_free(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.allocate(root) as lease:
                payload = json.loads(lease.mapping_path.read_text(encoding="utf-8"))
                serialized = json.dumps(payload)
                self.assertNotIn(str(root), serialized)
                self.assertNotIn("token", serialized.lower())
                self.assertNotIn("password", serialized.lower())

    def test_tracked_workspace_sources_have_no_absolute_user_path(self) -> None:
        for path in (WORKSPACE_MODULE, Path(__file__), ROOT / "scripts/qualification_rehearsal.py"):
            text = path.read_text(encoding="utf-8")
            self.assertNotRegex(text, r"[A-Za-z]:\\Users\\")

    def test_posix_budget_remains_conservative(self) -> None:
        report = workspace.path_budget(
            Path("/tmp/efq/w123"),
            effective_limit=workspace.POSIX_CONSERVATIVE_LIMIT,
        )
        self.assertEqual(report["effective_limit"], 4096)
        self.assertLess(report["maximum"], report["allowed"])

    def test_all_live_entrypoints_reference_canonical_allocator(self) -> None:
        entries = [
            "run_codex_live_smoke.py",
            "run_codex_negative_smoke.py",
            "run_codex_bounded_delegation_smoke.py",
            "run_codex_evidence_refusal_smoke.py",
            "run_public_beta_lifecycle.py",
            "run_exact_artifact_qualification.py",
        ]
        for name in entries:
            source = (SCRIPT_DIR / name).read_text(encoding="utf-8")
            self.assertIn("qualification_workspace", source, name)

    def test_zero_model_ci_uses_the_qualified_supported_codex_client(self) -> None:
        workflow = VALIDATION_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("@openai/codex@0.148.0-alpha.15", workflow)
        self.assertNotIn("@openai/codex@0.146.0", workflow)


if __name__ == "__main__":
    unittest.main()
