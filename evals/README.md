# Evaluation harness

The checked-in cases define expected activation, forbidden activation, and observable behavior assertions. They are test definitions, not completed model runs.

## JSONL identity

Each run row contains campaign, provider/client/version, case revision, harness commit, variant, subject version/commit, repetition, hard-gate results, and efficiency metrics.

- baseline: `subject_version = disabled`, `subject_commit = null`;
- previous: released version and commit;
- candidate: proposed version and commit.

The scorer rejects duplicate identities, unstable harness revisions, unstable subject identity within a variant, previous/candidate identity reuse, mixed live/synthetic rows, missing comparators, non-contiguous or mismatched repetition sets, unsafe artifact paths, and candidate hard-gate regressions.

## Metrics

Track tokens, tool calls, agents spawned, unrelated files, post-completion edits, and duration. Correctness, safety, activation, and evidence remain hard gates; efficiency is secondary.

`fixtures/sample-runs.jsonl` is synthetic and exists only to exercise scorer mechanics. It cannot qualify a provider, client, package, or release, despite the ancient human tradition of promoting test fixtures into executive dashboards.
