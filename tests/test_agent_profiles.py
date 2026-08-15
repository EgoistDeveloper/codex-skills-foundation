from __future__ import annotations

import importlib.util
import tempfile
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("install_agent_profiles", ROOT / "scripts/install_agent_profiles.py")
module = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(module)


class AgentProfileTests(unittest.TestCase):
    def test_codex_profiles_are_read_only_and_model_neutral(self) -> None:
        profiles = sorted((ROOT / "profiles/codex").glob("*.toml"))
        self.assertEqual(len(profiles), 3)
        for path in profiles:
            data = tomllib.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(data["sandbox_mode"], "read-only")
            self.assertNotIn("model", data)
            self.assertNotIn("model_reasoning_effort", data)
            self.assertTrue(data["developer_instructions"].strip())

    def test_claude_profiles_deny_edits_and_nested_agents(self) -> None:
        profiles = sorted((ROOT / "profiles/claude").glob("*.md"))
        self.assertEqual(len(profiles), 3)
        for path in profiles:
            text = path.read_text(encoding="utf-8")
            self.assertIn("tools: Read, Glob, Grep", text)
            self.assertIn("disallowedTools: Write, Edit, NotebookEdit, Agent", text)
            self.assertNotIn("\nmodel:", text)

    def test_installer_plan_is_dry_and_project_scoped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            actions = module.plan("codex", target)
            self.assertEqual(len(actions), 3)
            self.assertTrue(all(status == "CREATE" for _, _, status in actions))
            self.assertTrue(all(str(destination.relative_to(target)).startswith(".codex/agents/") for _, destination, _ in actions))
            self.assertFalse((target / ".codex").exists())

    def test_installer_detects_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            destination = target / ".claude/agents/foundation-reviewer.md"
            destination.parent.mkdir(parents=True)
            destination.write_text("local override\n", encoding="utf-8")
            statuses = {dest.name: status for _, dest, status in module.plan("claude", target)}
            self.assertEqual(statuses["foundation-reviewer.md"], "CONFLICT")


if __name__ == "__main__":
    unittest.main()
