# Codex live smoke

This document is for repository maintainers evaluating behavior. It is **not** an end-user installation guide.

## End users

A normal Codex user installs the marketplace and the small core package:

```bash
codex plugin marketplace add EgoistDeveloper/codex-skills-foundation --ref main
codex plugin add engineering-foundation-core@egoist-engineering-foundation
```

Then the user starts a new Codex thread. They do not run Python tests, JSON-RPC probes, package hash checks, or the live smoke harness.

## Maintainer smoke

The live smoke answers a narrower question: on one authenticated Codex CLI run, does an explicitly selected core debugging skill complete a controlled task safely and with reviewable evidence, compared with a plugin-disabled baseline?

Requirements:

- Python 3.11 or newer;
- Git;
- Codex CLI 0.147.0 or newer;
- an active `codex login` session;
- no concurrent Codex process changing plugin configuration during the smoke.

Run from a clean repository root:

```bash
python scripts/run_codex_live_smoke.py --confirm-live
```

Generated campaigns stay below the ignored `.eval-runs/` directory and do not dirty the foundation repository.

The command deliberately requires `--confirm-live` because it runs two real model turns and consumes plan usage.

## What the harness does

1. Creates one deterministic failing Python fixture and clones it twice.
2. Records the current Codex marketplace, core-plugin, and `config.toml` state.
3. Runs a plugin-disabled baseline.
4. Installs the local core package temporarily.
5. Starts a new Codex app-server session and selects `engineering-foundation-core:systematic-debugging` through the structured skill input.
6. Runs the same prompt, model, provider, service tier, reasoning effort, and fixture in the candidate variant.
7. Checks the final tests, allowed diff, unchanged Git commit, activation, fresh command evidence, tool calls, agent count, duration, and token usage.
8. Writes traces and artifacts below `.eval-runs/codex-live-smoke/`.
9. Runs `scripts/score_eval_runs.py` on the baseline and candidate rows.
10. Restores the original plugin, marketplace, and `config.toml` state even when the run fails.

The harness never copies authentication files or prints credentials. The candidate `subject_commit` is the exact checked-out repository revision used to materialize the local plugin, rather than an older release tag that merely happens to advertise the same package version.

## Artifacts

Each campaign contains:

```text
.eval-runs/codex-live-smoke/<campaign>/
├── baseline/
│   ├── artifact.json
│   ├── diff.patch
│   ├── final-message.md
│   ├── stderr.txt
│   ├── tests-after.txt
│   ├── tests-before.txt
│   └── trace.jsonl
├── candidate/
│   └── ...
├── preflight/trace.jsonl
├── runs.jsonl
├── score.json
├── summary.json
├── seed/
└── workspaces/
```

`trace.jsonl` records the app-server messages sent and received. It should be reviewed before sharing because model traces and repository content can contain sensitive information in real campaigns. The bundled fixture itself contains no secrets.

## Pass meaning

A passing smoke means one candidate repetition cleared the task, safety, explicit activation, and evidence gates without regressing against its baseline repetition.

It does **not** mean:

- every Codex model will improve;
- implicit activation is qualified;
- Claude, Codex Cloud, ChatGPT Desktop, or other clients are qualified;
- the complete release matrix passed;
- a single nondeterministic run is statistically persuasive.

Full qualification still requires repeated baseline, previous-release, and candidate runs across the matrix in [`qualification.md`](qualification.md). One green smoke is useful evidence, not a coronation ceremony.

## Safety refusals

The harness stops instead of guessing when:

- the configured marketplace name points to another repository;
- the existing core plugin is disabled;
- the existing core plugin version differs from the local candidate;
- Codex is not authenticated;
- Codex is older than the validated minimum;
- the fixture is not failing before the model runs;
- baseline and candidate use different model settings;
- the original plugin/config state cannot be restored.
