from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "run_codex_bounded_delegation_smoke_v3",
    ROOT / "scripts/run_codex_bounded_delegation_smoke_v3.py",
)
module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = module
assert SPEC.loader
SPEC.loader.exec_module(module)


class FakeReadServer:
    def __init__(self, threads: dict[str, dict[str, Any]]) -> None:
        self.threads = threads
        self.requests: list[tuple[str, dict[str, Any]]] = []

    def request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        self.requests.append((method, params))
        if method != "thread/read":
            raise AssertionError(f"unexpected method: {method}")
        thread_id = str(params["threadId"])
        if thread_id not in self.threads:
            raise module.delegation.base.HarnessError(f"missing child {thread_id}")
        return self.threads[thread_id]


def completed_v2_start(child_id: str, path: str) -> dict[str, Any]:
    return {
        "method": "item/completed",
        "params": {
            "item": {
                "type": "subAgentActivity",
                "id": f"spawn-{child_id}",
                "kind": "started",
                "agentThreadId": child_id,
                "agentPath": path,
            }
        },
    }


def completed_v1_spawn(parent: str, child_id: str) -> dict[str, Any]:
    return {
        "method": "item/completed",
        "params": {
            "item": {
                "type": "collabAgentToolCall",
                "tool": "spawnAgent",
                "status": "completed",
                "senderThreadId": parent,
                "receiverThreadIds": [child_id],
                "prompt": "Audit one file read-only.",
            }
        },
    }


def child_thread(
    child_id: str,
    *,
    parent_id: str,
    items: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "thread": {
            "id": child_id,
            "parentThreadId": parent_id,
            "turns": [{"items": items}],
        }
    }


def new_task_item(text: str = "Audit auth/session-policy.md read-only.") -> dict[str, Any]:
    return {
        "type": "agentMessage",
        "id": "new-task",
        "text": (
            "Message Type: NEW_TASK\n"
            "Task name: /root/auth_audit\n"
            "Sender: /root\n"
            f"Payload:\n{text}"
        ),
    }


class CodexBoundedDelegationSmokeV3Tests(unittest.TestCase):
    def test_case_revision_is_three(self) -> None:
        self.assertEqual(module.CASE_REVISION, 3)

    def test_agent_path_depth_distinguishes_direct_and_nested(self) -> None:
        self.assertEqual(module.agent_path_depth("/root/auth_audit"), 1)
        self.assertEqual(module.agent_path_depth("/root/auth_audit/worker"), 2)
        self.assertEqual(module.agent_path_depth("/root"), 0)
        self.assertIsNone(module.agent_path_depth("/morpheus"))

    def test_v2_direct_child_is_observed_and_inspected(self) -> None:
        parent = "parent"
        child = "child-auth"
        server = FakeReadServer(
            {
                child: child_thread(
                    child,
                    parent_id=parent,
                    items=[new_task_item()],
                )
            }
        )
        observation = module.observe_delegation(
            server=server,
            parent_thread_id=parent,
            events=[completed_v2_start(child, "/root/auth_audit")],
        )
        self.assertEqual(observation.direct_receiver_ids, [child])
        self.assertEqual(observation.nested_receiver_ids, [])
        self.assertEqual(observation.empty_prompt_calls, 0)
        self.assertEqual(observation.protocols, ["v2-subAgentActivity"])
        self.assertEqual(
            observation.direct_agent_paths,
            {child: "/root/auth_audit"},
        )
        self.assertIn("auth/session-policy.md", observation.assignment_text_by_child[child])
        self.assertEqual(
            [params["threadId"] for _, params in server.requests],
            [child],
        )

    def test_v2_nested_child_is_detected_from_child_thread(self) -> None:
        parent = "parent"
        child = "child-auth"
        grandchild = "grandchild"
        nested_item = {
            "type": "subAgentActivity",
            "id": "nested-start",
            "kind": "started",
            "agentThreadId": grandchild,
            "agentPath": "/root/auth_audit/nested_worker",
        }
        server = FakeReadServer(
            {
                child: child_thread(
                    child,
                    parent_id=parent,
                    items=[new_task_item(), nested_item],
                )
            }
        )
        observation = module.observe_delegation(
            server=server,
            parent_thread_id=parent,
            events=[completed_v2_start(child, "/root/auth_audit")],
        )
        self.assertEqual(observation.nested_receiver_ids, [grandchild])
        self.assertEqual(
            observation.nested_agent_paths,
            {grandchild: "/root/auth_audit/nested_worker"},
        )

    def test_v1_observation_remains_supported(self) -> None:
        parent = "parent"
        child = "child-v1"
        server = FakeReadServer(
            {
                child: child_thread(
                    child,
                    parent_id=parent,
                    items=[],
                )
            }
        )
        observation = module.observe_delegation(
            server=server,
            parent_thread_id=parent,
            events=[completed_v1_spawn(parent, child)],
        )
        self.assertEqual(observation.direct_receiver_ids, [child])
        self.assertEqual(observation.protocols, ["v1-collabAgentToolCall"])
        self.assertEqual(observation.empty_prompt_calls, 0)

    def test_missing_v2_assignment_is_rejected(self) -> None:
        parent = "parent"
        child = "child-empty"
        server = FakeReadServer(
            {
                child: child_thread(
                    child,
                    parent_id=parent,
                    items=[],
                )
            }
        )
        observation = module.observe_delegation(
            server=server,
            parent_thread_id=parent,
            events=[completed_v2_start(child, "/root/empty")],
        )
        self.assertEqual(observation.empty_prompt_calls, 1)

    def test_session_config_pins_v2_and_depth_one_contract(self) -> None:
        def safe_builder(**_: Any) -> dict[str, Any]:
            return {"features": {}, "skills": {"config": []}}

        config = module.session_config(
            safe_session_builder=safe_builder,
            disabled_skill_paths=[],
            disabled_mcp_names=[],
            plugin_ids=[module.delegation.base.PLUGIN_ID],
            enable_core=True,
        )
        v2 = config["features"]["multi_agent_v2"]
        self.assertTrue(v2["enabled"])
        self.assertTrue(v2["non_code_mode_only"])
        self.assertTrue(v2["wait_agent_enabled"])
        self.assertIn("spawn_agent", v2["multi_agent_mode_hint_text"])
        self.assertTrue(config["agents"]["enabled"])
        self.assertEqual(config["agents"]["max_concurrent_threads_per_session"], 3)
        self.assertEqual(config["agents"]["max_depth"], 1)

    def test_tool_metrics_count_v2_started_child(self) -> None:
        events = [completed_v2_start("child", "/root/auth_audit")]
        turn = SimpleNamespace(events=events)
        original = module._ORIGINAL_TOOL_METRICS
        module._ORIGINAL_TOOL_METRICS = lambda _turn: (5, 0)
        try:
            tool_calls, agents = module.tool_metrics(turn)
        finally:
            module._ORIGINAL_TOOL_METRICS = original
        self.assertEqual(tool_calls, 6)
        self.assertEqual(agents, 1)

    def test_posthoc_inspection_detects_v2_without_reclassifying(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            campaign = Path(tmp) / "campaign"
            candidate = campaign / "candidate"
            candidate.mkdir(parents=True)
            trace_record = {
                "direction": "server_to_client",
                "payload": completed_v2_start(
                    "child-auth",
                    "/root/auth_audit",
                ),
            }
            # The helper above returns an app-server message; store that message as payload.
            trace_record["payload"] = trace_record["payload"]
            (candidate / "trace.jsonl").write_text(
                json.dumps(trace_record) + "\n",
                encoding="utf-8",
            )
            (candidate / "artifact.json").write_text(
                json.dumps({"thread_id": "parent"}) + "\n",
                encoding="utf-8",
            )
            exit_code = module.inspect_existing_campaign(campaign)
            self.assertEqual(exit_code, 0)
            payload = json.loads(
                (campaign / "posthoc-delegation-observation.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(payload["model_calls"], 0)
            self.assertEqual(payload["direct_receiver_ids"], ["child-auth"])
            self.assertFalse(payload["historical_result_reclassified"])

    def test_revision_contract_patches_observer_and_runtime(self) -> None:
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
            self.assertEqual(module.delegation.CASE_REVISION, 3)
            self.assertIs(module.delegation.observe_delegation, module.observe_delegation)
            self.assertIs(module.delegation.run_read_only_variant, module.run_read_only_variant)
            self.assertIs(module.delegation.tool_metrics, module.tool_metrics)
            self.assertIs(module.delegation.evaluate_run, module.evaluate_run)
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
