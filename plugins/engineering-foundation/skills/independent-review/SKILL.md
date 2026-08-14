---
name: independent-review
description: Review a bounded diff from fresh context for goal compliance and material engineering risks. Use before merge on consequential changes; do not invent stylistic work when no defect exists.
---

# Independent Review

Review from the accepted goal, applicable repository rules, and actual diff.

## Axes

1. **Contract:** every criterion implemented, no non-goal added.
2. **Correctness:** edge cases, error paths, state transitions, concurrency, data integrity.
3. **Security:** authorization, validation, secrets, injection, unsafe defaults.
4. **Compatibility:** public APIs, routes, schemas, events, migrations, clients.
5. **Verification:** tests prove behavior and command evidence is relevant.
6. **Complexity:** avoid speculative abstractions and duplicated ownership.

## Finding format

- severity: blocker, high, medium, or low;
- exact file and line/construct;
- failure scenario;
- why existing tests do not prevent it;
- smallest safe path.

Do not report formatter issues handled by CI, personal style preferences, or unrelated debt. Reviewer agents do not edit code.

One review pass is the default. Re-review only material fixes, and only the affected area plus integration boundary.

## Stop condition

Return actionable findings or state that no material finding was found. Do not manufacture work to justify the review.
