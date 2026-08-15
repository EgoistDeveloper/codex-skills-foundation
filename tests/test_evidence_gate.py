from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("evidence_gate", ROOT / "scripts/evidence_gate.py")
module = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(module)


class EvidenceGateTests(unittest.TestCase):
    def fixture(self, name: str) -> dict:
        return json.loads((ROOT / f"examples/{name}").read_text(encoding="utf-8"))

    def contract(self) -> dict:
        return self.fixture("task-contract.static-validation.json")

    def test_pass_fixture_against_contract(self) -> None:
        self.assertEqual(
            module.validate(self.fixture("completion-evidence.pass.json"), self.contract()),
            [],
        )

    def test_fail_fixture(self) -> None:
        self.assertTrue(module.validate(self.fixture("completion-evidence.fail.json")))

    def test_partial_and_not_run_cannot_claim_complete(self) -> None:
        errors = module.validate(self.fixture("completion-evidence.partial.json"))
        self.assertTrue(any("PARTIAL" in item for item in errors))
        self.assertTrue(any("NOT_RUN" in item for item in errors))

    def test_duplicate_criteria_are_rejected(self) -> None:
        data = self.fixture("completion-evidence.pass.json")
        data["items"].append(dict(data["items"][0]))
        self.assertTrue(any("duplicated" in item for item in module.validate(data)))

    def test_contract_detects_omitted_acceptance(self) -> None:
        data = self.fixture("completion-evidence.pass.json")
        data["items"].pop()
        errors = module.validate(data, self.contract())
        self.assertTrue(any("missing from evidence" in item for item in errors))

    def test_contract_detects_task_mismatch(self) -> None:
        data = self.fixture("completion-evidence.pass.json")
        data["task_id"] = "other-task"
        errors = module.validate(data, self.contract())
        self.assertTrue(any("does not match" in item for item in errors))


if __name__ == "__main__":
    unittest.main()
