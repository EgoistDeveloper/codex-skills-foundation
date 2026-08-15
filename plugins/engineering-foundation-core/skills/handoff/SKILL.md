---
name: handoff
description: Produce a compact, durable transfer packet for another session, agent, machine, or provider, preserving decisions, repository state, evidence, risks, and the next atomic action. Use when context is ending, work changes owner, or the user requests a handoff. Do not dump the full transcript or include secrets.
license: MIT
metadata:
  author: EgoistDeveloper
  version: "0.2.0"
---

# Handoff

Distinguish three mechanisms:

1. **Native host handoff:** the client transfers chat and repository state.
2. **Session handoff artifact:** durable project state in a file.
3. **Worker return packet:** a bounded subagent result.

Native transfer is convenient, but the durable artifact is the provider-neutral source when work must survive clients or sessions.

## Required packet

- objective and acceptance criteria;
- non-goals and constraints;
- current branch/commit and working-tree status when available;
- decisions and why they were made;
- completed work with file locations;
- checks run with `PASS`, `FAIL`, or `NOT_RUN`;
- unresolved findings and hazards;
- exact next atomic action;
- source/provenance references for external research;
- commands needed to resume safely.

Keep the packet compact. Link to plans, diffs, reports, and logs instead of copying them. Exclude secrets, credentials, personal data, irrelevant conversation, and unsupported claims.

A receiver must be able to verify state without trusting the previous agent's confidence.
