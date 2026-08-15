---
name: bounded-orchestration
description: Decide whether to stay single-agent or delegate bounded read-heavy, independent, or specialist work to subagents. Use when a task has separable research, review, verification, or independent workstreams. Do not use to fan out small tasks, duplicate implementation, or create recursive agent chains.
license: MIT
metadata:
  author: EgoistDeveloper
  version: "0.2.0"
---

# Bounded Orchestration

Default to one agent. Delegation has a context, coordination, and verification cost; it is not free intelligence summoned from the cloud by managerial enthusiasm.

## Delegate only when

At least one is true:

- a read-heavy repository survey can proceed independently;
- current external research is required;
- a specialist review is materially different from implementation;
- independent verification can run without editing shared files;
- two implementation workstreams have disjoint write surfaces and clear integration ownership.

## Limits

- Maximum three active workers.
- Delegation depth is one. A child does not spawn another child.
- One writer owns each file at a time.
- The parent owns the task contract, integration, final diff, and completion claim.
- Reviewer and verifier roles are report-only by default.
- Never run parallel implementers against a shared write surface.
- Never ask multiple agents the same broad question merely to vote.

## Assignment packet

Give each worker:

- one bounded question or outcome;
- allowed read/write scope;
- explicit non-goals;
- required evidence;
- output format;
- stop condition.

## Return packet

Require:

- facts with file/source locations;
- actions taken;
- checks run and exact status;
- unresolved risks;
- recommended next atomic action.

Verify child claims before integrating them. End delegation when the parent has enough evidence; do not start a second review loop without a new material finding.
