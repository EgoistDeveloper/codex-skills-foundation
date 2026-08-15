from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "validate_repository", ROOT / "scripts/validate_repository.py"
)
module = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(module)


class RepositoryValidatorTests(unittest.TestCase):
    def test_checked_in_examples_match_their_contract(self) -> None:
        report = module.Report()
        module.validate_examples(report)
        self.assertEqual(report.errors, [])
        self.assertEqual(report.warnings, [])

    def test_synthetic_eval_fixture_has_traceable_identity(self) -> None:
        report = module.Report()
        catalog = module.load_json(ROOT / "catalog/plugins.json", report)
        self.assertIsInstance(catalog, dict)
        case_ids = module.validate_eval_cases(catalog, report)
        module.validate_eval_fixture(case_ids, report)
        self.assertEqual(report.errors, [])


if __name__ == "__main__":
    unittest.main()
