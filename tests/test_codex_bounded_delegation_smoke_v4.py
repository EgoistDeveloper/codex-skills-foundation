from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "run_codex_bounded_delegation_smoke_v4",
    ROOT / "scripts/run_codex_bounded_delegation_smoke_v4.py",
)
module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = module
assert SPEC.loader
SPEC.loader.exec_module(module)


class FakeAppServer:
    last: "FakeAppServer | None" = None

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
        self.requests: list[tuple[str, dict[str, Any]]] = []
        FakeAppServer.last = self

    def __enter__(self) -> "FakeAppServer":
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def initialize(self) -> Path:
        return Path("C:/Users/Test/.codex")

    def request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        self.requests.append((method, params))
        if method == "thread/start":
            return {
                "thread": {
                    "id": "parent-thread",
                    "ephemeral": False,
                },
                "multiAgentMode": "explicitRequestOnly",
            }
        if method == "thread/read":
            return {
                "thread": {
                    "id": "parent-thread",
                    "ephemeral": False,
                    "turns": [],
                }
            }
        raise AssertionError(f"unexpected request: {method}")

    def start_turn(self, **_: Any) -> tuple[str, list[dict[str, Any]], dict[str, Any]]:
        return "turn-id", [], {}

    def stderr_text(self) -> str:
        return ""


class CodexBoundedDelegationSmokeV4Tests(unittest.TestCase):
    def test_case_revision_is_four(self) -> None:
        self.assertEqual(module.CASE_REVISION, 4)

    def test_in_memory_override_is_valid_toml_and_precedes_listen(self) -> None:
        command, override = module.app_server_command_with_in_memory_store(
            (
                "node",
                "codex.js",
                "app-server",
                "-c",
                "features.plugins=true",
                "--listen",
                "stdio://",
            ),
            store_id="bounded-test-store",
        )
        parsed = tomllib.loads(override)
        self.assertEqual(
            parsed["experimental_thread_store"],
            {"type": "in_memory", "id": "bounded-test-store"},
        )
        override_index = command.index(override)
        self.assertEqual(command[override_index - 1], "-c")
        self.assertLess(override_index, command.index("--listen"))
        self.assertEqual(command[-2:], ("--listen", "stdio://"))

    def test_existing_thread_store_override_is_rejected(self) -> None:
        with self.assertRaises(module.delegation.base.HarnessError):
            module.app_server_command_with_in_memory_store(
                (
                    "node",
                    "codex.js",
                    "app-server",
                    "-c",
                    'experimental_thread_store={ type = "local" }',
                    "--listen",
                    "stdio://",
                ),
                store_id="duplicate",
            )

    def test_variant_uses_non_ephemeral_readable_in_memory_parent(self) -> None:
        original_server = module.delegation.base.AppServer
        original_parser = module.delegation.base.parse_live_turn
        module.delegation.base.AppServer = FakeAppServer
        module.delegation.base.parse_live_turn = lambda **kwargs: SimpleNamespace(**kwargs)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                workspace = root / "workspace"
                run_dir = root / "run"
                workspace.mkdir()
                run_dir.mkdir()
                _, observation, _ = module.run_read_only_variant(
                    variant="candidate",
                    launchers=SimpleNamespace(node_executable="node"),
                    app_server_command=(
                        "node",
                        "codex.js",
                        "app-server",
                        "--listen",
                        "stdio://",
                    ),
                    workspace=workspace,
                    run_dir=run_dir,
                    timeout_seconds=120,
                    model=None,
                    model_provider=None,
                    service_tier=None,
                    session_config={},
                    explicit_skill=None,
                )
        finally:
            module.delegation.base.AppServer = original_server
            module.delegation.base.parse_live_turn = original_parser

        server = FakeAppServer.last
        assert server is not None
        start_method, start_params = server.requests[0]
        self.assertEqual(start_method, "thread/start")
        self.assertIs(start_params["ephemeral"], False)
        self.assertEqual(
            server.requests[1],
            (
                "thread/read",
                {"threadId": "parent-thread", "includeTurns": True},
            ),
        )
        self.assertTrue(observation.parent_read_preflight_pass)
        self.assertFalse(observation.parent_thread_ephemeral)
        self.assertTrue(observation.child_history_readable)
        self.assertEqual(observation.thread_store_mode, "in_memory")
        self.assertTrue(
            any("experimental_thread_store" in part for part in server.command)
        )

    def test_evaluation_records_thread_store_evidence(self) -> None:
        original = module._REVISION3_EVALUATE_RUN
        module._REVISION3_EVALUATE_RUN = lambda **_: SimpleNamespace(
            row={},
            artifact={"startup_config_overrides": []},
        )
        try:
            with tempfile.TemporaryDirectory() as tmp:
                run_dir = Path(tmp)
                observation = SimpleNamespace(
                    thread_store_mode="in_memory",
                    thread_store_id="store-id",
                    thread_store_startup_override=(
                        'experimental_thread_store={ type = "in_memory", id = "store-id" }'
                    ),
                    parent_thread_ephemeral=False,
                    parent_read_preflight_pass=True,
                    child_history_readable=True,
                )
                result = module.evaluate_run(
                    observation=observation,
                    run_dir=run_dir,
                )
                written = json.loads(
                    (run_dir / "artifact.json").read_text(encoding="utf-8")
                )
        finally:
            module._REVISION3_EVALUATE_RUN = original

        self.assertEqual(result.artifact["thread_store_mode"], "in_memory")
        self.assertFalse(result.artifact["parent_thread_ephemeral"])
        self.assertTrue(result.artifact["parent_read_preflight_pass"])
        self.assertTrue(result.artifact["child_history_readable"])
        self.assertIn(
            result.artifact["thread_store_startup_override"],
            result.artifact["startup_config_overrides"],
        )
        self.assertEqual(written, result.artifact)

    def test_revision_contract_patches_revision_four_runtime(self) -> None:
        original = (
            module.delegation.CASE_REVISION,
            module.delegation.DELEGATION_PROMPT,
            module.delegation.session_config,
            module.delegation.observe_delegation,
            module.delegation.run_read_only_variant,
            module.delegation.tool_metrics,
            module.delegation.evaluate_run,
        )
        try:
            module.apply_revision_contract()
            self.assertEqual(module.delegation.CASE_REVISION, 4)
            self.assertIs(
                module.delegation.run_read_only_variant,
                module.run_read_only_variant,
            )
            self.assertIs(module.delegation.evaluate_run, module.evaluate_run)
            self.assertIs(
                module.delegation.observe_delegation,
                module.revision3.observe_delegation,
            )
        finally:
            (
                module.delegation.CASE_REVISION,
                module.delegation.DELEGATION_PROMPT,
                module.delegation.session_config,
                module.delegation.observe_delegation,
                module.delegation.run_read_only_variant,
                module.delegation.tool_metrics,
                module.delegation.evaluate_run,
            ) = original


if __name__ == "__main__":
    unittest.main()
