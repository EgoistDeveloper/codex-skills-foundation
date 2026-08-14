---
name: test-first-change
description: Build or fix behavior through a bounded red-green-refactor loop at a stable seam. Use when an automated regression test is practical; adapt honestly when the repository lacks a suitable harness.
---

# Test-First Change

## Loop

1. Find the narrowest observable behavior boundary.
2. Confirm the existing baseline.
3. Add or adjust a test that fails for the intended reason.
4. Run it and read the failure.
5. Write the minimum production change.
6. Run the targeted test until green.
7. Perform at most one local refactor that preserves behavior.
8. Run related checks, then the required broader suite.
9. Review the test: it should prove behavior, not implementation trivia.

## Constraints

- Do not weaken assertions to make the test pass.
- Do not mock the unit under test.
- Do not hide unrelated baseline failures.
- Do not delete code written before the test as a ritual; inspect and correct the actual sequence.
- For UI behavior, use component, browser, accessibility, or visual checks appropriate to the project.
- For migrations and performance, include data or query evidence, not only unit tests.

## Stop condition

The change is ready for verification when the test demonstrated red for the right reason, green after the minimal fix, and no unsupported behavior was added.
