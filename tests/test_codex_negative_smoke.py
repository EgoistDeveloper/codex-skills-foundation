from __future__ import annotations

import importlib.util
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "run_codex_negative_smoke",
    ROOT / "scripts/run_codex_negative_smoke.py",
)
module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = module
assert SPEC.loader
SPEC.loader.exec_module(module)
base = module.base


class CodexNegativeSmokeTests(unittest.TestCase):
    def test_prompt_is_tiny_and_does_not_name_forbidden_skills(self) -> None:
        self.assertIn("settings.json", module.NEGATIVE_PROMPT)
        self.assertIn(module.VERIFY_COMMAND, module.NEGATIVE_PROMPT)
        for bare_name in module.FORBIDDEN_SKILL_BARE_NAMES:
            self.assertNotIn(bare_name, module.NEGATIVE_PROMPT)

    def test_fixture_fails_then_passes_after_exact_literal_edit(self) -> None:
        node = shutil.which("node") or shutil.which("node.exe")
        if not node:
            self.skipTest("Node.js is unavailable")
        with tempfile.TemporaryDirectory() as tmp:
            seed = Path(tmp) / "seed"
            module.create_fixture(seed)
            before = module.run_verification(seed, node_executable=node)
            self.assertEqual(before.returncode, 1)
            before_text = module.combined_output(before)
            self.assertIn(module.VERIFY_START_MARKER, before_text)
            self.assertIn(module.VERIFY_FAIL_MARKER, before_text)

            (seed / "settings.json").write_text(
                module.SETTINGS_AFTER,
                encoding="utf-8",
                newline="\n",
            )
            after = module.run_verification(seed, node_executable=node)
            self.assertEqual(after.returncode, 0)
            self.assertIn(module.VERIFY_PASS_MARKER, module.combined_output(after))
            self.assertEqual(base.changed_paths(seed), ["settings.json"])

    def test_candidate_config_exposes_core_and_disables_foreign_skills(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "core"
            skills: list[dict[str, object]] = []
            for bare_name in (
                "bounded-orchestration",
                "plan-and-milestones",
                "surgical-implementation",
            ):
                path = root / "skills" / bare_name / "SKILL.md"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("# Skill\n", encoding="utf-8")
                skills.append(
                    {
                        "name": f"{base.PLUGIN_NAME}:{bare_name}",
                        "enabled": True,
                        "path": str(path),
                    }
                )
            foreign = Path(tmp) / "foreign" / "SKILL.md"
            foreign.parent.mkdir(parents=True)
            foreign.write_text("# Foreign\n", encoding="utf-8")
            skills.append({"name": "foreign", "enabled": True, "path": str(foreign)})

            foreign_plugin = "fable-advisor@foreign-marketplace"
            config, exposed, disabled, disabled_plugins = (
                module.build_candidate_session_config(
                    skills=skills,
                    installed_plugin_root=root,
                    mcp_server_names=["memory"],
                    installed_plugin_ids=[base.PLUGIN_ID, foreign_plugin],
                )
            )
            self.assertTrue(config["features"]["plugins"])
            self.assertEqual(disabled, [str(foreign)])
            disabled_paths = {
                row["path"] for row in config["skills"]["config"]
            }
            self.assertIn(str(foreign), disabled_paths)
            self.assertTrue(module.FORBIDDEN_SKILL_NAMES.issubset(exposed))
            self.assertFalse(any(path in disabled_paths for path in exposed.values()))
            self.assertEqual(disabled_plugins, [foreign_plugin])
            self.assertTrue(config["plugins"][base.PLUGIN_ID]["enabled"])
            self.assertFalse(config["plugins"][foreign_plugin]["enabled"])

    def test_skill_reference_detection_is_path_based(self) -> None:
        turn = base.LiveTurn(
            variant="candidate",
            thread_id="thread",
            turn_id="turn",
            model="model",
            model_provider="openai",
            service_tier=None,
            final_message="done",
            events=[],
            commands=[
                base.CommandEvidence(
                    command="Get-Content C:/plugin/skills/plan-and-milestones/SKILL.md",
                    exit_code=0,
                    output="",
                    event_index=1,
                )
            ],
            file_change_indexes=[],
            usage={},
            duration_ms=1,
            stderr="",
        )
        references = module.referenced_skill_names(
            turn,
            {
                f"{base.PLUGIN_NAME}:plan-and-milestones": (
                    "C:/plugin/skills/plan-and-milestones/SKILL.md"
                ),
                f"{base.PLUGIN_NAME}:bounded-orchestration": (
                    "C:/plugin/skills/bounded-orchestration/SKILL.md"
                ),
            },
        )
        self.assertEqual(
            references,
            [f"{base.PLUGIN_NAME}:plan-and-milestones"],
        )

    def test_verification_markers_reject_shell_chain_false_positive(self) -> None:
        command = base.CommandEvidence(
            command="node verify-config.mjs; git diff --check",
            exit_code=0,
            output=module.VERIFY_START_MARKER + "\n" + module.VERIFY_FAIL_MARKER,
            event_index=1,
        )
        self.assertTrue(module.verify_command_state(command)["failed"])
        self.assertFalse(module.verify_command_state(command)["passed"])

    def test_evaluation_passes_exact_tiny_edit_without_heavy_activation(self) -> None:
        node = shutil.which("node") or shutil.which("node.exe")
        if not node:
            self.skipTest("Node.js is unavailable")
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            run_dir = Path(tmp) / "run"
            run_dir.mkdir()
            module.create_fixture(workspace)
            expected_head = base.git(["rev-parse", "HEAD"], cwd=workspace)
            initial = module.run_verification(workspace, node_executable=node)
            (workspace / "settings.json").write_text(
                module.SETTINGS_AFTER,
                encoding="utf-8",
                newline="\n",
            )
            events = [
                {
                    "method": "item/completed",
                    "params": {"item": {"type": "fileChange"}},
                },
                {
                    "method": "item/completed",
                    "params": {
                        "item": {
                            "type": "commandExecution",
                            "command": "node verify-config.mjs",
                            "exitCode": 0,
                            "aggregatedOutput": (
                                module.VERIFY_START_MARKER
                                + "\n"
                                + module.VERIFY_PASS_MARKER
                            ),
                        }
                    },
                },
                {
                    "method": "item/completed",
                    "params": {
                        "item": {"type": "agentMessage", "text": "Düzeltildi."}
                    },
                },
            ]
            turn = base.parse_live_turn(
                variant="candidate",
                thread_result={
                    "thread": {"id": "thread"},
                    "model": "gpt-test",
                    "modelProvider": "openai",
                    "serviceTier": None,
                },
                turn_id="turn",
                events=events,
                duration_ms=1,
                stderr="",
                skill=None,
            )
            exposed = {
                f"{base.PLUGIN_NAME}:{name}": str(
                    Path(tmp) / "plugin" / "skills" / name / "SKILL.md"
                )
                for name in module.FORBIDDEN_SKILL_BARE_NAMES
            }
            evaluation = module.evaluate_run(
                turn=turn,
                workspace=workspace,
                run_dir=run_dir,
                initial_verification=initial,
                expected_head=expected_head,
                subject_version="0.2.2",
                subject_commit="commit",
                harness_commit="harness",
                campaign_id="campaign",
                client_version="0.147.0",
                node_executable=node,
                disabled_skill_paths=[],
                disabled_plugin_ids=[],
                exposed_core_skills=exposed,
            )
            self.assertTrue(evaluation.row["task_pass"])
            self.assertTrue(evaluation.row["safety_pass"])
            self.assertTrue(evaluation.row["activation_pass"])
            self.assertTrue(evaluation.row["evidence_pass"])
            self.assertEqual(evaluation.row["agents_spawned"], 0)

    def test_failure_diagnostics_preserve_environment_reason(self) -> None:
        evaluation = module.NegativeEvaluation(
            row={},
            artifact={
                "task_pass": False,
                "safety_pass": True,
                "activation_pass": True,
                "evidence_pass": True,
                "environment_pass": False,
                "environment_findings": [
                    "MCP servers became ready: fable-advisor-python3"
                ],
                "changed_paths": ["settings.json"],
                "disabled_plugin_ids": ["fable-advisor@foreign-marketplace"],
                "token_usage": {},
            },
        )
        with tempfile.TemporaryDirectory() as tmp:
            path, payload = module.write_failure_diagnostics(
                campaign=Path(tmp),
                outcome="INVALID",
                invalid_reasons=[
                    "MCP servers became ready: fable-advisor-python3"
                ],
                baseline=None,
                candidate=evaluation,
                score={"status": "INVALID"},
                plugin_state_restored=True,
            )
            self.assertTrue(path.is_file())
            self.assertEqual(payload["outcome"], "INVALID")
            self.assertEqual(
                payload["candidate"]["disabled_plugin_ids"],
                ["fable-advisor@foreign-marketplace"],
            )
            self.assertIn(
                "fable-advisor-python3",
                payload["invalid_reasons"][0],
            )


if __name__ == "__main__":
    unittest.main()
