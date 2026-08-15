---
name: surgical-implementation
description: Implement an accepted change with the smallest coherent diff, repository-local conventions, focused tests, and one bounded cleanup before final verification. Use when modifying code or configuration. Do not use for open-ended redesign, drive-by cleanup, or post-success rewrites.
---


# Surgical Implementation

## Before editing

- Inspect the working tree and nearest repository instructions.
- Trace the owning layer, nearby implementation, and tests.
- Preserve unrelated user changes and public behavior outside the contract.
- Confirm acceptance IDs and intended evidence.

## Change loop

1. Choose the smallest stable behavior seam.
2. When a meaningful automated regression test is practical, make it fail for the intended reason before the production change.
3. Implement one coherent slice using local naming, architecture, error handling, and test style.
4. Run the cheapest relevant feedback command early.
5. Correct that slice before expanding scope.
6. Add a dependency or abstraction only for a demonstrated need.
7. Remove only code made obsolete by this change.

Use `references/test-first-change.md` for the bounded red-green-refactor protocol.

## Cleanup boundary

One local cleanup pass is allowed **before** final verification when it improves the touched seam without changing the contract. After evidence passes, stop.

Do not generalize a one-use helper, refactor neighboring code because it is nearby, produce a second architecture for comparison, or repeat formatting/test/review loops without new information. Reopen only for failed evidence, unmet acceptance, changed requirements, or a concrete regression/security finding.
