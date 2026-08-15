---
name: plan-and-milestones
description: Create and maintain an executable plan with decisions, risks, milestones, validation, and stop conditions. Use for cross-cutting, uncertain, high-risk, migration, or multi-session work. Do not use for a small localized change that can be implemented and verified directly.
---


# Plan and Milestones

Plan only when planning reduces uncertainty, coordinates boundaries, or preserves state across sessions. A long narrative is not a plan; it is prose wearing a hard hat.

## Plan contents

1. Link or restate the task contract.
2. Record repository facts already verified.
3. Record material decisions and rejected alternatives.
4. Identify affected boundaries, migration/rollback concerns, and compatibility risks.
5. Define dependency-ordered milestones as observable end states.
6. Attach evidence and failure action to every milestone.
7. Define final completion and reopen conditions.

## Milestone form

For each milestone record:

- status: `PENDING`, `ACTIVE`, `BLOCKED`, `VERIFIED`, or `SUPERSEDED`;
- outcome;
- files or subsystem boundary;
- dependencies;
- implementation steps;
- evidence commands or artifacts;
- failure/rollback action;
- next milestone.

Do not use percentage-complete guesses. Update the plan after material discoveries, not after every keystroke. Preserve decision history by marking stale work `SUPERSEDED` instead of quietly rewriting history.

One independent plan review is sufficient by default. Permit a second review only after material changes; stop after two cycles if unresolved blockers remain. A host `/plan` or `/goal` can mirror the plan, but durable work must not depend on provider-only state.
