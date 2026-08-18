from __future__ import annotations

import importlib.util
import io
import json
import os
import tarfile
import tempfile
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "run_public_beta_lifecycle",
    ROOT / "scripts/run_public_beta_lifecycle.py",
)
module = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(module)


class PublicBetaLifecycleTests(unittest.TestCase):
    def test_release_identity_matches_catalog(self) -> None:
        versions = module.plugin_versions(module.load_catalog())
        self.assertEqual(
            versions["engineering-foundation-core"],
            module.RELEASE_VERSION,
        )
        self.assertEqual(module.RELEASE_VERSION, "0.3.0-beta.2")
        self.assertEqual(module.PREVIOUS_CORE_VERSION, "0.2.2")
        self.assertRegex(module.PREVIOUS_MARKETPLACE_COMMIT, r"^[0-9a-f]{40}$")

    def test_catalog_keeps_optional_packages_at_their_existing_versions(self) -> None:
        versions = module.plugin_versions(module.load_catalog())
        self.assertEqual(
            versions,
            {
                "engineering-foundation-authoring": "0.2.1",
                "engineering-foundation-cloud": "0.2.1",
                "engineering-foundation-core": "0.3.0-beta.2",
                "engineering-foundation-design": "0.2.1",
                "engineering-foundation-laravel": "0.2.1",
            },
        )

    def test_expected_skill_inventory_covers_every_package(self) -> None:
        versions = module.plugin_versions(module.load_catalog())
        names = module.expected_skill_names(ROOT, set(versions))
        self.assertEqual(len(names), 14)
        self.assertIn(
            "engineering-foundation-core:verify-before-completion",
            names,
        )
        self.assertIn(
            "engineering-foundation-core:bounded-orchestration",
            names,
        )
        self.assertIn(
            "engineering-foundation-laravel:laravel-project-engineering",
            names,
        )
        self.assertIn(
            "engineering-foundation-design:visual-verification",
            names,
        )
        self.assertIn(
            "engineering-foundation-cloud:cloud-readiness",
            names,
        )
        self.assertIn(
            "engineering-foundation-authoring:skill-authoring",
            names,
        )

    def test_safe_extract_rejects_path_traversal(self) -> None:
        payload = io.BytesIO()
        with tarfile.open(fileobj=payload, mode="w") as archive:
            info = tarfile.TarInfo("../escape.txt")
            content = b"escape"
            info.size = len(content)
            archive.addfile(info, io.BytesIO(content))
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(module.LifecycleError, "unsafe path"):
                module.safe_extract_tar(payload.getvalue(), Path(tmp))

    def test_isolated_environment_writes_only_disposable_home(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            codex_home = Path(tmp) / "codex-home"
            env = module.isolated_environment(codex_home)
            self.assertEqual(env["CODEX_HOME"], str(codex_home))
            self.assertEqual(env["HOME"], str(codex_home))
            self.assertEqual(env["USERPROFILE"], str(codex_home))
            config = (codex_home / "config.toml").read_text(encoding="utf-8")
            self.assertIn("plugins = true", config)
            self.assertIn("remote_plugin = false", config)
            self.assertIn("apps = false", config)
            self.assertIn("memories = false", config)

    def test_require_plugin_version_rejects_wrong_version(self) -> None:
        valid = {
            "name": "engineering-foundation-core",
            "version": module.RELEASE_VERSION,
        }
        self.assertEqual(
            module.require_plugin_version(
                payload=valid,
                plugin_name="engineering-foundation-core",
                expected_version=module.RELEASE_VERSION,
            ),
            valid,
        )
        with self.assertRaisesRegex(module.LifecycleError, "installed at"):
            module.require_plugin_version(
                payload={
                    "name": "engineering-foundation-core",
                    "version": "0.2.2",
                },
                plugin_name="engineering-foundation-core",
                expected_version=module.RELEASE_VERSION,
            )

    def test_installed_inventory_requires_exact_versions_and_enabled_state(self) -> None:
        expected = {
            "engineering-foundation-core": module.RELEASE_VERSION,
            "engineering-foundation-laravel": "0.2.1",
        }
        rows: list[dict[str, Any]] = [
            {
                "name": name,
                "version": version,
                "marketplaceName": module.base.MARKETPLACE_NAME,
                "installed": True,
                "enabled": True,
            }
            for name, version in expected.items()
        ]
        module.require_installed_inventory(
            payload={"installed": rows},
            expected_versions=expected,
            marketplace_name=module.base.MARKETPLACE_NAME,
        )
        rows[0]["enabled"] = False
        with self.assertRaisesRegex(module.LifecycleError, "not enabled"):
            module.require_installed_inventory(
                payload={"installed": rows},
                expected_versions=expected,
                marketplace_name=module.base.MARKETPLACE_NAME,
            )

    def test_clear_worktree_preserves_git_metadata_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".git").mkdir()
            (root / ".git" / "config").write_text("git", encoding="utf-8")
            (root / "file.txt").write_text("file", encoding="utf-8")
            (root / "folder").mkdir()
            (root / "folder" / "nested.txt").write_text("nested", encoding="utf-8")
            module.clear_worktree_except_git(root)
            self.assertTrue((root / ".git" / "config").is_file())
            self.assertEqual([child.name for child in root.iterdir()], [".git"])

    def test_summary_contract_declares_zero_model_calls(self) -> None:
        source = (ROOT / "scripts/run_public_beta_lifecycle.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('"model_calls": 0', source)
        self.assertIn("marketplace_upgrade:PASS", source)
        self.assertIn("all_packages_discovery:PASS", source)
        self.assertIn("all_packages_remove:PASS", source)
        self.assertNotIn("turn/start", source)


if __name__ == "__main__":
    unittest.main()
