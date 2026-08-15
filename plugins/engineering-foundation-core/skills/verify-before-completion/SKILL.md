---
name: verify-before-completion
description: Build an evidence matrix and gate completion on current, relevant command output and artifact inspection. Use before claiming implementation, debugging, review fixes, or a milestone is complete. Do not use to invent evidence for checks that were not run.
license: MIT
metadata:
  author: EgoistDeveloper
  version: "0.2.0"
---

# Verify Before Completion

Match each acceptance criterion to evidence.

## Status vocabulary

- `PASS`: ran or inspected in the current workspace and satisfied the criterion.
- `FAIL`: ran or inspected and did not satisfy it.
- `NOT_RUN`: relevant but unavailable, unaffordable, or blocked; include the reason and risk.
- `NOT_APPLICABLE`: explain why the criterion does not apply.

## Verification order

1. Static or schema checks.
2. Focused tests for the changed behavior.
3. Integration or broader regression tests proportional to risk.
4. Runtime, browser, query, migration, or security checks when the change requires them.
5. Diff and working-tree inspection.

Capture command, exit status, and a concise result. Do not paste enormous logs when a summary plus artifact path is sufficient.

## Completion gate

`COMPLETE` requires:

- every acceptance item mapped to evidence;
- every required item is `PASS` or legitimately `NOT_APPLICABLE`;
- no unresolved `FAIL` or required `NOT_RUN`;
- no unrelated diff;
- no known high-severity regression or security finding;
- final state and remaining risk reported accurately.

A required `NOT_RUN` is disclosed honestly **and keeps the task `PARTIAL`**. It becomes compatible with completion only when the evidence runs or the user explicitly changes the acceptance contract first.

When a durable task contract exists, compare the evidence matrix against it rather than validating only the rows the agent chose to include. A unit test proving an evidence parser works is not evidence that an agent supplied truthful evidence. Live behavior qualification remains separate.
