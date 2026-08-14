# Architecture

## Design goal

The foundation minimizes four common failure modes:

1. **Misalignment:** implementation begins before success is defined.
2. **Scope drift:** the agent touches adjacent code or invents requirements.
3. **Coordination waste:** multi-agent is used where a single agent is cheaper and safer.
4. **False completion:** the agent claims success without fresh evidence.

## Layers

```text
Portable contract
├── Agent Plugins v1 manifest
├── Agent Skills workflows
├── deterministic router and evidence gate
└── behavior eval cases

Client adapters
├── Codex marketplace and compatibility manifest
├── Codex custom-agent TOML templates
├── Claude Code marketplace, manifest, and agents
└── Hermes / generic Agent Skills compatibility guidance

Project context
├── AGENTS.md
├── project-specific DESIGN.md or CONTEXT.md
├── framework conventions
└── actual tests, linters, builds, and runtime evidence
```

The portable layer must not depend on a current model name, provider-specific billing, or a private API.

## State machine

```text
INTAKE
  → CONTRACT
  → ROUTE
  → RESEARCH? 
  → PLAN?
  → IMPLEMENT
  → VERIFY
  → REVIEW?
  → COMPLETE
```

`COMPLETE` is a lock, not an invitation to polish again. Reopen only when:

- a verification command fails;
- an acceptance criterion lacks evidence;
- a concrete regression or security issue is found;
- the user changes scope.

“Could be cleaner” is not a reopen reason.

## Writing ownership

The primary agent is the default and final integrator. Specialist agents are read-only unless the user explicitly opts into a partitioned write workflow. The bundled specialists intentionally use read-only sandboxes.

For rare parallel write work:

- each worker receives exclusive file ownership;
- shared files remain owned by the primary;
- delegation depth is one;
- the primary re-runs integrated verification;
- no agent accepts another agent's completion claim as proof.

## Token discipline

- Skill descriptions are short because they are always candidates for the initial skill index.
- Full instructions load only when the skill triggers.
- Large checklists live in `references/`.
- Read-heavy exploration may move to subagents to avoid context pollution.
- Small, coupled, or write-heavy work stays in one thread.
- Plan review is capped at two material cycles.
- Code review is one independent pass plus one re-check only when material fixes were made.

## Model policy

The foundation uses capability classes rather than model names:

- **economy:** deterministic extraction, file inventory, simple checks;
- **standard:** normal implementation and bounded planning;
- **deep:** architecture, difficult debugging, high-risk review;
- **independent-deep:** fresh-context audit for consequential decisions.

Clients may map these classes to current models. The mapping is deployment configuration, not portable skill logic.

## Evidence contract

A valid completion packet contains:

- every requirement marked pass;
- concrete evidence for every requirement;
- fresh verification command results;
- a reviewed final diff;
- no unresolved blocker;
- actual limitations stated plainly.

The deterministic `evidence_gate.py` enforces the machine-checkable subset.
