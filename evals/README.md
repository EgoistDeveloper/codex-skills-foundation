# Evaluation harness

Static validation answers “are files well-formed?” Live evaluation answers “does an agent behave better?” These are different questions and must not be merged into one flattering green badge.

## Run record identity

Every JSONL row carries a `campaign_id`, provider, client and version, case ID and revision, candidate package commit, variant, and repetition number. The scorer rejects duplicate identities, mixed live/synthetic inputs, mismatched repetition sets, non-contiguous repetitions, and campaigns that claim multiple package commits.

`artifact_path` and `trace_path` are relative to the JSONL file. Live rows require a real artifact. A trace is required unless `notes` explicitly contains `trace unavailable` with the reason.

## Required comparison

For every normal release candidate compare:

1. baseline with the package disabled;
2. previous released package;
3. candidate package.

Run representative cases on each supported provider with at least three repetitions for ordinary behavior and five for release-critical cases when budget permits.

## Hard gates

- candidate `task_pass`, `safety_pass`, `activation_pass`, and `evidence_pass` must all be true;
- candidate pass rates must not regress against baseline or previous release;
- a token improvement never compensates for correctness or safety regression.

## Efficiency metrics

Track tokens, tool calls, agents spawned, unrelated files changed, post-completion edits, and duration. Report medians and pass rates; retain redacted traces and artifacts.

## Subjective grading

Use deterministic checks first. A model grader may assess visual quality, clarity, or maintainability only after objective checks and must not grade its own hidden reasoning. Keep the rubric, grader version, and artifacts in the run record or campaign report.

`sample-runs.jsonl` is synthetic and tests only scorer mechanics. It cannot qualify Codex, Claude, a plugin, a release, or anything else humans may be tempted to promote from a fixture.
