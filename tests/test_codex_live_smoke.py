from __future__ import annotations

import importlib.util
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "run_codex_live_smoke",
    ROOT / "scripts/run_codex_live_smoke.py",
)
module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = module
assert SPEC.loader
SPEC.loader.exec_module(module)


class CodexLiveSmokeTests(unittest.TestCase):
    def test_version_parser_and_minimum_shape(self) -> None:
        self.assertEqual(module.parse_version("codex-cli 0.147.0"), (0, 147, 0))
        with self.assertRaises(module.HarnessError):
            module.parse_version("Codex unknown")

    def test_fixture_starts_failing_and_passes_after_supported_fix(self) -> None:
        node = shutil.which("node") or shutil.which("node.exe")
        if not node:
            self.skipTest("Node.js is unavailable")
        with tempfile.TemporaryDirectory() as tmp:
            seed = Path(tmp) / "seed"
            module.create_fixture(seed)
            before = module.run_tests(seed, node_executable=node)
            self.assertEqual(before.returncode, 1)
            before_text = before.stdout + before.stderr
            self.assertIn(module.TEST_START_MARKER, before_text)
            self.assertIn(module.TEST_FAIL_MARKER, before_text)

            source = (seed / "retry_after.mjs").read_text(encoding="utf-8")
            source = source.replace("Number(candidate) / 1000", "Number(candidate)")
            (seed / "retry_after.mjs").write_text(source, encoding="utf-8", newline="\n")

            after = module.run_tests(seed, node_executable=node)
            self.assertEqual(after.returncode, 0)
            after_text = after.stdout + after.stderr
            self.assertIn(module.TEST_PASS_MARKER, after_text)
            self.assertEqual(module.changed_paths(seed), ["retry_after.mjs"])

    def test_skill_selection_requires_namespaced_enabled_installed_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plugin_root = Path(tmp) / "plugin"
            skill_path = plugin_root / "skills" / "systematic-debugging" / "SKILL.md"
            skill_path.parent.mkdir(parents=True)
            skill_path.write_text("# Systematic Debugging\n", encoding="utf-8")

            skills = [
                {
                    "name": module.SKILL_QUALIFIED_NAME,
                    "enabled": True,
                    "path": str(skill_path),
                }
            ]
            self.assertEqual(
                module.select_skill(skills, installed_plugin_root=plugin_root),
                (module.SKILL_QUALIFIED_NAME, str(skill_path)),
            )

            skills[0]["name"] = module.SKILL_BARE_NAME
            with self.assertRaises(module.HarnessError):
                module.select_skill(skills, installed_plugin_root=plugin_root)

    def test_turn_parser_extracts_commands_changes_messages_and_usage(self) -> None:
        events = [
            {
                "method": "item/completed",
                "params": {
                    "item": {
                        "type": "commandExecution",
                        "command": "node smoke-test.mjs",
                        "exitCode": 1,
                        "aggregatedOutput": (
                            module.TEST_START_MARKER + "\n" + module.TEST_FAIL_MARKER
                        ),
                    }
                },
            },
            {
                "method": "item/completed",
                "params": {"item": {"type": "fileChange"}},
            },
            {
                "method": "thread/tokenUsage/updated",
                "params": {
                    "tokenUsage": {
                        "total": {
                            "totalTokens": 1234,
                            "inputTokens": 1000,
                            "cachedInputTokens": 750,
                            "outputTokens": 234,
                            "reasoningOutputTokens": 50,
                        }
                    }
                },
            },
            {
                "method": "item/completed",
                "params": {
                    "item": {
                        "type": "agentMessage",
                        "text": "Düzeltme tamamlandı.",
                    }
                },
            },
        ]
        turn = module.parse_live_turn(
            variant="candidate",
            thread_result={
                "thread": {"id": "thread-1"},
                "model": "gpt-test",
                "modelProvider": "openai",
                "serviceTier": None,
            },
            turn_id="turn-1",
            events=events,
            duration_ms=100,
            stderr="",
            skill=(module.SKILL_QUALIFIED_NAME, "C:/plugin/SKILL.md"),
        )
        self.assertEqual(turn.thread_id, "thread-1")
        self.assertTrue(module.test_command_state(turn.commands[0])["failed"])
        self.assertEqual(turn.file_change_indexes, [1])
        self.assertEqual(turn.final_message, "Düzeltme tamamlandı.")
        self.assertEqual(module.usage_total_tokens(turn.usage), 1234)
        self.assertEqual(module.usage_breakdown(turn.usage)["uncached_input_tokens"], 250)

    def test_test_markers_prevent_shell_chain_false_positive(self) -> None:
        failed_but_shell_zero = module.CommandEvidence(
            command="node smoke-test.mjs; git diff --check",
            exit_code=0,
            output=module.TEST_START_MARKER + "\n" + module.TEST_FAIL_MARKER,
            event_index=1,
        )
        self.assertTrue(module.test_command_state(failed_but_shell_zero)["failed"])
        self.assertFalse(module.test_command_state(failed_but_shell_zero)["passed"])

        command_not_found = module.CommandEvidence(
            command="node smoke-test.mjs",
            exit_code=1,
            output="node: command not found",
            event_index=2,
        )
        self.assertFalse(module.test_command_state(command_not_found)["failed"])
        self.assertFalse(module.test_command_state(command_not_found)["started"])

    def test_session_config_disables_ambient_capabilities(self) -> None:
        config = module.build_session_config(
            disabled_skill_paths=["C:/skills/one/SKILL.md"],
            mcp_server_names=["memory", "node_repl"],
        )
        self.assertEqual(
            config["features"],
            {
                "plugins": False,
                "apps": False,
                "memories": False,
                "js_repl": False,
            },
        )
        self.assertFalse(config["skills"]["config"][0]["enabled"])
        self.assertFalse(config["mcp_servers"]["memory"]["enabled"])

    def test_environment_findings_detect_mcp_and_foreign_skill_reads(self) -> None:
        turn = module.LiveTurn(
            variant="baseline",
            thread_id="thread",
            turn_id="turn",
            model="model",
            model_provider="openai",
            service_tier=None,
            final_message="done",
            events=[
                {
                    "method": "mcpServer/startupStatus/updated",
                    "params": {"name": "memory", "status": "ready"},
                }
            ],
            commands=[
                module.CommandEvidence(
                    command="Get-Content C:/skills/other/SKILL.md",
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
        findings = module.runtime_environment_findings(
            turn=turn,
            disabled_skill_paths=["C:/skills/other/SKILL.md"],
            allowed_skill_path=None,
        )
        self.assertTrue(any("MCP servers became ready" in item for item in findings))
        self.assertTrue(any("disabled skill path" in item for item in findings))


if __name__ == "__main__":
    unittest.main()
