from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "run_codex_live_smoke",
    ROOT / "scripts/run_codex_live_smoke.py",
)
module = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(module)


class CodexLiveSmokeTests(unittest.TestCase):
    def test_version_parser_and_minimum_shape(self) -> None:
        self.assertEqual(module.parse_version("codex-cli 0.147.0"), (0, 147, 0))
        with self.assertRaises(module.HarnessError):
            module.parse_version("Codex unknown")

    def test_fixture_starts_failing_and_passes_after_supported_fix(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            seed = Path(tmp) / "seed"
            module.create_fixture(seed)
            before = module.run_tests(seed)
            self.assertEqual(before.returncode, 1)

            source = (seed / "retry_after.py").read_text(encoding="utf-8")
            source = source.replace("int(candidate) // 1000", "int(candidate)")
            (seed / "retry_after.py").write_text(source, encoding="utf-8", newline="\n")

            after = module.run_tests(seed)
            self.assertEqual(after.returncode, 0)
            self.assertEqual(module.changed_paths(seed), ["retry_after.py"])

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
                        "command": "python -m unittest -v",
                        "exitCode": 1,
                        "aggregatedOutput": "FAIL",
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
                        "total": {"totalTokens": 1234},
                        "last": {"totalTokens": 1234},
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
        self.assertEqual(turn.commands[0].exit_code, 1)
        self.assertEqual(turn.file_change_indexes, [1])
        self.assertEqual(turn.final_message, "Düzeltme tamamlandı.")
        self.assertEqual(module.usage_total_tokens(turn.usage), 1234)


if __name__ == "__main__":
    unittest.main()
