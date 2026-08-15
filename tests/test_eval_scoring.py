from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("score_eval_runs", ROOT / "scripts/score_eval_runs.py")
module = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(module)


class EvalScoringTests(unittest.TestCase):
    def row(
        self,
        variant: str,
        task: bool = True,
        safety: bool = True,
        activation: bool = True,
        evidence: bool = True,
        repetition: int = 1,
        synthetic: bool = True,
    ) -> dict:
        return {
            "campaign_id": "campaign", "case_id": "case", "case_revision": 1,
            "variant": variant, "provider": "test", "client": "test-client",
            "client_version": "1", "package_commit": "abc1234", "repetition": repetition,
            "synthetic": synthetic, "task_pass": task, "safety_pass": safety,
            "activation_pass": activation, "evidence_pass": evidence, "unrelated_files": 0,
            "post_completion_edits": 0, "tokens": 10, "tool_calls": 1,
            "agents_spawned": 0,
        }

    def paired(self, **candidate_overrides: bool) -> list[dict]:
        return [self.row("baseline"), self.row("candidate", **candidate_overrides)]

    def test_candidate_passes_with_baseline(self) -> None:
        self.assertEqual(module.hard_gate_failures(self.paired()), [])

    def test_baseline_failure_can_be_improved(self) -> None:
        rows = [self.row("baseline", safety=False), self.row("candidate", safety=True)]
        self.assertEqual(module.hard_gate_failures(rows), [])

    def test_candidate_hard_gates_all_behavior_dimensions(self) -> None:
        for field in ("task", "safety", "activation", "evidence"):
            failures = module.hard_gate_failures(self.paired(**{field: False}))
            self.assertTrue(any(f"candidate {field} failed" in item for item in failures), field)

    def test_baseline_is_required(self) -> None:
        failures = module.hard_gate_failures([self.row("candidate")])
        self.assertTrue(any("baseline missing" in item for item in failures))

    def test_previous_can_be_required(self) -> None:
        failures = module.hard_gate_failures(self.paired(), require_previous=True)
        self.assertTrue(any("previous release missing" in item for item in failures))

    def test_candidate_rows_are_required(self) -> None:
        self.assertEqual(module.hard_gate_failures([self.row("baseline")]), ["no candidate rows"])

    def test_repetition_sets_must_match(self) -> None:
        rows = [self.row("baseline", repetition=1), self.row("candidate", repetition=2)]
        self.assertTrue(any("repetition mismatch" in item for item in module.hard_gate_failures(rows)))

    def test_minimum_repetitions_are_enforced(self) -> None:
        failures = module.hard_gate_failures(self.paired(), min_repetitions=3)
        self.assertTrue(any("repetitions below 3" in item for item in failures))

    def test_loader_rejects_string_boolean_duplicates_and_mixed_evidence_classes(self) -> None:
        bad = self.row("candidate")
        bad["task_pass"] = "false"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rows.jsonl"
            path.write_text(json.dumps(bad) + "\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                module.load(path)

        duplicate = self.row("candidate")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rows.jsonl"
            path.write_text(json.dumps(duplicate) + "\n" + json.dumps(duplicate) + "\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                module.load(path)

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rows.jsonl"
            path.write_text(
                json.dumps(self.row("baseline", synthetic=True)) + "\n"
                + json.dumps(self.row("candidate", synthetic=False)) + "\n",
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                module.load(path)

    def test_live_artifact_paths_must_exist_and_stay_under_run_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            rows = self.paired(synthetic=False)
            for row in rows:
                row["artifact_path"] = "missing.json"
                row["notes"] = "trace unavailable: client did not expose a trace"
            failures = module.live_artifact_failures(rows, base)
            self.assertTrue(any("artifact missing" in item for item in failures))

            artifact = base / "artifact.json"
            artifact.write_text("{}\n", encoding="utf-8")
            for row in rows:
                row["artifact_path"] = "artifact.json"
            self.assertEqual(module.live_artifact_failures(rows, base), [])


if __name__ == "__main__":
    unittest.main()
