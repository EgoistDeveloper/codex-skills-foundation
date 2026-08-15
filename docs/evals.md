# Evaluation design

Static validation answers “are the files and contracts well formed?” Live evaluation answers “does an agent behave better?” A green parser test is not a personality transplant for a probabilistic model.

## Layers

- **T0, every change:** manifest drift, provider metadata, YAML/JSON parsing, JSON Schema, links, security sentinels, unit tests, packaging.
- **T1, activation:** positive and negative trigger cases with the relevant package enabled and disabled.
- **T2, behavior:** realistic repository fixtures, repeated provider runs, deterministic artifact checks.
- **T3, release canary:** representative core, Laravel, design, cloud, authoring, review, and handoff tasks on supported surfaces.

## Run identity

Every JSONL row records:

- `campaign_id`;
- provider, client, and client version;
- case ID and revision;
- `harness_commit` for the eval machinery;
- variant: `baseline`, `previous`, or `candidate`;
- `subject_version` and `subject_commit` for the package under test;
- repetition and metrics.

The identities are intentionally separate. A disabled baseline has `subject_version: "disabled"` and `subject_commit: null`; previous and candidate releases carry different subject revisions. The comparison key excludes subject identity, otherwise the three variants would never meet in the same comparison group. That was a real defect in the clean-room candidate and is now covered by regression tests.

## Required comparison

A normal release campaign compares:

1. package-disabled baseline;
2. previous released package;
3. candidate package.

Use one harness revision, client/version, case revision, and repetition set across variants. Run at least three repetitions for ordinary nondeterministic cases and five for release-critical cases when budget permits.

## Hard gates

Every candidate run must pass:

- task outcome;
- safety;
- expected activation or non-activation;
- truthful completion evidence.

Candidate pass rates must not regress against available comparators. Lower token use never compensates for lower correctness or safety.

## Trace and artifact rules

Each live row points to an artifact relative to the JSONL file. A trace is also required unless notes explicitly disclose `trace unavailable` and the reason. Absolute paths, parent traversal, missing files, duplicate identities, mixed live/synthetic rows, and repetition drift are rejected.

Useful evidence includes task contracts, final responses, diffs, working-tree state, commands and exit codes, screenshots, rendered-state reports, redacted traces, token/tool/agent counts, duration, unrelated changes, and post-completion churn.

## Commands

Scorer self-test:

```bash
python scripts/score_eval_runs.py \
  evals/fixtures/sample-runs.jsonl \
  --allow-synthetic \
  --require-previous
```

Live campaign:

```bash
python scripts/score_eval_runs.py evals/runs/release.jsonl \
  --require-previous \
  --min-repetitions 3 \
  --json
```

Synthetic rows test scorer mechanics only and always report `NOT_QUALIFIED`. A clean live subset reports `COVERAGE_NOT_ASSESSED`; the complete matrix in `docs/qualification.md` remains the release authority.

## Subjective grading

Use deterministic checks first. A model grader may assess visual quality, clarity, or maintainability only with an explicit rubric and reviewable artifacts. Record grader identity/version. Do not ask a model to grade its own hidden reasoning, a practice already amply represented in human performance reviews.
