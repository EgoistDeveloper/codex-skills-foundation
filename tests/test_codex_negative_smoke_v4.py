from __future__ import annotations

import importlib.util
import tempfile
import tomllib
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "run_codex_negative_smoke_v4",
    ROOT / "scripts/run_codex_negative_smoke_v4.py",
)
module = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(module)
base = module.base


class PagingServer:
    def __init__(self) -> None:
        self.requests: list[tuple[str, dict[str, Any]]] = []

    def request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        self.requests.append((method, params))
        if params["cursor"] is None:
            return {
                "data": [
                    {
                        "name": "fable-advisor-python3",
                        "pluginId": None,
                        "authStatus": "unsupported",
                        "tools": {
                            "create_plan": {},
                            "review_plan": {},
                        },
                    },
                    {
                        "name": "node_repl",
                        "pluginId": None,
                        "authStatus": "unsupported",
                        "tools": {},
                    },
                ],
                "nextCursor": "2",
            }
        return {
            "data": [
                {
                    "name": "plugin-mcp",
                    "pluginId": "foreign@marketplace",
                    "authStatus": "unsupported",
                    "tools": {"inspect": {}},
                },
                {
                    "name": "node_repl",
                    "pluginId": None,
                    "authStatus": "unsupported",
                    "tools": {},
                },
            ],
            "nextCursor": None,
        }


class FakeRuntimeAppServer:
    expected_home = Path(".").resolve()
    start_turn_calls = 0

    def __init__(
        self,
        *,
        command: tuple[str, ...],
        node_executable: str,
        cwd: Path,
        trace_path: Path,
        timeout_seconds: int,
    ) -> None:
        self.command = command
        self.node_executable = node_executable
        self.cwd = cwd
        self.trace_path = trace_path
        self.timeout_seconds = timeout_seconds

    def __enter__(self) -> "FakeRuntimeAppServer":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> bool:
        return False

    def initialize(self) -> Path:
        return self.expected_home

    def start_thread(
        self,
        *,
        cwd: Path,
        model: str | None,
        model_provider: str | None,
        service_tier: str | None,
        session_config: dict[str, Any],
    ) -> dict[str, Any]:
        if session_config != {}:
            raise AssertionError("runtime probe must not inject a model-session policy")
        return {"thread": {"id": "runtime-probe-thread"}}

    def start_turn(self, **_: Any) -> None:
        type(self).start_turn_calls += 1
        raise AssertionError("runtime MCP discovery must not start a model turn")

    def request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        if method != "mcpServerStatus/list":
            raise AssertionError(f"unexpected request: {method}")
        if params["threadId"] != "runtime-probe-thread":
            raise AssertionError("wrong thread id")
        return {
            "data": [
                {
                    "name": "fable-advisor-python3",
                    "pluginId": None,
                    "authStatus": "unsupported",
                    "tools": {
                        "create_plan": {},
                        "review_plan": {},
                        "revise_plan": {},
                        "status": {},
                    },
                }
            ],
            "nextCursor": None,
        }


class EmptyRuntimeAppServer(FakeRuntimeAppServer):
    def request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        if method != "mcpServerStatus/list":
            raise AssertionError(f"unexpected request: {method}")
        if params["threadId"] != "runtime-probe-thread":
            raise AssertionError("wrong thread id")
        return {"data": [], "nextCursor": None}


class FakeVetoAppServer:
    expected_home = Path(".").resolve()
    start_turn_calls = 0
    leak_tools = False
    last_session_config: dict[str, Any] = {}

    def __init__(
        self,
        *,
        command: tuple[str, ...],
        node_executable: str,
        cwd: Path,
        trace_path: Path,
        timeout_seconds: int,
    ) -> None:
        self.command = command
        self.node_executable = node_executable
        self.cwd = cwd
        self.trace_path = trace_path
        self.timeout_seconds = timeout_seconds

    def __enter__(self) -> "FakeVetoAppServer":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> bool:
        return False

    def initialize(self) -> Path:
        return self.expected_home

    def start_thread(
        self,
        *,
        cwd: Path,
        model: str | None,
        model_provider: str | None,
        service_tier: str | None,
        session_config: dict[str, Any],
    ) -> dict[str, Any]:
        type(self).last_session_config = session_config
        return {"thread": {"id": "veto-thread"}}

    def start_turn(self, **_: Any) -> None:
        type(self).start_turn_calls += 1
        raise AssertionError("runtime veto verification must not start a model turn")

    def request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        if method != "mcpServerStatus/list":
            raise AssertionError(f"unexpected request: {method}")
        tools = {"create_plan": {}} if type(self).leak_tools else {}
        return {
            "data": [
                {
                    "name": "fable-advisor-python3",
                    "pluginId": None,
                    "authStatus": "unsupported",
                    "tools": tools,
                }
            ],
            "nextCursor": None,
        }


class CodexNegativeSmokeV4Tests(unittest.TestCase):
    def test_case_revision_is_six(self) -> None:
        self.assertEqual(module.CASE_REVISION, 6)

    def test_status_inventory_is_paginated_deduplicated_and_attributed(self) -> None:
        server = PagingServer()
        rows = module.mcp_status_rows(server, thread_id="thread")
        self.assertEqual(
            [row["name"] for row in rows],
            ["fable-advisor-python3", "node_repl", "plugin-mcp"],
        )
        self.assertEqual(rows[0]["plugin_id"], None)
        self.assertEqual(rows[0]["tool_names"], ["create_plan", "review_plan"])
        self.assertEqual(rows[2]["plugin_id"], "foreign@marketplace")
        self.assertEqual(
            [params["cursor"] for _, params in server.requests],
            [None, "2"],
        )

    def test_status_inventory_distinguishes_empty_from_malformed(self) -> None:
        class StaticServer:
            def __init__(self, response: dict[str, Any]) -> None:
                self.response = response

            def request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
                self.assert_request(method, params)
                return self.response

            @staticmethod
            def assert_request(method: str, params: dict[str, Any]) -> None:
                if method != "mcpServerStatus/list" or params["cursor"] is not None:
                    raise AssertionError("unexpected MCP inventory request")

        self.assertEqual(
            module.mcp_status_rows(
                StaticServer({"data": [], "nextCursor": None}),
                thread_id="thread",
            ),
            [],
        )
        malformed = (
            {"data": [{}], "nextCursor": None},
            {"data": [None], "nextCursor": None},
            {"data": [{"name": ""}], "nextCursor": None},
            {"data": [], "nextCursor": 1},
        )
        for response in malformed:
            with self.subTest(response=response):
                with self.assertRaises(base.HarnessError):
                    module.mcp_status_rows(
                        StaticServer(response),
                        thread_id="thread",
                    )

    def test_name_veto_unions_direct_and_runtime_sources(self) -> None:
        names = module.merge_mcp_server_names(
            ["codebase-memory-mcp", "node_repl"],
            [
                {"name": "fable-advisor-py"},
                {"name": "fable-advisor-python"},
                {"name": "fable-advisor-python3"},
                {"name": "node_repl"},
            ],
        )
        self.assertEqual(
            names,
            [
                "codebase-memory-mcp",
                "fable-advisor-py",
                "fable-advisor-python",
                "fable-advisor-python3",
                "node_repl",
            ],
        )

    def test_disabled_mcp_override_is_transport_complete(self) -> None:
        override = module.disabled_mcp_table_override(
            ["fable-advisor-python3", "codebase-memory-mcp"]
        )
        table = tomllib.loads(override)["mcp_servers"]
        self.assertEqual(
            sorted(table),
            ["codebase-memory-mcp", "fable-advisor-python3"],
        )
        for config in table.values():
            self.assertFalse(config["enabled"])
            self.assertEqual(
                config["command"],
                module.DISABLED_MCP_STUB_COMMAND,
            )

    def test_transport_safe_builder_replaces_partial_mcp_overrides(self) -> None:
        captured: dict[str, Any] = {}

        def original_builder(**kwargs: Any) -> tuple[tuple[str, ...], list[str]]:
            captured.update(kwargs)
            return (
                (
                    "node",
                    "codex.js",
                    "app-server",
                    "-c",
                    "features.plugins=false",
                    "--listen",
                    "stdio://",
                ),
                ["features.plugins=false"],
            )

        builder = module.transport_safe_builder(original_builder)
        command, overrides = builder(
            launchers=object(),
            installed_plugin_ids=["foreign@marketplace"],
            mcp_server_names=["codebase-memory-mcp", "fable-advisor-python3"],
            plugin_mcp_servers={},
            plugins_enabled=False,
            enabled_plugin_id=None,
        )
        self.assertEqual(captured["mcp_server_names"], [])
        self.assertEqual(command[-2:], ("--listen", "stdio://"))
        veto = overrides[-1]
        self.assertTrue(veto.startswith("mcp_servers="))
        self.assertIn(veto, command)
        self.assertFalse(
            any(".enabled=false" in override for override in overrides)
        )
        table = tomllib.loads(veto)["mcp_servers"]
        self.assertFalse(table["codebase-memory-mcp"]["enabled"])
        self.assertIn("command", table["fable-advisor-python3"])

    def test_startup_only_session_builder_omits_thread_mcp_rows(self) -> None:
        captured: dict[str, Any] = {}

        def original_builder(
            *,
            disabled_skill_paths: list[str],
            mcp_server_names: list[str],
        ) -> dict[str, Any]:
            captured["disabled_skill_paths"] = list(disabled_skill_paths)
            captured["mcp_server_names"] = list(mcp_server_names)
            config: dict[str, Any] = {
                "features": {"plugins": False},
            }
            if disabled_skill_paths:
                config["skills"] = {
                    "config": [
                        {"path": path, "enabled": False}
                        for path in disabled_skill_paths
                    ]
                }
            if mcp_server_names:
                config["mcp_servers"] = {
                    name: {"enabled": False}
                    for name in mcp_server_names
                }
            return config

        builder = module.startup_only_session_config_builder(original_builder)
        config = builder(
            disabled_skill_paths=["C:/skills/foreign/SKILL.md"],
            mcp_server_names=["codex_apps", "fable-advisor-python3"],
        )
        self.assertEqual(
            captured["disabled_skill_paths"],
            ["C:/skills/foreign/SKILL.md"],
        )
        self.assertEqual(captured["mcp_server_names"], [])
        self.assertNotIn("mcp_servers", config)
        self.assertEqual(
            config["skills"]["config"][0]["path"],
            "C:/skills/foreign/SKILL.md",
        )

    def test_runtime_discovery_starts_no_model_turn(self) -> None:
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
        original_app_server = module.base.AppServer
        original_poll = module.RUNTIME_PROBE_POLL_SECONDS
        original_stable = module.RUNTIME_PROBE_STABLE_POLLS
        FakeRuntimeAppServer.expected_home = ROOT.resolve()
        FakeRuntimeAppServer.start_turn_calls = 0
        module.base.AppServer = FakeRuntimeAppServer
        module.RUNTIME_PROBE_POLL_SECONDS = 0
        module.RUNTIME_PROBE_STABLE_POLLS = 1
        try:
            rows = module.discover_runtime_mcp_inventory(
                launchers=launchers,
                codex_home=ROOT.resolve(),
                cwd=ROOT.resolve(),
                timeout_seconds=5,
            )
        finally:
            module.base.AppServer = original_app_server
            module.RUNTIME_PROBE_POLL_SECONDS = original_poll
            module.RUNTIME_PROBE_STABLE_POLLS = original_stable
        self.assertEqual([row["name"] for row in rows], ["fable-advisor-python3"])
        self.assertEqual(FakeRuntimeAppServer.start_turn_calls, 0)

    def test_runtime_discovery_accepts_a_stable_empty_inventory(self) -> None:
        launchers = base.CodexLaunchers(
            cli_prefix=("node", "codex.js"),
            app_server_command=("node", "codex.js", "app-server", "--listen", "stdio://"),
            node_executable="node",
            version_text="codex-cli 0.147.0",
            version=(0, 147, 0),
        )
        original_app_server = module.base.AppServer
        original_poll = module.RUNTIME_PROBE_POLL_SECONDS
        original_stable = module.RUNTIME_PROBE_STABLE_POLLS
        EmptyRuntimeAppServer.expected_home = ROOT.resolve()
        EmptyRuntimeAppServer.start_turn_calls = 0
        module.base.AppServer = EmptyRuntimeAppServer
        module.RUNTIME_PROBE_POLL_SECONDS = 0
        module.RUNTIME_PROBE_STABLE_POLLS = 1
        try:
            rows = module.discover_runtime_mcp_inventory(
                launchers=launchers,
                codex_home=ROOT.resolve(),
                cwd=ROOT.resolve(),
                timeout_seconds=5,
            )
        finally:
            module.base.AppServer = original_app_server
            module.RUNTIME_PROBE_POLL_SECONDS = original_poll
            module.RUNTIME_PROBE_STABLE_POLLS = original_stable
        self.assertEqual(rows, [])
        self.assertEqual(EmptyRuntimeAppServer.start_turn_calls, 0)

    def test_veto_verification_starts_no_model_turn_and_rejects_leaks(self) -> None:
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
        original_app_server = module.base.AppServer
        original_installed = module.negative.installed_plugin_ids
        original_session_builder = module.base.build_session_config
        original_poll = module.RUNTIME_PROBE_POLL_SECONDS
        original_stable = module.RUNTIME_PROBE_STABLE_POLLS
        FakeVetoAppServer.expected_home = ROOT.resolve()
        FakeVetoAppServer.start_turn_calls = 0
        FakeVetoAppServer.last_session_config = {}
        module.base.AppServer = FakeVetoAppServer
        module.negative.installed_plugin_ids = lambda _launchers: []
        module.base.build_session_config = (
            module.startup_only_session_config_builder(original_session_builder)
        )
        module.RUNTIME_PROBE_POLL_SECONDS = 0
        module.RUNTIME_PROBE_STABLE_POLLS = 1

        def builder(**_: Any) -> tuple[tuple[str, ...], list[str]]:
            return (
                launchers.app_server_command,
                ["mcp_servers={}"],
            )

        try:
            FakeVetoAppServer.leak_tools = False
            inventory, _ = module.verify_runtime_mcp_veto(
                launchers=launchers,
                codex_home=ROOT.resolve(),
                cwd=ROOT.resolve(),
                disabled_names=["fable-advisor-python3"],
                builder=builder,
                campaign=None,
                timeout_seconds=5,
            )
            self.assertEqual(inventory[0]["tool_names"], [])
            self.assertEqual(FakeVetoAppServer.start_turn_calls, 0)
            self.assertNotIn(
                "mcp_servers",
                FakeVetoAppServer.last_session_config,
            )

            FakeVetoAppServer.leak_tools = True
            with self.assertRaisesRegex(base.HarnessError, "left tools exposed"):
                module.verify_runtime_mcp_veto(
                    launchers=launchers,
                    codex_home=ROOT.resolve(),
                    cwd=ROOT.resolve(),
                    disabled_names=["fable-advisor-python3"],
                    builder=builder,
                    campaign=None,
                    timeout_seconds=5,
                )
        finally:
            module.base.AppServer = original_app_server
            module.negative.installed_plugin_ids = original_installed
            module.base.build_session_config = original_session_builder
            module.RUNTIME_PROBE_POLL_SECONDS = original_poll
            module.RUNTIME_PROBE_STABLE_POLLS = original_stable
            FakeVetoAppServer.leak_tools = False

    def test_probe_artifact_preserves_runtime_and_veto_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            campaign = Path(tmp) / "campaign"
            path = module.write_runtime_probe_artifact(
                campaign=campaign,
                codex_home=ROOT,
                direct_config_names=["node_repl"],
                runtime_inventory=[
                    {
                        "name": "fable-advisor-python3",
                        "plugin_id": None,
                        "auth_status": "unsupported",
                        "tool_names": ["create_plan", "status"],
                    }
                ],
                disabled_names=["fable-advisor-python3", "node_repl"],
                veto_inventory=[
                    {
                        "name": "fable-advisor-python3",
                        "plugin_id": None,
                        "auth_status": "unsupported",
                        "tool_names": [],
                    }
                ],
                veto_overrides=["mcp_servers={ ... }"],
            )
            self.assertIsNotNone(path)
            assert path is not None
            payload = __import__("json").loads(path.read_text(encoding="utf-8"))
            self.assertEqual(payload["schema_version"], 3)
            self.assertEqual(payload["case_revision"], 6)
            self.assertEqual(payload["model_calls"], 0)
            self.assertTrue(payload["thread_mcp_overrides_omitted"])
            self.assertTrue(payload["veto_validation_pass"])
            self.assertEqual(
                payload["runtime_mcp_inventory"][0]["plugin_id"],
                None,
            )
            self.assertEqual(
                payload["veto_validation_inventory"][0]["tool_names"],
                [],
            )
            self.assertEqual(
                payload["disabled_mcp_server_names"],
                ["fable-advisor-python3", "node_repl"],
            )


if __name__ == "__main__":
    unittest.main()
