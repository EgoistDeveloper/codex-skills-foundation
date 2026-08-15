---
name: systematic-debugging
description: Diagnose a reproducible defect through evidence, ranked hypotheses, isolation, a minimal fix, and a regression test. Use for failures, flaky tests, performance regressions, unexpected behavior, or unclear root causes. Do not use for ordinary feature implementation.
license: MIT
metadata:
  author: EgoistDeveloper
  version: "0.2.0"
---

# Systematic Debugging

## Sequence

1. Capture the symptom, expected behavior, environment, and exact reproduction.
2. Establish whether the failure is deterministic, intermittent, or not reproduced.
3. Gather logs, stack traces, failing inputs, timing, queries, and recent relevant changes.
4. Rank a small set of falsifiable hypotheses.
5. Run the cheapest discriminating experiment for the leading hypothesis.
6. Identify the earliest incorrect state, not merely the final exception.
7. Apply the smallest root-cause fix.
8. Add a regression test that fails before the fix and passes after it when practical.
9. Run targeted and relevant broader verification.

## Discipline

Change one causal variable at a time. Do not accumulate speculative edits and call the final green test a diagnosis. Revert experiments that do not contribute to the fix.

If reproduction is unavailable, report `NOT_REPRODUCED`, preserve observations, and state what evidence is missing. Do not manufacture certainty to make the status emotionally satisfying.
