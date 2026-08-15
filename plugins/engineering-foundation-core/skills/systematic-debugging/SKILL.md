---
name: systematic-debugging
description: Diagnose a reproducible defect through evidence, ranked hypotheses, isolation, a minimal fix, and a regression guard. Use for failures, flaky tests, performance regressions, unexpected behavior, or unclear root causes. Do not use random patches as experiments or for ordinary feature implementation.
---

# Systematic Debugging

## Reproduction gate

- When a reproduction command is supplied and runnable, execute it before editing production code and record the observed failure.
- Reading source code, tests, logs, or an obvious-looking defect is not reproduction.
- Do not edit under an assumed failure. If the command cannot run, make at most one direct attempt and one bounded repository-local fallback, then report `BLOCKED` or `NOT_REPRODUCED`.
- Do not scan system directories, install or download runtimes, or borrow an unrelated environment merely to force a reproduction.
- After the fix, rerun the same reproduction command and report only the result actually observed.

## Procedure

1. Capture the exact symptom, expected behavior, input, environment, and reproduction command.
2. Classify the failure as deterministic, intermittent, blocked, or not reproduced.
3. Localize the earliest incorrect state with logs, traces, focused tests, query inspection, or binary search.
4. Reduce to the smallest reliable reproducer.
5. Rank a small set of falsifiable hypotheses.
6. Run the cheapest experiment that distinguishes the leading hypothesis.
7. Change the root cause, not the final visible symptom.
8. Add a regression guard that fails before the fix and passes after it when practical.
9. Remove temporary instrumentation and run targeted plus risk-proportional broader verification.

Change one causal variable at a time. Do not accumulate speculative edits and call the eventual green test a diagnosis. Performance claims require comparable before/after measurement. Never add a fallback that silently masks authorization failure, data corruption, or invariant violations.

If reproduction is unavailable, preserve observations, state the missing evidence, and give the safest next diagnostic action. Do not manufacture certainty merely because completion statuses look lonely.
