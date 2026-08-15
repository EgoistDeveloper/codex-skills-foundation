---
name: review-diff
description: Review a proposed diff against its task contract for correctness, regressions, security, tests, and maintainability, using severity, confidence, and concrete evidence. Use after an implementation reaches a reviewable state or when the user asks for review. Do not use to rewrite code for taste or create endless review loops.
license: MIT
metadata:
  author: EgoistDeveloper
  version: "0.2.0"
---

# Review Diff

Review the change, not the author's personality and not an imaginary greenfield system.

## Method

1. Read the task contract and relevant repository guidance.
2. Inspect the complete diff and surrounding code required to understand it.
3. Check acceptance, behavior, error paths, data/security boundaries, compatibility, tests, and observability.
4. Run focused checks when permitted.
5. Deduplicate findings by root cause.

## Finding format

For each material finding provide:

- severity: `critical`, `high`, `medium`, or `low`;
- confidence: `high`, `medium`, or `low`;
- file and precise location;
- concrete failure mode;
- evidence or reproduction;
- smallest credible remediation.

Do not report style preference as a defect. Suppress low-confidence speculation unless it identifies a high-impact risk and is clearly labeled.

Default to report-only. One repair-and-rereview cycle is enough unless a new material defect appears. If no material findings exist, state that plainly and stop.
