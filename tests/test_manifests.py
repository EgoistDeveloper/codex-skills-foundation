from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("render_manifests", ROOT / "scripts/render_manifests.py")
module = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(module)


class ManifestTests(unittest.TestCase):
    def test_generated_manifests_match(self) -> None:
        catalog = json.loads((ROOT / "catalog/plugins.json").read_text(encoding="utf-8"))
        for path, expected in module.targets(catalog).items():
            self.assertTrue(path.exists(), path)
            self.assertEqual(path.read_text(encoding="utf-8"), expected, path)

    def test_portable_manifests_are_closed(self) -> None:
        allowed = {"$schema", "name", "version", "description", "author", "homepage", "repository", "license", "keywords", "extensions"}
        for path in ROOT.glob("plugins/*/plugin.json"):
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertFalse(set(data) - allowed, path)


    def test_claude_manifests_declare_schema_and_display_name(self) -> None:
        expected_schema = "https://json.schemastore.org/claude-code-plugin-manifest.json"
        for path in ROOT.glob("plugins/*/.claude-plugin/plugin.json"):
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(data.get("$schema"), expected_schema, path)
            self.assertIsInstance(data.get("displayName"), str, path)
            self.assertTrue(data["displayName"].strip(), path)

    def test_openai_marketplace_has_install_policy(self) -> None:
        data = json.loads((ROOT / ".agents/plugins/marketplace.json").read_text(encoding="utf-8"))
        for entry in data["plugins"]:
            self.assertIn(entry["policy"]["installation"], {"AVAILABLE", "INSTALLED_BY_DEFAULT", "NOT_AVAILABLE"})
            self.assertIn(entry["policy"]["authentication"], {"ON_INSTALL", "ON_FIRST_USE"})
            self.assertTrue(entry["category"])

    def test_publisher_metadata_has_no_placeholder_contact(self) -> None:
        for path in [ROOT / "catalog/plugins.json", ROOT / ".claude-plugin/marketplace.json"]:
            self.assertNotIn("example.invalid", path.read_text(encoding="utf-8"), path)

    def test_packages_have_no_mcp_or_hooks(self) -> None:
        for root in ROOT.glob("plugins/*"):
            self.assertFalse((root / "mcp.json").exists())
            self.assertFalse((root / ".mcp.json").exists())
            self.assertFalse((root / "hooks").exists())
            self.assertFalse((root / "hooks.json").exists())


if __name__ == "__main__":
    unittest.main()
