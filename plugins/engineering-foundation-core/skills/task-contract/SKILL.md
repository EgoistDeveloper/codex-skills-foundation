---
name: task-contract
description: Define a concrete engineering task contract with objective, acceptance criteria, non-goals, constraints, evidence, and reopen conditions. Use when starting implementation, debugging, review, or a long-running goal. Do not use to create ceremony for a tiny deterministic edit whose done state is already explicit.
license: MIT
metadata:
  author: EgoistDeveloper
  version: "0.2.0"
---

# Task Contract

Create a compact contract before changing code. Keep it in working context for small tasks. Write `docs/exec-plans/<task>.md` only when the task is long-running, cross-cutting, risky, or likely to survive a session handoff.

## Contract

Record:

- **Objective:** one observable outcome.
- **Acceptance:** conditions that must be true.
- **Non-goals:** nearby work intentionally excluded.
- **Constraints:** compatibility, safety, scope, time, or tooling limits.
- **Evidence:** commands, artifacts, or inspections that can prove acceptance.
- **Risk:** low, medium, or high, with the reason.
- **Reopen conditions:** failed evidence, unmet acceptance, changed requirements, or a material regression/security finding.

Do not treat a provider `/goal` status as proof. It may track intent, but the contract and evidence determine completion.

## Scale

- **Tiny:** hold the contract in one sentence; no plan artifact.
- **Normal:** list acceptance and evidence before editing.
- **Complex/high risk:** create an executable plan and milestones with the `plan-and-milestones` skill.

## Boundaries

Infer harmless details from repository conventions. Ask only when a missing decision materially changes product behavior, security, data, or irreversible work. Never broaden scope merely because neighboring code looks untidy.

A task is complete only when every acceptance item is `PASS` or legitimately `NOT_APPLICABLE`. A required `NOT_RUN` item keeps the task partial until the evidence runs or the user explicitly changes the acceptance contract.
