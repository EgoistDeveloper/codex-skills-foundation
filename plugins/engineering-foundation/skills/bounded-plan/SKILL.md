---
name: bounded-plan
description: Produce a minimal dependency-ordered implementation plan for multi-file, risky, or unfamiliar work. Do not use for trivial edits or continue revising a plan after material gaps are resolved.
---

# Bounded Plan

Plan only enough to make implementation predictable.

## Process

1. Confirm the accepted goal contract and baseline.
2. Trace the relevant code path, tests, data boundaries, and public interfaces.
3. Identify the smallest coherent change set.
4. Order tasks by dependency. For each task record:
   - expected files or seam;
   - behavior to add or preserve;
   - verification;
   - risk and rollback note when relevant.
5. Mark work that can be read in parallel, but keep shared writes with the primary agent.
6. Request one independent plan review only for high-risk, unfamiliar, or cross-domain work.
7. Revise only material gaps. Cap review at two cycles; unresolved blockers stop implementation.

## Quality bar

A plan must prevent scope drift, not narrate every keystroke. It must not prescribe speculative abstractions, unrelated cleanup, or duplicate artifacts in multiple plan systems.

## Stop condition

Stop planning when a competent implementer can execute the tasks and prove the goal without making a new architectural decision.
