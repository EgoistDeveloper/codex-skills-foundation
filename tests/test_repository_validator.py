from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("validate_repository", ROOT / "scripts/validate_repository.py")
module = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(module)


class RepositoryValidatorTests(unittest.TestCase):
    def test_full_repository_validation_is_clean(self) -> None:
        report = module.Report()
        catalog = module.load_json(ROOT / "catalog/plugins.json", report)
        plugins = module.validate_catalog(catalog, report)
        all_skills: set[str] = set()
        provider_schema = ROOT / "schemas/provider/agent-plugins-1.0.0.schema.json"
        for plugin in plugins:
            all_skills.update(module.validate_plugin(plugin, provider_schema, report))
        module.validate_packaged_resource_closure(plugins, report)
        module.validate_marketplaces(plugins, report)
        module.validate_profiles(report)
        module.validate_examples_and_schemas(report)
        module.validate_evals(plugins, all_skills, report)
        module.validate_markdown_links(report)
        module.validate_security_and_placeholders(report)
        module.validate_root_contract(report)
        self.assertEqual(report.errors, [])
        self.assertEqual(report.warnings, [])

    def test_local_dependency_directories_are_excluded(self) -> None:
        for relative in (
            ".venv/Lib/site-packages/example.py",
            "venv/lib/python/site-packages/example.py",
            "node_modules/example/index.js",
            ".tox/example/lib/site-packages/example.py",
            ".eval-runs/codex-live-smoke/example/final-message.md",
        ):
            self.assertTrue(module.is_excluded_path(ROOT / relative))
        self.assertFalse(
            module.is_excluded_path(
                ROOT / "plugins/engineering-foundation-core/skills/task-contract/SKILL.md"
            )
        )

    def test_catalog_matches_five_modular_packages(self) -> None:
        catalog = json.loads((ROOT / "catalog/plugins.json").read_text(encoding="utf-8"))
        names = [plugin["name"] for plugin in catalog["plugins"]]
        self.assertEqual(
            names,
            [
                "engineering-foundation-core",
                "engineering-foundation-laravel",
                "engineering-foundation-design",
                "engineering-foundation-cloud",
                "engineering-foundation-authoring",
            ],
        )

    def test_pinned_agent_plugins_schema_is_valid(self) -> None:
        schema = json.loads(
            (ROOT / "schemas/provider/agent-plugins-1.0.0.schema.json").read_text(encoding="utf-8")
        )
        module.Draft202012Validator.check_schema(schema)


if __name__ == "__main__":
    unittest.main()
