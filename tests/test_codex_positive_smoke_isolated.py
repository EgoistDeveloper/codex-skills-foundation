from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "run_codex_positive_smoke_isolated",
    ROOT / "scripts/run_codex_positive_smoke_isolated.py",
)
module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = module
assert SPEC.loader
SPEC.loader.exec_module(module)
base = module.base


class CodexPositiveSmokeIsolationTests(unittest.TestCase):
    def test_effective_plugin_ids_union_cli_inventory_and_core(self) -> None:
        ids = module.effective_plugin_ids(
            [
                {"id": "hidden@curated"},
                {"id": "foreign@marketplace"},
                {"id": ""},
            ],
            ["foreign@marketplace", "cli-only@marketplace"],
        )
        self.assertEqual(
            ids,
            sorted(
                {
                    base.PLUGIN_ID,
                    "hidden@curated",
                    "foreign@marketplace",
                    "cli-only@marketplace",
                }
            ),
        )

    def test_positive_command_enables_only_core_and_uses_valid_mcp_veto(self) -> None:
        launchers = base.CodexLaunchers(
            cli_prefix=("node", "codex.js"),
            app_server_command=(
                "node",
                "codex.js",
                "app-server",
                "--listen",
                "stdio://",
            ),
            node_executable="node",
            version_text="codex-cli 0.147.0",
            version=(0, 147, 0),
        )
        foreign = "foreign@marketplace"
        command, overrides = module.build_positive_app_server_command(
            launchers=launchers,
            plugin_ids=[base.PLUGIN_ID, foreign],
            disabled_mcp_server_names=["fable-advisor-python3", "node_repl"],
        )
        self.assertEqual(command[-2:], ("--listen", "stdio://"))
        self.assertIn("features.remote_plugin=false", overrides)

        plugin_override = next(
            item for item in overrides if item.startswith("plugins=")
        )
        plugin_table = tomllib.loads(plugin_override)["plugins"]
        self.assertTrue(plugin_table[base.PLUGIN_ID]["enabled"])
        self.assertFalse(plugin_table[foreign]["enabled"])

        mcp_override = next(
            item for item in overrides if item.startswith("mcp_servers=")
        )
        mcp_table = tomllib.loads(mcp_override)["mcp_servers"]
        self.assertFalse(mcp_table["fable-advisor-python3"]["enabled"])
        self.assertEqual(
            mcp_table["fable-advisor-python3"]["command"],
            module.isolation.DISABLED_MCP_STUB_COMMAND,
        )

    def test_isolation_artifact_discloses_zero_model_preflight(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            campaign = Path(tmp) / "campaign"
            path = module.write_isolation_artifact(
                campaign=campaign,
                codex_home=Path(tmp) / ".codex",
                direct_mcp_names=["node_repl"],
                runtime_inventory=[
                    {
                        "name": "fable-advisor-python3",
                        "plugin_id": None,
                        "tool_names": ["create_plan"],
                    }
                ],
                disabled_mcp_names=["fable-advisor-python3", "node_repl"],
                veto_inventory=[
                    {
                        "name": "fable-advisor-python3",
                        "plugin_id": None,
                        "tool_names": [],
                    }
                ],
                veto_overrides=["mcp_servers={ ... }"],
                startup_overrides=["features.plugins=true"],
                plugin_ids=[base.PLUGIN_ID],
            )
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(payload["isolation_revision"], 1)
            self.assertEqual(payload["positive_case_revision"], 2)
            self.assertEqual(payload["model_calls"], 0)
            self.assertTrue(payload["thread_mcp_overrides_omitted"])
            self.assertTrue(payload["veto_validation_pass"])


if __name__ == "__main__":
    unittest.main()
