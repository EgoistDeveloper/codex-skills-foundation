# Runtime workflow

## Tiny task

`contract in context -> implement -> targeted verification -> complete`

No plan file and no subagent unless a material risk appears.

## Normal task

`task contract -> short plan in context -> implementation -> evidence matrix -> optional report-only review -> complete`

## Complex or high-risk task

`durable contract -> executable plan -> observable milestones -> bounded delegation -> integration -> independent review -> verification -> handoff or complete`

## Goal

A goal is the durable outcome contract:

- objective;
- non-goals;
- acceptance criteria;
- constraints;
- validation;
- stop and reopen conditions.

A provider `/goal` command may mirror this state but is not proof of completion.

## Plan

A plan resolves implementation uncertainty. Skip it when the work is obvious and local. For long work, check it into `docs/exec-plans/` so it survives context compression and provider handoff.

## Milestones

Milestones are observable end states with evidence and rollback, not percentage estimates. Their purpose is repairability and continuity, not project-management decoration.

## Handoff

Use native host handoff when convenient, but write a provider-neutral artifact for work that must survive clients or sessions. The artifact points to evidence instead of dumping the conversation.
