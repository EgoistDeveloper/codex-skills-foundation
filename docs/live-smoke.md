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

The live smoke answers a narrower question: on one authenticated Codex CLI run, does one explicitly selected core debugging skill complete a controlled task safely and with reviewable evidence, compared with an isolated baseline?

Requirements:

- Python 3.11 or newer;
- Git;
- Node.js;
- Codex CLI 0.147.0 or newer;
- an active `codex login` session;
- no concurrent Codex process changing plugin configuration during the smoke.

Run from a clean repository root:

```bash
python scripts/run_codex_live_smoke.py --confirm-live
```

Generated campaigns stay below the ignored `.eval-runs/` directory and do not dirty the foundation repository. The command deliberately requires `--confirm-live` because it runs two real model turns and consumes plan usage.

## Validity controls

The harness treats environment isolation as a hard precondition, not a decorative checkbox:

- the fixture uses Node.js, which is already required by the npm Codex launcher;
- the test runner prints explicit started, pass, and fail markers;
- a shell command returning zero after a failed test cannot become false positive evidence;
- every discovered user skill path is disabled through per-thread session config;
- plugin, app, memory, and JavaScript REPL feature surfaces are disabled for both variants;
- configured MCP servers are disabled for both variants;
- the candidate receives only one structured explicit skill input;
- any ready MCP server, foreign skill-file read, or Codex-memory read marks the campaign `INVALID` and skips scoring;
- `summary.json` is written for PASS, FAIL, INVALID, and harness-error outcomes.

The baseline and candidate still use the same authenticated Codex home. Authentication files are never copied, parsed, printed, or moved.

## What the harness does

1. Creates one deterministic failing Node.js fixture and clones it twice.
2. Records the current Codex marketplace, core-plugin, and `config.toml` state.
3. Discovers ambient skills and MCP names for explicit per-thread disabling.
4. Runs an isolated baseline with plugins, apps, memories, configured MCP servers, and discovered user skills disabled.
5. Installs the local core package temporarily.
6. Resolves `engineering-foundation-core:systematic-debugging`, then runs the candidate with the same isolation config plus that one structured skill input.
7. Uses the same prompt, model, provider, service tier, reasoning effort, and fixture.
8. Checks marker-backed reproduction, marker-backed post-edit verification, allowed diff, unchanged Git commit, activation, ambient-capability isolation, tool calls, agent count, duration, and detailed token usage.
9. Writes traces and artifacts below `.eval-runs/codex-live-smoke/`.
10. Runs `scripts/score_eval_runs.py` only when the environment-isolation gate passes.
11. Restores the original plugin, marketplace, and `config.toml` state even when the run fails.

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
├── preflight/
├── runs.jsonl
├── score.json
├── summary.json
├── seed/
└── workspaces/
```

`trace.jsonl` records the app-server messages sent and received. Review it before sharing because model traces and repository content can contain sensitive information in real campaigns. The bundled fixture itself contains no secrets.

## Result meanings

- `PASS`: one isolated candidate repetition cleared scorer gates.
- `FAIL`: the environment was valid, but behavior or regression gates failed.
- `INVALID`: ambient skills, MCPs, memory, or other capabilities contaminated the comparison; the scorer was not run.
- `HARNESS_ERROR`: the harness or runtime failed before a trustworthy comparison completed.

A passing smoke does **not** mean every model or client is qualified. Full qualification still requires repeated baseline, previous-release, and candidate runs across the matrix in [`qualification.md`](qualification.md). One green smoke is evidence, not a coronation ceremony.
r