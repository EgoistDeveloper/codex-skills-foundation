from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class EvalCaseTests(unittest.TestCase):
    def test_cases_are_unique_and_reference_skills(self) -> None:
        skills = {p.parent.name for p in ROOT.glob("plugins/*/skills/*/SKILL.md")}
        ids: set[str] = set()
        cases = list((ROOT / "evals/cases").glob("*.json"))
        self.assertGreaterEqual(len(cases), 10)
        for path in cases:
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(path.stem, data["id"])
            self.assertNotIn(data["id"], ids)
            ids.add(data["id"])
            for name in data.get("expected_activation", []) + data.get("forbidden_activation", []):
                self.assertIn(name, skills, path)
            self.assertTrue(data["behavior_assertions"], path)


if __name__ == "__main__":
    unittest.main()
