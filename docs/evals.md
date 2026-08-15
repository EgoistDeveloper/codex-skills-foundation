# Evaluation design

Static validation answers “are the files well-formed?” Live evaluation answers “does an agent behave better?” Those questions must remain separate, however desperately a release dashboard wants one flattering green square.

## Layers

- **T0, every change:** JSON/frontmatter/layout validation, generated-file drift, unit tests, schema cross-checks.
- **T1, activation:** positive and negative trigger tests with the relevant package enabled and disabled.
- **T2, behavior:** realistic repository fixtures, repeated provider runs, deterministic artifact checks.
- **T3, release canary:** representative Laravel, design, debugging, review, orchestration, and handoff tasks on each supported surface.

## Required comparison

For a normal release campaign compare:

1. baseline with the package disabled;
2. previous released package;
3. candidate package.

An initial release may document that no previous release exists. Later releases should run the scorer with `--require-previous`.

Run at least three repetitions for ordinary non-deterministic cases and five for release-critical cases when budget permits. Use the same campaign ID, client/version, case revision, package commit, and repetition set across variants.

## Hard gates

Every candidate run must pass:

- task outcome;
- safety;
- expected activation/non-activation;
- truthful completion evidence.

Candidate pass rates must not regress against the available comparators. Correctness and safety dominate efficiency. Lower token use does not purchase permission to be wrong more cheaply.

## Trace and artifact rules

Each live row must point to an artifact file relative to the JSONL run file. A trace file is also required unless the notes explicitly disclose `trace unavailable` and why. Absolute paths and parent traversal are rejected. Synthetic and live rows cannot be mixed in one input.

Keep artifacts redacted and reproducible. Useful evidence includes:

- task contract and final response;
- diff and working-tree state;
- commands, exit codes, and concise outputs;
- screenshots or rendered-state reports;
- provider trace or a documented reason it is unavailable;
- token, tool-call, duration, agent-count, unrelated-change, and post-completion-churn metrics.

## Scoring policy

Example self-test:

```bash
python scripts/score_eval_runs.py evals/fixtures/sample-runs.jsonl --allow-synthetic
```

Release campaign example:

```bash
python scripts/score_eval_runs.py evals/runs/release.jsonl \
  --require-previous \
  --min-repetitions 3 \
  --json
```

The scorer can say that supplied rows cleared its hard gates. It **cannot by itself** say the release is qualified, because it does not know whether every required client and case in `docs/qualification.md` was actually supplied. Consequently, a live clean run reports `COVERAGE_NOT_ASSESSED`, not `QUALIFIED`.

## Model grading

Use model grading only for subjective properties after deterministic checks. The grader receives the contract, rubric, and artifacts, not the acting model's hidden reasoning. Calibrate the rubric against human examples and record grader identity/version. A model should not grade its own invisible thought process, partly because that is unverifiable and partly because self-appraisal is already a crowded human industry.
