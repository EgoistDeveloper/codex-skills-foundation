from __future__ import annotations

import importlib.util
import json
import tempfile
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
        self.assertEqual(module.validate(self.fixture("completion-evidence.pass.json"), self.contract()), [])

    def test_complete_without_contract_is_rejected(self) -> None:
        errors = module.validate(self.fixture("completion-evidence.pass.json"))
        self.assertTrue(any("requires --contract" in item for item in errors))

    def test_fail_and_partial_cannot_pass_completion_gate(self) -> None:
        fail_errors = module.validate(self.fixture("completion-evidence.fail.json"), self.contract())
        self.assertTrue(any("BLOCKED" in item for item in fail_errors))
        self.assertTrue(any("required criterion A2" in item for item in fail_errors))
        partial_errors = module.validate(self.fixture("completion-evidence.partial.json"), self.contract())
        self.assertTrue(any("PARTIAL" in item for item in partial_errors))
        self.assertTrue(any("required criterion A2" in item for item in partial_errors))

    def test_duplicate_and_omitted_criteria_are_rejected(self) -> None:
        data = self.fixture("completion-evidence.pass.json")
        data["items"].append(dict(data["items"][0]))
        self.assertTrue(any("duplicated" in item for item in module.validate(data, self.contract())))

        data = self.fixture("completion-evidence.pass.json")
        data["items"].pop()
        errors = module.validate(data, self.contract())
        self.assertTrue(any("missing from evidence" in item for item in errors))

    def test_task_mismatch_is_rejected(self) -> None:
        data = self.fixture("completion-evidence.pass.json")
        data["task_id"] = "other-task"
        errors = module.validate(data, self.contract())
        self.assertTrue(any("does not match" in item for item in errors))

    def test_stale_or_failed_command_cannot_support_pass(self) -> None:
        data = self.fixture("completion-evidence.pass.json")
        command = data["items"][0]["evidence"][0]
        command["fresh"] = False
        command["exit_code"] = 1
        errors = module.validate(data, self.contract())
        self.assertTrue(any("fresh must be true" in item for item in errors))
        self.assertTrue(any("exit_code is 1" in item for item in errors))

    def test_command_only_fields_are_rejected_on_inspection(self) -> None:
        data = self.fixture("completion-evidence.pass.json")
        data["items"][0]["evidence"][0] = {
            "type": "inspection",
            "summary": "Inspected output.",
            "exit_code": 0,
        }
        errors = module.validate(data, self.contract())
        self.assertTrue(any("only valid for command" in item for item in errors))

    def test_command_receipt_binding_is_closed_and_matches_exit_code(self) -> None:
        data = self.fixture("completion-evidence.pass.json")
        command = data["items"][0]["evidence"][0]
        command["receipt"] = {
            "run_id": "run-1",
            "command_id": "command-1",
            "payload_sha256": "a" * 64,
            "child_exit_code": 0,
        }
        command["verifier_argv"] = ["python", "verify.py"]
        self.assertEqual(module.validate(data, self.contract()), [])

        missing_argv = self.fixture("completion-evidence.pass.json")
        missing_argv["items"][0]["evidence"][0]["receipt"] = {
            "run_id": "run-1",
            "command_id": "command-1",
            "payload_sha256": "a" * 64,
            "child_exit_code": 0,
        }
        errors = module.validate(missing_argv, self.contract())
        self.assertTrue(any("verifier_argv" in error for error in errors), errors)

        argv_without_receipt = self.fixture("completion-evidence.pass.json")
        argv_without_receipt["items"][0]["evidence"][0]["verifier_argv"] = [
            "python",
            "verify.py",
        ]
        errors = module.validate(argv_without_receipt, self.contract())
        self.assertTrue(any("requires" in error for error in errors), errors)

        for field, value in (
            ("run_id", ""),
            ("command_id", ""),
            ("payload_sha256", "not-a-digest"),
            ("child_exit_code", 1),
        ):
            with self.subTest(field=field):
                invalid = self.fixture("completion-evidence.pass.json")
                invalid["items"][0]["evidence"][0]["receipt"] = {
                    "run_id": "run-1",
                    "command_id": "command-1",
                    "payload_sha256": "a" * 64,
                    "child_exit_code": 0,
                    field: value,
                }
                invalid["items"][0]["evidence"][0]["verifier_argv"] = [
                    "python",
                    "verify.py",
                ]
                self.assertTrue(module.validate(invalid, self.contract()))

    def test_artifact_path_is_bounded_and_must_exist_when_workspace_is_supplied(self) -> None:
        data = self.fixture("completion-evidence.pass.json")
        data["items"][0]["evidence"] = [
            {"type": "artifact", "summary": "Report", "artifact_path": "../escape.txt"}
        ]
        errors = module.validate(data, self.contract())
        self.assertTrue(any("inside the workspace" in item for item in errors))

        with tempfile.TemporaryDirectory() as tmp:
            data["items"][0]["evidence"][0]["artifact_path"] = "report.txt"
            errors = module.validate(data, self.contract(), workspace_root=Path(tmp))
            self.assertTrue(any("does not exist" in item for item in errors))
            (Path(tmp) / "report.txt").write_text("ok\n", encoding="utf-8")
            self.assertEqual(module.validate(data, self.contract(), workspace_root=Path(tmp)), [])


if __name__ == "__main__":
    unittest.main()
