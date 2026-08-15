from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "run_codex_core_repeatability",
    ROOT / "scripts/run_codex_core_repeatability.py",
)
module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = module
assert SPEC.loader
SPEC.loader.exec_module(module)


class CodexCoreRepeatabilityTests(unittest.TestCase):
    def test_default_plan_alternates_case_order(self) -> None:
        plan = module.build_plan(3)
        self.assertEqual(
            [(step.case_key, step.repetition) for step in plan],
            [
                ("positive", 1),
                ("negative", 1),
                ("negative", 2),
                ("positive", 2),
                ("positive", 3),
                ("negative", 3),
            ],
        )
        self.assertEqual(len({step.step_id for step in plan}), 6)

    def test_manifest_counts_twelve_authenticated_turns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            campaign = Path(tmp) / "campaign"
            manifest = module.new_manifest(
                campaign=campaign,
                repetitions=3,
                harness_commit="abc123",
                client_version="0.147.0",
                subject_version="0.2.2",
            )
        self.assertEqual(manifest["expected_model_turns"], 12)
        self.assertEqual(len(manifest["plan"]), 6)
        self.assertEqual(manifest["outcome"], "IN_PROGRESS")

    def test_transform_rows_rewrites_parent_identity_and_artifact_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp) / "parent"
            child = parent / "runs" / "positive" / "rep-01" / "attempt-01" / "child"
            for variant in ("baseline", "candidate"):
                directory = child / variant
                directory.mkdir(parents=True, exist_ok=True)
                (directory / "trace.jsonl").write_text("{}\n", encoding="utf-8")
                (directory / "artifact.json").write_text("{}\n", encoding="utf-8")
            rows = [
                {
                    "campaign_id": "child",
                    "case_id": "debug-before-fix",
                    "case_revision": 2,
                    "variant": variant,
                    "harness_commit": "head",
                    "repetition": 1,
                    "trace_path": f"{variant}/trace.jsonl",
                    "artifact_path": f"{variant}/artifact.json",
                    "notes": "single child",
                }
                for variant in ("baseline", "candidate")
            ]
            transformed = module.transform_rows(
                rows=rows,
                child_campaign=child,
                parent_campaign=parent,
                parent_campaign_id="parent-campaign",
                spec=module.CASES["positive"],
                repetition=2,
                harness_commit="head",
            )
            self.assertEqual(
                {row["campaign_id"] for row in transformed},
                {"parent-campaign"},
            )
            self.assertEqual({row["repetition"] for row in transformed}, {2})
            for row in transformed:
                self.assertTrue((parent / row["trace_path"]).is_file())
                self.assertTrue((parent / row["artifact_path"]).is_file())
                self.assertIn("repetition 2", row["notes"])

    def test_transform_rows_rejects_case_revision_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp) / "parent"
            child = parent / "child"
            for variant in ("baseline", "candidate"):
                directory = child / variant
                directory.mkdir(parents=True, exist_ok=True)
                (directory / "trace.jsonl").write_text("{}\n", encoding="utf-8")
                (directory / "artifact.json").write_text("{}\n", encoding="utf-8")
            rows = [
                {
                    "campaign_id": "child",
                    "case_id": "tiny-edit-skips-plan",
                    "case_revision": 5,
                    "variant": variant,
                    "harness_commit": "head",
                    "repetition": 1,
                    "trace_path": f"{variant}/trace.jsonl",
                    "artifact_path": f"{variant}/artifact.json",
                }
                for variant in ("baseline", "candidate")
            ]
            with self.assertRaisesRegex(module.base.HarnessError, "case_revision"):
                module.transform_rows(
                    rows=rows,
                    child_campaign=child,
                    parent_campaign=parent,
                    parent_campaign_id="parent",
                    spec=module.CASES["negative"],
                    repetition=1,
                    harness_commit="head",
                )

    def test_identity_drift_is_rejected(self) -> None:
        canonical = {
            "client_version": "0.147.0",
            "harness_commit": "head",
            "subject_version": "0.2.2",
            "subject_commit": "head",
            "model": "gpt-test",
            "model_provider": "openai",
            "service_tier": "default",
        }
        records = [
            {"step_id": "positive-r01", "identity": canonical},
            {
                "step_id": "negative-r01",
                "identity": {**canonical, "model": "gpt-other"},
            },
        ]
        with self.assertRaisesRegex(module.base.HarnessError, "drift"):
            module.ensure_identity_stable(records)

    def test_metric_summary_uses_medians_and_pass_rates(self) -> None:
        def artifact(tokens: int, uncached: int, duration: int) -> dict[str, object]:
            return {
                "task_pass": True,
                "safety_pass": True,
                "activation_pass": True,
                "evidence_pass": True,
                "environment_pass": True,
                "tokens": tokens,
                "tool_calls": 2,
                "agents_spawned": 0,
                "duration_ms": duration,
                "token_usage": {"uncached_input_tokens": uncached},
            }

        records = [
            {
                "case_key": "positive",
                "baseline": artifact(10, 4, 100),
                "candidate": artifact(20, 8, 200),
            },
            {
                "case_key": "positive",
                "baseline": artifact(30, 12, 300),
                "candidate": artifact(40, 16, 400),
            },
        ]
        metrics = module.metric_summary(records)["positive"]
        self.assertEqual(metrics["baseline"]["median_tokens"], 20)
        self.assertEqual(metrics["candidate"]["median_uncached_input_tokens"], 12)
        self.assertEqual(metrics["candidate"]["task_pass_rate"], 1.0)

    def test_campaign_lock_is_exclusive_and_removed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            lock_path = Path(tmp) / "campaign.lock"
            campaign = Path(tmp) / "campaign"
            with module.CampaignLock(lock_path, campaign):
                self.assertTrue(lock_path.is_file())
                with self.assertRaises(module.base.HarnessError):
                    with module.CampaignLock(lock_path, campaign):
                        pass
            self.assertFalse(lock_path.exists())

    def test_failure_diagnostics_are_machine_readable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            campaign = Path(tmp) / "campaign"
            campaign.mkdir()
            manifest = {
                "schema_version": 1,
                "campaign": "campaign",
                "outcome": "IN_PROGRESS",
                "completed": [],
            }
            module.finalize_failure(
                campaign=campaign,
                manifest=manifest,
                reason="candidate failed",
                record={"step_id": "negative-r01", "outcome": "FAIL"},
            )
            payload = json.loads(
                (campaign / "failure-diagnostics.json").read_text(encoding="utf-8")
            )
            self.assertEqual(payload["outcome"], "FAIL")
            self.assertEqual(payload["failed_child"]["step_id"], "negative-r01")


if __name__ == "__main__":
    unittest.main()
