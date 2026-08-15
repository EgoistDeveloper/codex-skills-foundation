---
name: task-contract
description: Define a compact task contract with objective, acceptance IDs, non-goals, constraints, evidence, risk, and reopen conditions. Use when starting implementation, debugging, review, or durable work. Do not use to create ceremony for an obvious one-line edit.
---


# Task Contract

Create the smallest contract that makes completion testable before changing code. Keep tiny contracts in working context; write a durable plan only when work is cross-cutting, risky, uncertain, or likely to survive a session boundary.

## Contract fields

- **Task ID:** stable identifier used by evidence and handoff packets.
- **Objective:** one observable outcome.
- **Context:** repository facts that materially constrain the task.
- **Assumptions:** narrow, explicit assumptions needed to proceed.
- **Acceptance:** stable IDs such as `A1`, each with one independently verifiable criterion and an evidence hint.
- **Non-goals:** nearby work intentionally excluded.
- **Constraints:** compatibility, security, data, performance, tooling, branch, and permission boundaries.
- **Risk:** `low`, `medium`, or `high`, plus a concise reason.
- **Reopen conditions:** failed evidence, unmet acceptance, changed requirements, or a concrete regression/security finding.

## Scale

- **Tiny:** hold the contract in one sentence; no file.
- **Normal:** list acceptance IDs and evidence before editing.
- **Complex/high risk:** create an executable plan with `plan-and-milestones`.

Inspect repository evidence before asking a question the code can answer. Ask only when a missing decision materially changes product behavior, security, data, compatibility, or irreversible work. A host `/goal` may mirror intent, but it is not completion evidence.

Completion requires every required acceptance ID to have current evidence. A required `NOT_RUN` keeps the task partial until the check runs or the user explicitly changes the contract.
