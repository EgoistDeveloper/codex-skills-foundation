---
name: review-diff
description: Review a proposed diff against its task contract for correctness, regressions, security, compatibility, tests, and maintainability. Use after a material implementation reaches a reviewable state or when review is requested. Do not use to rewrite code for taste, manufacture style findings, or create endless review loops.
---


# Review Diff

Review the change, not the author's personality and not an imaginary greenfield system.

## Method

1. Read the task contract and applicable repository guidance.
2. Inspect the complete diff and only the surrounding code required to establish behavior.
3. Check acceptance, non-goals, error paths, state transitions, authorization, data/concurrency boundaries, compatibility, observability, and tests.
4. Run focused checks when permitted.
5. Deduplicate findings by root cause.

## Finding format

For every material finding provide:

- severity: `critical`, `high`, `medium`, or `low`;
- confidence: `high`, `medium`, or `low`;
- precise file/location;
- concrete failure scenario and impact;
- evidence or reproduction;
- smallest credible remediation.

Do not report formatter output, personal style preferences, or unrelated debt as defects. Suppress low-confidence speculation unless it identifies a high-impact risk and is labeled clearly. Default to report-only. One repair-and-rereview cycle is enough unless a new material defect appears. If no material finding is supported, say so and stop.
