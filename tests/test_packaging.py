from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("package_plugins", ROOT / "scripts/package_plugins.py")
module = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(module)


class PackagingTests(unittest.TestCase):
    def test_each_plugin_builds_a_safe_deterministic_archive(self) -> None:
        catalog = json.loads((ROOT / "catalog/plugins.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            for plugin in catalog["plugins"]:
                archive, first_digest = module.build_archive(plugin, output)
                _, second_digest = module.build_archive(plugin, output)
                self.assertEqual(first_digest, second_digest)
                with zipfile.ZipFile(archive) as zf:
                    names = zf.namelist()
                    self.assertIn("plugin.json", names)
                    self.assertIn(".codex-plugin/plugin.json", names)
                    self.assertIn(".claude-plugin/plugin.json", names)
                    self.assertTrue(any(name.endswith("/SKILL.md") for name in names))
                    self.assertTrue(all(not Path(name).is_absolute() and ".." not in Path(name).parts for name in names))


if __name__ == "__main__":
    unittest.main()
