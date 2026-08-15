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
        *,
        task: bool = True,
        safety: bool = True,
        activation: bool = True,
        evidence: bool = True,
        repetition: int = 1,
        synthetic: bool = True,
        case_id: str = "case",
    ) -> dict:
        identities = {
            "baseline": ("disabled", None),
            "previous": ("0.1.0", "previous-sha"),
            "candidate": ("0.2.0", "candidate-sha"),
        }
        subject_version, subject_commit = identities[variant]
        return {
            "campaign_id": "campaign",
            "case_id": case_id,
            "case_revision": 1,
            "variant": variant,
            "provider": "test",
            "client": "test-client",
            "client_version": "1",
            "harness_commit": "harness-sha",
            "subject_version": subject_version,
            "subject_commit": subject_commit,
            "repetition": repetition,
            "synthetic": synthetic,
            "task_pass": task,
            "safety_pass": safety,
            "activation_pass": activation,
            "evidence_pass": evidence,
            "unrelated_files": 0,
            "post_completion_edits": 0,
            "tokens": 10,
            "tool_calls": 1,
            "agents_spawned": 0,
        }

    def matrix(self, *, include_previous: bool = False, **candidate_overrides: bool) -> list[dict]:
        rows = [self.row("baseline")]
        if include_previous:
            rows.append(self.row("previous"))
        rows.append(self.row("candidate", **candidate_overrides))
        return rows

    def test_candidate_passes_with_baseline(self) -> None:
        self.assertEqual(module.hard_gate_failures(self.matrix()), [])

    def test_previous_and_candidate_can_have_distinct_subject_commits(self) -> None:
        self.assertEqual(
            module.hard_gate_failures(self.matrix(include_previous=True), require_previous=True),
            [],
        )

    def test_same_previous_and_candidate_identity_is_rejected(self) -> None:
        rows = self.matrix(include_previous=True)
        rows[1]["subject_version"] = rows[2]["subject_version"]
        rows[1]["subject_commit"] = rows[2]["subject_commit"]
        failures = module.hard_gate_failures(rows, require_previous=True)
        self.assertTrue(any("same subject identity" in item for item in failures))

    def test_baseline_identity_is_strict(self) -> None:
        row = self.row("baseline")
        row["subject_commit"] = "not-disabled"
        with self.assertRaises(ValueError):
            module.validate_row(row, 1)

    def test_candidate_hard_gates_all_behavior_dimensions(self) -> None:
        for field in ("task", "safety", "activation", "evidence"):
            failures = module.hard_gate_failures(self.matrix(**{field: False}))
            self.assertTrue(any(f"candidate {field} failed" in item for item in failures), field)

    def test_baseline_failure_can_be_improved(self) -> None:
        rows = [self.row("baseline", safety=False), self.row("candidate", safety=True)]
        self.assertEqual(module.hard_gate_failures(rows), [])

    def test_baseline_and_previous_requirements(self) -> None:
        candidate = self.row("candidate")
        self.assertTrue(any("baseline missing" in item for item in module.hard_gate_failures([candidate])))
        failures = module.hard_gate_failures(self.matrix(), require_previous=True)
        self.assertTrue(any("previous release missing" in item for item in failures))

    def test_candidate_rows_are_required(self) -> None:
        self.assertEqual(module.hard_gate_failures([self.row("baseline")]), ["no candidate rows"])

    def test_repetition_sets_and_minimum_are_enforced(self) -> None:
        rows = [self.row("baseline", repetition=1), self.row("candidate", repetition=2)]
        failures = module.hard_gate_failures(rows)
        self.assertTrue(any("repetition mismatch" in item for item in failures))
        self.assertTrue(any("non-contiguous repetitions" in item for item in failures))
        failures = module.hard_gate_failures(self.matrix(), min_repetitions=3)
        self.assertTrue(any("repetitions below 3" in item for item in failures))

    def test_harness_identity_is_stable_per_campaign(self) -> None:
        rows = self.matrix()
        rows[1]["harness_commit"] = "another-harness"
        failures = module.hard_gate_failures(rows)
        self.assertTrue(any("multiple harness_commit" in item for item in failures))

    def test_loader_rejects_type_confusion_duplicates_and_mixed_classes(self) -> None:
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
            rows = self.matrix()
            for row in rows:
                row["synthetic"] = False
                row["artifact_path"] = "missing.json"
                row["notes"] = "trace unavailable: client did not expose a trace"
            failures = module.live_artifact_failures(rows, base)
            self.assertTrue(any("artifact missing" in item for item in failures))

            artifact = base / "artifact.json"
            artifact.write_text("{}\n", encoding="utf-8")
            for row in rows:
                row["artifact_path"] = "artifact.json"
            self.assertEqual(module.live_artifact_failures(rows, base), [])

    def test_synthetic_fixture_can_never_be_release_qualified(self) -> None:
        rows = module.load(ROOT / "evals/fixtures/sample-runs.jsonl")
        self.assertTrue(rows[0]["synthetic"])
        self.assertEqual(
            module.hard_gate_failures(rows, require_previous=True),
            [],
        )


if __name__ == "__main__":
    unittest.main()
