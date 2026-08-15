---
name: plan-and-milestones
description: Produce and maintain an executable implementation plan with decisions, risks, milestones, validation, and stop conditions. Use for cross-cutting, uncertain, high-risk, or multi-session work. Do not use for a small localized change that can be implemented and verified directly.
license: MIT
metadata:
  author: EgoistDeveloper
  version: "0.2.0"
---

# Plan and Milestones

Plan only when planning reduces uncertainty or coordinates work. A long narrative is not a plan; it is merely prose wearing a hard hat.

## Plan contents

1. Link or restate the task contract.
2. Summarize repository facts already verified.
3. Record decisions and rejected alternatives only when they affect implementation.
4. List affected boundaries, data migrations, compatibility risks, and rollback needs.
5. Define milestones as observable end states.
6. Attach evidence to each milestone.
7. Define final completion and reopen conditions.

## Milestone form

For every milestone record:

- outcome;
- files or subsystem boundary;
- dependencies;
- implementation steps;
- evidence commands or artifacts;
- failure/rollback action;
- next milestone.

Do not use percentage-complete guesses. A milestone is `PENDING`, `ACTIVE`, `BLOCKED`, `VERIFIED`, or `SUPERSEDED`.

## Provider controls

A host `/plan` or `/goal` command may mirror the plan, but it does not replace the checked-in artifact for durable work. Keep provider-specific state thin so a handoff to another client does not erase the engineering record.

## Maintenance

Update the plan after material discoveries, not after every keystroke. Preserve decision history. Remove stale steps or mark them superseded rather than quietly pretending they never existed.
