---
name: handoff
description: Produce a compact, durable transfer packet for another session, agent, machine, or provider while preserving decisions, repository state, evidence, risks, and the next atomic action. Use when context is ending, work changes owner, or a handoff is requested. Do not dump the full transcript, raw logs, secrets, or unsupported claims.
---


# Handoff

Distinguish three mechanisms:

1. **Native host handoff:** the client transfers conversation and workspace state.
2. **Durable session artifact:** provider-neutral project state that survives clients or context resets.
3. **Worker return packet:** a bounded subagent result.

## Required packet

- task ID, objective, acceptance IDs, non-goals, and constraints;
- repository, branch, baseline/head commit, and working-tree state;
- accepted decisions and relevant rejected alternatives;
- completed work with file locations;
- checks run with `PASS`, `FAIL`, or `NOT_RUN`;
- unresolved findings, risks, and uncertainty;
- exact next atomic action and commands required to resume;
- provenance for external research.

Link plans, diffs, reports, and logs instead of copying them. Exclude credentials, personal data, raw search history, irrelevant conversation, and speculative ideas not adopted.

A receiver must be able to verify state without trusting the previous agent's confidence. The handoff is complete when a fresh agent can continue without repeating broad exploration and can distinguish fact, decision, evidence, and open question.
