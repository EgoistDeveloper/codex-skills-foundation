---
name: bounded-orchestration
description: Choose between one accountable agent and bounded delegation for independent research, review, verification, or disjoint workstreams. Use when a task has genuinely separable work. Do not use to fan out small tasks, duplicate implementation, overlap writers, or create recursive agent chains.
---


# Bounded Orchestration

Default to one accountable writing agent. Delegation has context, coordination, and verification cost; it is not free intelligence summoned by managerial enthusiasm.

## Delegate only when

At least one condition is true:

- a read-heavy repository survey can proceed independently;
- current external research is required;
- a specialist review differs materially from implementation;
- independent verification can run without editing shared files;
- implementation workstreams have disjoint write surfaces and explicit integration ownership.

## Limits

- Maximum three active workers.
- Delegation depth is one; a child never spawns another child.
- One writer owns each file at a time.
- The parent owns the task contract, integration, final diff, and completion claim.
- Reviewer and verifier roles are report-only by default.
- Never run parallel implementers against a shared write surface.
- Never ask several agents the same broad question merely to vote.

## Assignment packet

Give each worker one bounded outcome, allowed scope, explicit non-goals, required evidence, output format, and stop condition. Require a compact return packet containing facts with locations, actions taken, checks and exact status, unresolved risks, and the next atomic action.

Verify worker claims before integration. Stop delegating when enough evidence exists; do not begin another review loop without a new material finding.
