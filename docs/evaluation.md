# Evaluation

## Deterministic checks

`python scripts/validate_repository.py --strict` checks:

- JSON manifests and marketplace paths;
- plugin names and version alignment;
- skill folder/frontmatter consistency;
- compact unique skill descriptions;
- adapter copy consistency;
- forbidden placeholders and obvious secret patterns;
- routing eval expectations;
- evidence-gate positive and negative fixtures.

`python -m unittest discover -s tests -v` verifies router and evidence behavior independently.

## Live behavior evals

Deterministic checks do not prove that every model will follow every skill. Before a stable release, run representative tasks in each supported client and record:

- client and version;
- model and reasoning setting;
- exact plugin commit;
- task prompt;
- tool/network permissions;
- token usage when available;
- diff size;
- verification outcome;
- requirement coverage;
- unnecessary-change count;
- number of delegation threads;
- whether completion was reopened without a valid reason.

## Required live cases

1. Small PHP feature: one agent, minimal diff, targeted test, no post-pass rewrite.
2. Laravel bug: regression test, minimal fix, authorization and route checks.
3. Large read-only audit: bounded parallel exploration and compact synthesis.
4. Coupled refactor: no parallel writers on shared files.
5. Corporate landing page: one direction, DESIGN.md, light/dark, responsive and browser verification.
6. Admin performance task: measurement before optimization.
7. Current framework question: primary-source research with date/version provenance.
8. Failed verification: honest incomplete status, no completion claim.
9. Explicit “no subagents”: zero delegation.
10. Reviewer with no material findings: stop without inventing work.

Results belong under `evals/results/` and must never be fabricated.
