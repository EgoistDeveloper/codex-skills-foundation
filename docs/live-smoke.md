# Codex live smokes

This document is for repository maintainers evaluating behavior. It is **not** an end-user installation guide.

## End users

A normal Codex user installs the marketplace and the small core package:

```bash
codex plugin marketplace add EgoistDeveloper/codex-skills-foundation --ref main
codex plugin add engineering-foundation-core@egoist-engineering-foundation
```

Then the user starts a new Codex thread. They do not run Python tests, JSON-RPC probes, package hash checks, or live-evaluation harnesses.

## Maintainer requirements

Both live harnesses require:

- Python 3.11 or newer;
- Git;
- Node.js;
- Codex CLI 0.147.0 or newer;
- an active `codex login` session;
- no concurrent Codex process changing plugin configuration during a campaign.

Generated campaigns stay below the ignored `.eval-runs/` directory and do not dirty the foundation repository. Each command deliberately requires `--confirm-live` because it runs two authenticated model turns and consumes plan usage.

## Explicit positive debugging smoke

This campaign asks whether one explicitly selected core debugging skill completes a controlled defect safely and with reviewable evidence, compared with an isolated baseline.

```bash
python scripts/run_codex_live_smoke.py --confirm-live
```

The harness:

1. Creates one deterministic failing Node.js fixture and clones it twice.
2. Records the current Codex marketplace, core-plugin, and `config.toml` state.
3. Discovers ambient skills and MCP names for exact per-thread disabling.
4. Runs an isolated baseline with plugins, apps, memories, configured MCP servers, and discovered user skills disabled.
5. Installs the local core package temporarily.
6. Resolves `engineering-foundation-core:systematic-debugging`, then supplies only that structured skill to the candidate.
7. Uses the same prompt, model, provider, service tier, reasoning effort, and fixture.
8. Requires marker-backed failure reproduction before editing and marker-backed verification after editing.
9. Checks the allowed diff, unchanged Git commit, activation, ambient-capability isolation, tool calls, agent count, duration, and detailed token usage.
10. Runs `scripts/score_eval_runs.py` only when environment isolation passes.
11. Restores the original plugin, marketplace, and `config.toml` state even when the campaign fails.

## Negative tiny-edit smoke

This campaign asks the opposite question: when the core plugin is naturally exposed to a one-literal configuration edit, do heavyweight planning and orchestration remain dormant?

```bash
python scripts/run_codex_negative_smoke.py --confirm-live
```

The baseline runs with plugins and ambient skills disabled. The candidate installs and exposes the core plugin without an explicit skill input. Foreign installed plugins and user skills, apps, memories, JavaScript REPL, and configured MCP servers remain disabled at the thread layer.

The negative campaign passes only when:

- both variants make the exact requested one-literal `settings.json` edit;
- no unrelated file, formatting, key, value, or Git commit changes;
- `node verify-config.mjs` passes after the edit;
- `plan-and-milestones` and `bounded-orchestration` are present and eligible in the candidate, but their skill files are not read;
- no subagent is spawned;
- no foreign skill, memory, app, or MCP contamination is observed;
- candidate behavior clears the same live scorer regression gates as the baseline.

Other lightweight core skills are not automatically treated as forbidden. The case contract specifically tests that durable planning and multi-agent orchestration do not appear for a tiny edit.

## Validity controls

The harnesses treat environment isolation as a hard precondition, not a decorative checkbox:

- fixtures use Node.js, already required by the npm Codex launcher;
- runners print explicit started, pass, and fail markers on stdout;
- a shell command returning zero after a failed verification cannot become false-positive evidence;
- discovered foreign skill paths are disabled through per-thread config;
- apps, memories, JavaScript REPL, and configured MCP servers are disabled;
- any ready MCP server, foreign skill-file read, or Codex-memory read marks a campaign `INVALID` and skips scoring;
- `summary.json` is written for PASS, FAIL, INVALID, and harness-error outcomes; every non-PASS result also prints compact reasons and writes `failure-diagnostics.json`.

The harnesses use the same authenticated Codex home for both variants. Authentication files are never copied, parsed, printed, or moved.

## Artifacts

Each campaign contains variant traces, diffs, final messages, verification output, machine-readable artifacts, scorer output, and a summary. Positive campaigns are written below:

```text
.eval-runs/codex-live-smoke/<campaign>/
```

Negative-trigger campaigns are written below:

```text
.eval-runs/codex-negative-smoke/<campaign>/
```

Review `trace.jsonl` before sharing it because model traces and repository content can contain local paths or environment metadata. The bundled fixtures themselves contain no secrets.

## Result meanings

- `PASS`: one isolated candidate repetition cleared the relevant behavior and scorer gates.
- `FAIL`: the environment was valid, but behavior or regression gates failed.
- `INVALID`: ambient skills, MCPs, memory, or other capabilities contaminated the comparison; the scorer was not run.
- `HARNESS_ERROR`: the harness or runtime failed before a trustworthy comparison completed.

A passing smoke does **not** mean every model or client is qualified. Full qualification still requires repeated baseline, previous-release, and candidate runs across the matrix in [`qualification.md`](qualification.md). One green run is evidence, not a tiny coronation ceremony.
