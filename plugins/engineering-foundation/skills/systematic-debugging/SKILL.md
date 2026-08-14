---
name: systematic-debugging
description: Diagnose a reproducible bug, flaky test, build failure, or performance regression before editing. Use when the cause is uncertain; do not use random patches as experiments.
---

# Systematic Debugging

## Process

1. **Reproduce:** capture the exact command, input, environment, expected result, and actual result.
2. **Localize:** narrow the failing layer with logs, traces, binary search, focused tests, or query inspection.
3. **Reduce:** create the smallest reliable reproducer.
4. **Hypothesize:** list a small number of falsifiable causes, ordered by evidence.
5. **Instrument:** gather the minimum data that distinguishes them.
6. **Fix:** change the root cause, not the visible symptom.
7. **Guard:** add a regression test or durable check.
8. **Clean:** remove temporary instrumentation and verify the final diff.

## Constraints

- One hypothesis-driven experiment at a time.
- No broad dependency upgrade unless evidence points to it.
- No production fallback that silently masks data corruption or authorization failure.
- If reproduction is impossible, report the evidence gap and safest next diagnostic step.
- Performance claims require before/after measurements using comparable conditions.

## Stop condition

Stop when the original symptom is reproduced, the causal mechanism is supported, the fix removes it, and a guard prevents recurrence.
