---
name: verify-before-completion
description: Build an evidence matrix and gate completion on current command output, runtime observations, artifacts, and diff inspection. Use before claiming implementation, debugging, review fixes, milestones, or handoffs are complete. Do not use to infer, invent, recycle stale, or omit required evidence.
---


# Verify Before Completion

Match every acceptance ID to current evidence.

## Status vocabulary

- `PASS`: current workspace evidence satisfied the criterion.
- `FAIL`: current evidence did not satisfy it.
- `NOT_RUN`: relevant evidence was unavailable or blocked; state reason and risk.
- `NOT_APPLICABLE`: only for an optional criterion, with a concrete reason.

## Verification order

1. Static, schema, or syntax checks.
2. Focused tests for changed behavior.
3. Integration or broader regression tests proportional to risk.
4. Runtime, browser, query, migration, security, or provider checks when required.
5. Complete diff and working-tree inspection.

For command evidence record the exact command, `fresh: true`, integer exit code, concise result, and artifact path when useful. A passing linter cannot stand in for compilation or runtime behavior; another agent's confidence cannot stand in for a command.

`COMPLETE` requires exact acceptance coverage, all required IDs `PASS`, no unresolved required `FAIL`/`NOT_RUN`, a reviewed working tree, no unrelated diff, and honest remaining-risk disclosure.

Validate a durable packet with the packaged [scripts/evidence_gate.py](scripts/evidence_gate.py), resolving that path relative to this `SKILL.md` directory rather than the consumer repository:

```text
python <verify-before-completion-skill-directory>/scripts/evidence_gate.py completion-evidence.json --contract task-contract.json --workspace-root .
```

The helper is self-contained in the installed Core package and uses only the Python standard library. It checks structure and disclosure; it cannot prove a claimed command actually ran.
