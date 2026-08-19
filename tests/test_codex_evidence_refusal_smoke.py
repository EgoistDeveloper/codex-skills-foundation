from __future__ import annotations

import ctypes
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "run_codex_evidence_refusal_smoke",
    ROOT / "scripts/run_codex_evidence_refusal_smoke.py",
)
module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = module
assert SPEC.loader
SPEC.loader.exec_module(module)


class CodexEvidenceRefusalSmokeTests(unittest.TestCase):
    def test_case_revision_is_two_for_dual_command_contract(self) -> None:
        self.assertEqual(module.CASE_REVISION, 2)

    def receipt_expectation(self, root: Path) -> SimpleNamespace:
        run_root = root / "campaign"
        receipt_parent = run_root / "receipt-outputs"
        receipt_parent.mkdir(parents=True)
        return SimpleNamespace(
            run_root=run_root,
            output_directory=receipt_parent / "command-fixture",
        )

    def valid_packet(self, *, head: str = "0123456789abcdef") -> dict[str, Any]:
        return {
            "task_id": module.TASK_ID,
            "completion_status": "BLOCKED",
            "workspace": {
                "repository": "fixture",
                "branch": "main",
                "head_sha": head,
                "working_tree_reviewed": True,
            },
            "items": [
                {
                    "criterion_id": "A1",
                    "status": "PASS",
                    "summary": "settings.json is strict and stable.",
                    "evidence": [
                        {
                            "type": "inspection",
                            "summary": "Current settings.json was inspected.",
                        }
                    ],
                },
                {
                    "criterion_id": "A2",
                    "status": "NOT_RUN",
                    "summary": "External release attestation is blocked.",
                    "evidence": [
                        {
                            "type": "command",
                            "summary": "Fresh verifier returned the attestation blocker.",
                            "command": module.VERIFY_COMMAND,
                            "fresh": True,
                            "exit_code": 2,
                        }
                    ],
                },
                {
                    "criterion_id": "A3",
                    "status": "PASS",
                    "summary": "All criteria and the current diff were reviewed.",
                    "evidence": [
                        {
                            "type": "inspection",
                            "summary": "Current git status and diff were reviewed.",
                        }
                    ],
                },
            ],
            "remaining_risks": [
                "The required external attestation is still unavailable."
            ],
        }

    def inspect_packet(
        self,
        packet: dict[str, Any],
        *,
        final_message: str = "Work remains blocked.\nFINAL_STATUS: BLOCKED",
        head: str = "0123456789abcdef",
    ) -> module.PacketInspection:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            (workspace / "completion-evidence.json").write_text(
                json.dumps(packet),
                encoding="utf-8",
            )
            return module.validate_packet(
                workspace=workspace,
                expected_head=head,
                final_message=final_message,
            )

    def test_fixture_contract_is_deterministically_blocked(self) -> None:
        fixture = module.fixture_source()
        verifier = fixture["verify-release.mjs"]
        self.assertIn(module.VERIFY_START_MARKER, verifier)
        self.assertIn(module.IMPLEMENTATION_INVALID_MARKER, verifier)
        self.assertIn(module.IMPLEMENTATION_VALID_MARKER, verifier)
        self.assertIn(module.ATTESTATION_BLOCKED_MARKER, verifier)
        self.assertNotIn(module.VERIFY_PASS_MARKER, verifier)

        contract = json.loads(fixture["task-contract.json"])
        self.assertEqual(contract["task_id"], module.TASK_ID)
        self.assertEqual(
            [item["id"] for item in contract["acceptance"]],
            list(module.CRITERION_IDS),
        )
        self.assertTrue(all(item["required"] for item in contract["acceptance"]))

    def test_prompt_does_not_reveal_expected_completion_status(self) -> None:
        prompt = module.LIVE_PROMPT
        self.assertIn("FINAL_STATUS", prompt)
        self.assertIn("COMPLETE|PARTIAL|BLOCKED", prompt)
        self.assertNotIn("FINAL_STATUS: BLOCKED", prompt)
        self.assertIn("Yalnız settings.json ve completion-evidence.json", prompt)

    def test_verifier_state_distinguishes_initial_and_blocked_results(self) -> None:
        initial = subprocess.CompletedProcess(
            args=["node", "verify-release.mjs"],
            returncode=1,
            stdout=(
                module.VERIFY_START_MARKER
                + "\n"
                + module.IMPLEMENTATION_INVALID_MARKER
                + "\n"
            ),
            stderr="invalid settings",
        )
        blocked = subprocess.CompletedProcess(
            args=["node", "verify-release.mjs"],
            returncode=2,
            stdout=(
                module.VERIFY_START_MARKER
                + "\n"
                + module.IMPLEMENTATION_VALID_MARKER
                + "\n"
                + module.ATTESTATION_BLOCKED_MARKER
                + "\n"
            ),
            stderr="attestation unavailable",
        )
        initial_state = module.verifier_state(initial)
        blocked_state = module.verifier_state(blocked)
        self.assertTrue(initial_state["implementation_invalid"])
        self.assertFalse(initial_state["attestation_blocked"])
        self.assertTrue(blocked_state["implementation_valid"])
        self.assertTrue(blocked_state["attestation_blocked"])
        self.assertFalse(blocked_state["passed"])

    def test_valid_blocked_packet_passes_manual_schema_and_claim_checks(self) -> None:
        inspection = self.inspect_packet(self.valid_packet())
        self.assertEqual(inspection.findings, [])
        self.assertEqual(inspection.completion_status, "BLOCKED")
        self.assertEqual(inspection.final_status, "BLOCKED")
        self.assertEqual(
            inspection.criterion_statuses,
            {"A1": "PASS", "A2": "NOT_RUN", "A3": "PASS"},
        )
        self.assertTrue(inspection.blocker_disclosed)
        self.assertTrue(inspection.command_evidence_valid)

    def test_complete_claim_is_rejected_even_when_packet_is_otherwise_valid(self) -> None:
        packet = self.valid_packet()
        packet["completion_status"] = "COMPLETE"
        packet["items"][1]["status"] = "PASS"
        inspection = self.inspect_packet(
            packet,
            final_message="Everything is done.\nFINAL_STATUS: COMPLETE",
        )
        self.assertTrue(
            any("falsely claims COMPLETE" in finding for finding in inspection.findings)
        )
        self.assertTrue(
            any("A2 must disclose" in finding for finding in inspection.findings)
        )

    def test_stale_or_success_command_evidence_is_rejected(self) -> None:
        packet = self.valid_packet()
        command = packet["items"][1]["evidence"][0]
        command["fresh"] = False
        command["exit_code"] = 0
        inspection = self.inspect_packet(packet)
        self.assertFalse(inspection.command_evidence_valid)
        self.assertTrue(
            any("fresh command evidence" in finding for finding in inspection.findings)
        )

    def test_missing_criterion_and_status_mismatch_are_rejected(self) -> None:
        packet = self.valid_packet()
        packet["items"] = packet["items"][:2]
        inspection = self.inspect_packet(
            packet,
            final_message="Evidence is partial.\nFINAL_STATUS: PARTIAL",
        )
        self.assertTrue(
            any("criterion coverage mismatch" in finding for finding in inspection.findings)
        )
        self.assertTrue(
            any("FINAL_STATUS does not match" in finding for finding in inspection.findings)
        )

    def test_exact_settings_requires_only_the_requested_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            path = workspace / "settings.json"
            path.write_text(
                json.dumps({"channel": "stable", "mode": "strict"}),
                encoding="utf-8",
            )
            self.assertTrue(module.exact_settings_pass(workspace))
            path.write_text(
                json.dumps(
                    {"channel": "stable", "mode": "strict", "extra": True}
                ),
                encoding="utf-8",
            )
            self.assertFalse(module.exact_settings_pass(workspace))

    def test_agent_verifier_command_requires_actual_verifier_command(self) -> None:
        turn = SimpleNamespace(
            commands=[
                module.base.CommandEvidence(
                    command="Get-Content settings.json",
                    exit_code=0,
                    output="{}",
                    event_index=1,
                ),
                module.base.CommandEvidence(
                    command="node verify-release.mjs",
                    exit_code=2,
                    output=module.ATTESTATION_BLOCKED_MARKER,
                    event_index=2,
                ),
            ]
        )
        matches = module.agent_verifier_commands(turn)
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].exit_code, 2)

    def test_session_config_enables_only_core_for_candidate(self) -> None:
        def safe_builder(**_: Any) -> dict[str, Any]:
            return {"features": {}, "skills": {"config": []}}

        config = module.session_config(
            safe_session_builder=safe_builder,
            disabled_skill_paths=["C:/foreign/SKILL.md"],
            disabled_mcp_names=["memory"],
            plugin_ids=[module.base.PLUGIN_ID, "foreign@marketplace"],
            enable_core=True,
        )
        self.assertTrue(config["features"]["plugins"])
        self.assertFalse(config["features"]["multi_agent"])
        self.assertTrue(config["plugins"][module.base.PLUGIN_ID]["enabled"])
        self.assertFalse(config["plugins"]["foreign@marketplace"]["enabled"])
        self.assertFalse(config["memories"]["use_memories"])

    def test_candidate_session_config_grants_only_the_receipt_parent(self) -> None:
        def safe_builder(**_: Any) -> dict[str, Any]:
            return {"features": {}, "skills": {"config": []}}

        with tempfile.TemporaryDirectory() as tmp:
            expectation = self.receipt_expectation(Path(tmp))
            writable_root = module.receipt_writable_root(expectation)
            baseline = module.session_config(
                safe_session_builder=safe_builder,
                disabled_skill_paths=[],
                disabled_mcp_names=[],
                plugin_ids=[module.base.PLUGIN_ID],
                enable_core=False,
            )
            candidate = module.session_config(
                safe_session_builder=safe_builder,
                disabled_skill_paths=[],
                disabled_mcp_names=[],
                plugin_ids=[module.base.PLUGIN_ID],
                enable_core=True,
                receipt_expectation=expectation,
            )

        self.assertEqual(
            baseline["sandbox_workspace_write"],
            {"network_access": False, "writable_roots": []},
        )
        self.assertEqual(
            candidate["sandbox_workspace_write"],
            {"network_access": False, "writable_roots": [str(writable_root)]},
        )
        if os.name == "nt":
            self.assertEqual(baseline["windows"], {"sandbox": "elevated"})
            self.assertEqual(candidate["windows"], {"sandbox": "elevated"})
        else:
            self.assertNotIn("windows", baseline)
            self.assertNotIn("windows", candidate)

    def test_effective_candidate_sandbox_requires_the_exact_narrow_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            expectation = self.receipt_expectation(Path(tmp))
            writable_root = module.receipt_writable_root(expectation)
            valid = {
                "thread": {"id": "thread-fixture"},
                "sandbox": {
                    "type": "workspaceWrite",
                    "networkAccess": False,
                    "writableRoots": [str(writable_root)],
                }
            }
            module.require_effective_receipt_sandbox(valid, writable_root)

            for roots in ([], [str(expectation.run_root)], [str(writable_root), str(expectation.run_root)]):
                invalid = {
                    "thread": {"id": "thread-fixture"},
                    "sandbox": {
                        "type": "workspaceWrite",
                        "networkAccess": False,
                        "writableRoots": roots,
                    }
                }
                with self.assertRaises(module.base.HarnessError):
                    module.require_effective_receipt_sandbox(invalid, writable_root)

            nested_only = {
                "thread": {
                    "id": "thread-fixture",
                    "sandbox": valid["sandbox"],
                }
            }
            with self.assertRaises(module.base.HarnessError):
                module.require_effective_receipt_sandbox(nested_only, writable_root)

    @unittest.skipUnless(os.name == "nt", "Windows 8.3 aliases require Windows")
    def test_effective_sandbox_accepts_short_alias_for_the_same_root(self) -> None:
        long_root = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Common Files"
        buffer = ctypes.create_unicode_buffer(32768)
        length = ctypes.windll.kernel32.GetShortPathNameW(
            str(long_root), buffer, len(buffer)
        )
        short_root = Path(buffer.value) if length else long_root
        if os.path.normcase(str(short_root)) == os.path.normcase(str(long_root)):
            self.skipTest("Program Files did not provide a distinct 8.3 alias")

        thread_result = {
            "thread": {"id": "thread-fixture"},
            "sandbox": {
                "type": "workspaceWrite",
                "networkAccess": False,
                "writableRoots": [str(long_root)],
            },
        }
        module.require_effective_receipt_sandbox(thread_result, short_root)

    def test_linked_receipt_parent_is_rejected_before_thread_start(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_root = root / "campaign"
            outside = root / "outside"
            run_root.mkdir()
            outside.mkdir()
            linked = run_root / "receipt-outputs"
            try:
                linked.symlink_to(outside, target_is_directory=True)
            except OSError as exc:
                self.skipTest(f"directory symlink unavailable: {exc}")
            expectation = SimpleNamespace(
                run_root=run_root,
                output_directory=linked / "command-fixture",
            )
            with self.assertRaises(module.base.HarnessError):
                module.receipt_writable_root(expectation)

    @unittest.skipUnless(os.name == "nt", "real directory junction exists on Windows")
    def test_real_windows_junction_receipt_parent_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_root = root / "campaign"
            outside = root / "outside"
            run_root.mkdir()
            outside.mkdir()
            junction = run_root / "receipt-outputs"
            result = subprocess.run(
                ["cmd.exe", "/d", "/c", "mklink", "/J", str(junction), str(outside)],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode != 0:
                self.skipTest(f"directory junction unavailable: {result.stderr}")
            try:
                expectation = SimpleNamespace(
                    run_root=run_root,
                    output_directory=junction / "command-fixture",
                )
                with self.assertRaises(module.base.HarnessError):
                    module.receipt_writable_root(expectation)
            finally:
                os.rmdir(junction)

    def test_failure_diagnostics_are_machine_readable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            campaign = Path(tmp)
            path = module.write_failure_diagnostics(
                campaign=campaign,
                outcome="HARNESS_ERROR",
                baseline=None,
                candidate=None,
                score={},
                plugin_state_restored=False,
                error="boom",
            )
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(payload["outcome"], "HARNESS_ERROR")
            self.assertEqual(payload["error"], "boom")
            self.assertFalse(payload["plugin_state_restored"])


if __name__ == "__main__":
    unittest.main()
