---
name: verification-gate
description: Gate any claim that work is complete, fixed, safe, or passing on fresh requirement-level evidence. Use before commit, PR, handoff, or task completion.
---

# Verification Gate

Evidence precedes every success claim.

## Gate

1. Re-read the accepted goal and final diff.
2. For each criterion, identify the command or observation that proves it.
3. Run fresh commands in the current worktree.
4. Read complete exit status and relevant output; do not infer one check from another.
5. Record requirement-level evidence.
6. List unresolved failures, skipped checks, unavailable tools, and environment differences.
7. Run the deterministic gate when a packet exists:

   ```bash
   python <skill-root>/../../scripts/evidence_gate.py evidence.json
   ```

## Invalid evidence

- an earlier run before the final edit;
- “should pass” or confidence;
- another agent's success statement;
- a linter standing in for compilation or runtime behavior;
- partial tests presented as the full suite;
- screenshots without interaction/state checks;
- passing tests with an unreviewed diff.

## Honest outcomes

- **PASS:** all required evidence is current and positive.
- **PARTIAL:** useful work exists, but one or more checks were unavailable or unresolved.
- **FAIL:** a required criterion or command failed.

Only PASS may close the task. PARTIAL and FAIL must state the exact next action.

## Stop condition

Stop after reporting the evidence-backed state. Do not reopen implementation after PASS unless a valid reopen reason appears.
