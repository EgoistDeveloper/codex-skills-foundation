---
name: surgical-implementation
description: Implement an accepted change with the smallest coherent diff, repository-local conventions, focused tests, and one bounded cleanup before final verification. Use when modifying code or configuration. Do not use for open-ended redesign or unrelated cleanup.
license: MIT
metadata:
  author: EgoistDeveloper
  version: "0.2.0"
---

# Surgical Implementation

## Before editing

- Inspect the working tree and nearby patterns.
- Identify the owning layer and tests.
- Preserve unrelated user changes.
- Confirm the task contract and intended evidence.

## Implement

1. Change the smallest coherent surface that satisfies acceptance.
2. Follow local naming, architecture, error handling, and test style before importing a new pattern.
3. Add dependencies only with an explicit need and compatibility check.
4. Add or update the narrowest meaningful regression test.
5. Run targeted feedback early.

## Cleanup boundary

One bounded cleanup pass is allowed **before** final verification when it directly improves the changed code and does not alter the contract. After final evidence passes, stop.

Do not:

- generalize a one-use helper without demonstrated reuse;
- refactor neighboring code because it is available;
- replace a working approach with a second architecture after acceptance passes;
- repeat formatting, test, or review loops without new information;
- hide behavior changes inside “cleanup.”

Reopen implementation only for failed evidence, unmet acceptance, changed requirements, or a concrete regression/security finding.
