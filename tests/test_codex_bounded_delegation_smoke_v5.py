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
    "run_codex_bounded_delegation_smoke_v5",
    ROOT / "scripts/run_codex_bounded_delegation_smoke_v5.py",
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


def v2_start_item(child_id: str, path: str) -> dict[str, Any]:
    return completed_v2_start(child_id, path)["params"]["item"]


def completed_v1_spawn(
    *,
    sender: str,
    receiver: str,
) -> dict[str, Any]:
    return {
        "method": "item/completed",
        "params": {
            "item": {
                "type": "collabAgentToolCall",
                "tool": "spawnAgent",
                "status": "completed",
                "senderThreadId": sender,
                "receiverThreadIds": [receiver],
                "prompt": "Audit one file read-only.",
            }
        },
    }


def v1_spawn_item(*, sender: str, receiver: str) -> dict[str, Any]:
    return completed_v1_spawn(sender=sender, receiver=receiver)["params"]["item"]


def new_task_item(path: str) -> dict[str, Any]:
    return {
        "type": "agentMessage",
        "id": f"task-{path}",
        "text": (
            "Message Type: NEW_TASK\n"
            "Task name: /root/audit\n"
            "Sender: /root\n"
            f"Payload:\nAudit {path} read-only and return its Risk-ID."
        ),
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
            "ephemeral": False,
            "turns": [{"items": items}],
        }
    }


class CodexBoundedDelegationSmokeV5Tests(unittest.TestCase):
    def test_case_revision_is_five(self) -> None:
        self.assertEqual(module.CASE_REVISION, 5)

    def test_child_self_start_is_provenance_not_nested_delegation(self) -> None:
        parent = "parent"
        child = "child-auth"
        server = FakeReadServer(
            {
                child: child_thread(
                    child,
                    parent_id=parent,
                    items=[
                        new_task_item("auth/session-policy.md"),
                        v2_start_item(child, "/root/audit_auth"),
                    ],
                )
            }
        )

        observation = module.observe_delegation(
            server=server,
            parent_thread_id=parent,
            events=[completed_v2_start(child, "/root/audit_auth")],
        )

        self.assertEqual(observation.direct_receiver_ids, [child])
        self.assertEqual(observation.nested_receiver_ids, [])
        self.assertEqual(observation.child_read_errors, [])
        self.assertEqual(
            observation.self_activity_paths_by_child,
            {child: ["/root/audit_auth"]},
        )
        self.assertIn(
            "auth/session-policy.md",
            observation.assignment_text_by_child[child],
        )

    def test_mirrored_direct_sibling_activity_is_not_nested(self) -> None:
        parent = "parent"
        auth = "child-auth"
        billing = "child-billing"
        server = FakeReadServer(
            {
                auth: child_thread(
                    auth,
                    parent_id=parent,
                    items=[
                        new_task_item("auth/session-policy.md"),
                        v2_start_item(auth, "/root/audit_auth"),
                        v2_start_item(billing, "/root/audit_billing"),
                    ],
                ),
                billing: child_thread(
                    billing,
                    parent_id=parent,
                    items=[
                        new_task_item("billing/refunds.md"),
                        v2_start_item(billing, "/root/audit_billing"),
                    ],
                ),
            }
        )

        observation = module.observe_delegation(
            server=server,
            parent_thread_id=parent,
            events=[
                completed_v2_start(auth, "/root/audit_auth"),
                completed_v2_start(billing, "/root/audit_billing"),
            ],
        )

        self.assertEqual(observation.nested_receiver_ids, [])
        self.assertEqual(observation.child_read_errors, [])
        self.assertEqual(
            observation.mirrored_direct_activity_by_child,
            {auth: [billing]},
        )

    def test_depth_two_child_activity_is_real_nested_delegation(self) -> None:
        parent = "parent"
        child = "child-auth"
        grandchild = "grandchild"
        server = FakeReadServer(
            {
                child: child_thread(
                    child,
                    parent_id=parent,
                    items=[
                        new_task_item("auth/session-policy.md"),
                        v2_start_item(child, "/root/audit_auth"),
                        v2_start_item(
                            grandchild,
                            "/root/audit_auth/nested_worker",
                        ),
                    ],
                )
            }
        )

        observation = module.observe_delegation(
            server=server,
            parent_thread_id=parent,
            events=[completed_v2_start(child, "/root/audit_auth")],
        )

        self.assertEqual(observation.nested_receiver_ids, [grandchild])
        self.assertEqual(
            observation.nested_agent_paths,
            {grandchild: "/root/audit_auth/nested_worker"},
        )

    def test_unobserved_root_level_activity_fails_closed(self) -> None:
        parent = "parent"
        child = "child-auth"
        unknown = "unknown-direct"
        server = FakeReadServer(
            {
                child: child_thread(
                    child,
                    parent_id=parent,
                    items=[
                        new_task_item("auth/session-policy.md"),
                        v2_start_item(unknown, "/root/unknown"),
                    ],
                )
            }
        )

        observation = module.observe_delegation(
            server=server,
            parent_thread_id=parent,
            events=[completed_v2_start(child, "/root/audit_auth")],
        )

        self.assertEqual(observation.nested_receiver_ids, [])
        self.assertEqual(len(observation.child_read_errors), 1)
        self.assertIn("unobserved root-level", observation.child_read_errors[0])

    def test_v1_parent_spawn_mirrored_in_child_history_is_not_nested(self) -> None:
        parent = "parent"
        child = "child-v1"
        server = FakeReadServer(
            {
                child: child_thread(
                    child,
                    parent_id=parent,
                    items=[v1_spawn_item(sender=parent, receiver=child)],
                )
            }
        )

        observation = module.observe_delegation(
            server=server,
            parent_thread_id=parent,
            events=[completed_v1_spawn(sender=parent, receiver=child)],
        )

        self.assertEqual(observation.direct_receiver_ids, [child])
        self.assertEqual(observation.nested_receiver_ids, [])
        self.assertEqual(
            observation.mirrored_v1_parent_spawns_by_child,
            {child: [child]},
        )

    def test_evaluation_records_provenance_classification(self) -> None:
        original = module._REVISION4_EVALUATE_RUN
        module._REVISION4_EVALUATE_RUN = lambda **_: SimpleNamespace(
            row={},
            artifact={},
        )
        try:
            with tempfile.TemporaryDirectory() as tmp:
                run_dir = Path(tmp)
                observation = SimpleNamespace(
                    self_activity_paths_by_child={"child": ["/root/child"]},
                    mirrored_direct_activity_by_child={"child": ["sibling"]},
                    root_activity_paths_by_child={"child": ["/root"]},
                    mirrored_v1_parent_spawns_by_child={"child": ["child"]},
                )
                result = module.evaluate_run(
                    observation=observation,
                    run_dir=run_dir,
                )
                written = json.loads(
                    (run_dir / "artifact.json").read_text(encoding="utf-8")
                )
        finally:
            module._REVISION4_EVALUATE_RUN = original

        self.assertEqual(
            result.artifact["self_activity_paths_by_child"],
            {"child": ["/root/child"]},
        )
        self.assertEqual(written, result.artifact)

    def test_revision_contract_preserves_v4_storage_and_patches_observer(self) -> None:
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
            self.assertEqual(module.delegation.CASE_REVISION, 5)
            self.assertIs(
                module.delegation.observe_delegation,
                module.observe_delegation,
            )
            self.assertIs(
                module.delegation.run_read_only_variant,
                module.revision4.run_read_only_variant,
            )
            self.assertIs(
                module.delegation.evaluate_run,
                module.evaluate_run,
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
