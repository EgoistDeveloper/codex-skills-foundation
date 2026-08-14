---
name: bounded-multi-agent
description: Delegate genuinely independent engineering work while preserving one accountable orchestrator. Use for parallel read-heavy analysis or exclusive-file workstreams; never for small or tightly coupled changes.
---

# Bounded Multi-Agent

## Preconditions

Delegate only when all are true:

- at least two workstreams are independently useful;
- boundaries and expected outputs are explicit;
- coordination cost is lower than sequential work;
- the user has not disabled delegation.

## Default topology

- one primary orchestrator and final integrator;
- up to three concurrent specialists;
- delegation depth one;
- specialists read-only by default;
- one writer per file;
- shared files owned by the primary.

Prefer parallel agents for exploration, primary-source research, test-log analysis, and independent review. Be cautious with write-heavy work.

## Delegation packet

Each assignment includes:

- bounded question or deliverable;
- allowed files/tools;
- forbidden changes;
- evidence required;
- response budget;
- stop condition.

Each specialist returns:

- findings or patch summary;
- evidence and exact paths;
- uncertainties;
- no raw log dump unless requested.

## Integration

The primary agent:

1. checks every result against the goal;
2. resolves conflicts;
3. performs shared writes;
4. runs integrated verification;
5. closes completed threads;
6. makes the only completion claim.

## Stop condition

Stop delegation when the requested packets are returned. Do not create substitute work for an idle agent or recursively spawn more agents.
