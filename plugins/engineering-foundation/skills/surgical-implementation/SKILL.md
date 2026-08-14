---
name: surgical-implementation
description: Implement an accepted change with the smallest correct diff and one bounded cleanup pass. Use for feature, fix, or refactor execution; forbids drive-by cleanup and post-success rewrites.
---

# Surgical Implementation

## Before editing

- Verify branch, worktree, baseline tests when practical, and applicable instructions.
- Read the closest existing implementation and tests.
- Preserve public behavior not included in the goal.
- Reuse established project conventions before introducing a new pattern.

## Edit loop

1. Make one coherent slice.
2. Run the cheapest relevant feedback command.
3. Correct the slice before expanding.
4. Remove only imports, variables, tests, or helpers made obsolete by this change.
5. Add no dependency or abstraction without a demonstrated need.
6. Keep generated or formatting-only churn out of the diff.

## Refactor boundary

A refactor phase is allowed only before final verification and only inside the touched seam. It must reduce clear duplication or complexity introduced by the change while preserving tests.

After acceptance criteria pass, lock implementation. Do not:

- rewrite the solution into another architecture;
- generalize a one-use helper;
- “clean up” neighboring code;
- generate a second implementation for comparison;
- restart because a different style is possible.

Reopen only for failed evidence, a missed criterion, a concrete regression/security finding, or user-changed scope.

## Stop condition

Stop when the contract is satisfied, the final diff is minimal and understood, and the verification gate passes.
