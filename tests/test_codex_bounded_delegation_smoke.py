from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "run_codex_bounded_delegation_smoke",
    ROOT / "scripts/run_codex_bounded_delegation_smoke.py",
)
module = importlib.util.module_from_spec(SPEC)
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
            raise module.base.HarnessError(f"missing child {thread_id}")
        return self.threads[thread_id]


def completed_spawn(
    *,
    sender: str,
    receivers: list[str],
    prompt: str = "Audit one subsystem read-only.",
) -> dict[str, Any]:
    return {
        "method": "item/completed",
        "params": {
            "item": {
                "type": "collabAgentToolCall",
                "tool": "spawnAgent",
                "status": "completed",
                "senderThreadId": sender,
                "receiverThreadIds": receivers,
                "prompt": prompt,
            }
        },
    }


def child_thread(
    child_id: str,
    *,
    parent_id: str,
    items: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "thread": {
            "id": child_id,
            "parentThreadId": parent_id,
            "turns": [{"items": items or []}],
        }
    }


class CodexBoundedDelegationSmokeTests(unittest.TestCase):
    def test_fixture_has_three_independent_exact_risks(self) -> None:
        fixture = module.fixture_source()
        self.assertEqual(
            set(path for path in fixture if path != "README.md"),
            set(module.REPORT_PATHS),
        )
        combined = "\n".join(fixture.values())
        for risk_id in module.REPORT_RISK_IDS:
            self.assertEqual(combined.count(risk_id), 1)

    def test_prompt_requires_read_only_bounded_parent_integration(self) -> None:
        prompt = module.DELEGATION_PROMPT.lower()
        self.assertIn("bounded read-only delegation", prompt)
        self.assertIn("bir ile üç", prompt)
        self.assertIn("alt agentlar başka alt agent açmamalı", prompt)
        self.assertIn("hiçbir dosyayı değiştirme", prompt)
        self.assertIn("parent", prompt)
        for path in module.REPORT_PATHS:
            self.assertIn(path, module.DELEGATION_PROMPT)

    def test_report_coverage_requires_every_id_and_path(self) -> None:
        complete = "\n".join(
            f"{path}: {risk_id} risk and smallest action"
            for path, risk_id in zip(module.REPORT_PATHS, module.REPORT_RISK_IDS)
        )
        self.assertTrue(module.report_coverage(complete)["pass"])
        incomplete = complete.replace(module.REPORT_RISK_IDS[1], "missing")
        coverage = module.report_coverage(incomplete)
        self.assertFalse(coverage["pass"])
        self.assertEqual(coverage["missing_risk_ids"], [module.REPORT_RISK_IDS[1]])

    def test_direct_delegation_is_deduplicated_and_children_are_inspected(self) -> None:
        parent = "parent"
        events = [
            completed_spawn(sender=parent, receivers=["child-a", "child-b"]),
        ]
        server = FakeReadServer(
            {
                "child-a": child_thread("child-a", parent_id=parent),
                "child-b": child_thread("child-b", parent_id=parent),
            }
        )
        observation = module.observe_delegation(
            server=server,
            parent_thread_id=parent,
            events=events,
        )
        self.assertEqual(observation.direct_receiver_ids, ["child-a", "child-b"])
        self.assertEqual(observation.duplicate_receiver_ids, [])
        self.assertEqual(observation.nested_receiver_ids, [])
        self.assertEqual(observation.child_read_errors, [])
        self.assertEqual(
            [params["threadId"] for _, params in server.requests],
            ["child-a", "child-b"],
        )

    def test_nested_spawn_is_detected_from_child_thread(self) -> None:
        parent = "parent"
        nested_item = {
            "type": "collabAgentToolCall",
            "tool": "spawnAgent",
            "status": "completed",
            "senderThreadId": "child-a",
            "receiverThreadIds": ["grandchild"],
            "prompt": "Should not happen",
        }
        server = FakeReadServer(
            {
                "child-a": child_thread(
                    "child-a",
                    parent_id=parent,
                    items=[nested_item],
                )
            }
        )
        observation = module.observe_delegation(
            server=server,
            parent_thread_id=parent,
            events=[completed_spawn(sender=parent, receivers=["child-a"])],
        )
        self.assertEqual(observation.nested_receiver_ids, ["grandchild"])

    def test_duplicate_and_empty_spawn_packet_are_detected(self) -> None:
        parent = "parent"
        server = FakeReadServer(
            {"child-a": child_thread("child-a", parent_id=parent)}
        )
        observation = module.observe_delegation(
            server=server,
            parent_thread_id=parent,
            events=[
                completed_spawn(sender=parent, receivers=["child-a"], prompt=""),
                completed_spawn(sender=parent, receivers=["child-a"]),
            ],
        )
        self.assertEqual(observation.direct_receiver_ids, ["child-a"])
        self.assertEqual(observation.duplicate_receiver_ids, ["child-a"])
        self.assertEqual(observation.empty_prompt_calls, 1)

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
        self.assertTrue(config["plugins"][module.base.PLUGIN_ID]["enabled"])
        self.assertFalse(config["plugins"]["foreign@marketplace"]["enabled"])
        self.assertFalse(config["features"]["apps"])
        self.assertFalse(config["memories"]["use_memories"])

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
            payload = __import__("json").loads(path.read_text(encoding="utf-8"))
            self.assertEqual(payload["outcome"], "HARNESS_ERROR")
            self.assertEqual(payload["error"], "boom")
            self.assertFalse(payload["plugin_state_restored"])


if __name__ == "__main__":
    unittest.main()
