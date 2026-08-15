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

The live harnesses require:

- Python 3.11 or newer;
- Git;
- Node.js;
- Codex CLI 0.147.0 or newer;
- an active `codex login` session;
- no concurrent Codex process changing plugin configuration during a campaign.

Generated campaigns stay below the ignored `.eval-runs/` directory and do not dirty the foundation repository. Every live command requires `--confirm-live` because it consumes authenticated plan usage and temporarily changes core plugin/marketplace state.

## Explicit positive debugging smoke

This campaign asks whether one explicitly selected core debugging skill completes a controlled defect safely and with reviewable evidence, compared with an isolated baseline.

```bash
python scripts/run_codex_positive_smoke_isolated.py --confirm-live
```

The wrapper first discovers runtime-only MCP registrations, validates a transport-complete name veto without a model turn, disables foreign plugins at app-server startup, and then delegates to the established positive harness.

The measured harness:

1. Creates one deterministic failing Node.js fixture and clones it twice.
2. Records the current Codex marketplace, core-plugin, and `config.toml` state.
3. Runs an isolated baseline with the core plugin absent.
4. Installs the local core package temporarily.
5. Resolves `engineering-foundation-core:systematic-debugging`, then supplies only that structured skill to the candidate.
6. Uses the same prompt, model, provider, service tier, reasoning effort, and fixture.
7. Requires marker-backed failure reproduction before editing and marker-backed verification after editing.
8. Checks the allowed diff, unchanged Git commit, activation, ambient-capability isolation, tool calls, agent count, duration, and detailed token usage.
9. Runs `scripts/score_eval_runs.py` only when environment isolation passes.
10. Restores the original plugin, marketplace, and `config.toml` state even when the campaign fails.

## Negative tiny-edit smoke

This campaign asks the opposite question: when the core plugin is naturally exposed to a one-literal configuration edit, do heavyweight planning and orchestration remain dormant?

```bash
python scripts/run_codex_negative_smoke_v4.py --confirm-live
```

The file name is retained for compatibility; the machine-readable case revision is authoritative. The current launcher performs two model-free runtime MCP preflights and uses transport-complete startup vetoes before either authenticated model turn begins.

The negative campaign passes only when:

- both variants make the exact requested one-literal `settings.json` edit;
- no unrelated file, formatting, key, value, or Git commit changes;
- `node verify-config.mjs` passes after the edit;
- `plan-and-milestones` and `bounded-orchestration` are present and eligible in the candidate, but their skill files are not read;
- no subagent is spawned;
- no foreign skill, memory, app, or MCP contamination is observed;
- candidate behavior clears the same live scorer regression gates as the baseline.

Other lightweight core skills are not automatically treated as forbidden. The case contract specifically tests that durable planning and multi-agent orchestration do not appear for a tiny edit.

## Core repeatability campaign

One passing sample does not establish stable behavior. The repeatability runner executes both isolated cases under one harness, client, model, and subject identity:

```bash
python scripts/run_codex_core_repeatability.py --confirm-live --repetitions 3
```

Three repetitions per case create six child campaigns and twelve authenticated model turns. The order alternates by repetition to reduce fixed ordering bias. The runner:

- requires a clean foundation working tree;
- creates an exclusive campaign lock;
- checkpoints after every restored PASS child;
- stops on the first non-PASS, failed restoration, identity drift, or malformed evidence packet;
- rewrites child rows into one parent campaign with contiguous repetition numbers;
- verifies model, client, harness, subject version, and subject commit stability;
- invokes `score_eval_runs.py --min-repetitions 3` only after all children pass;
- reports pass rates plus median token, uncached-input, tool-call, agent, and duration metrics;
- writes `manifest.json`, `runs.jsonl`, `summary.json`, `score.json`, `report.md`, transcripts, and automatic failure diagnostics.

Preview the exact order and turn count without changing Codex state:

```bash
python scripts/run_codex_core_repeatability.py --dry-run --repetitions 3
```

An interrupted campaign can be resumed only under the same repository HEAD:

```bash
python scripts/run_codex_core_repeatability.py \
  --confirm-live \
  --repetitions 3 \
  --resume .eval-runs/codex-core-repeatability/<campaign>
```

A finalized FAIL, INVALID, or harness-error campaign is not resumable. Start a new campaign after repairing the cause so results from different harness identities are not mixed.

## Bounded read-only delegation smoke

The repeatability campaign proves that a tiny edit does not trigger orchestration. This complementary positive case asks whether Codex delegates when the work is genuinely separable and then keeps that delegation bounded:

```bash
python scripts/run_codex_bounded_delegation_smoke_v2.py --confirm-live
```

Revision 1 told the candidate to use bounded delegation but also said that it *could* use one through three children. The fixture was small enough to complete directly, while the selected skill explicitly defaults to one accountable agent when delegation cost is not justified. The candidate therefore completed the task safely with zero children, and the hidden minimum-one-child gate failed. Revision 2 removes that contract mismatch: it explicitly requires the native `spawn_agent` path, requires at least one direct child, and pins Codex's stable default multi-agent v1 feature on for both variants. The core package itself is unchanged by this harness correction.

The fixture contains three independent audit documents. The same read-only task is given to a plugin-disabled baseline and to a candidate with `engineering-foundation-core:bounded-orchestration` explicitly selected. The candidate passes only when:

- one through three direct child agents are spawned;
- every child receives a nonempty bounded assignment;
- each direct child belongs to the parent thread;
- child threads are inspected and none spawns another child;
- no file or Git commit changes in the read-only fixture;
- the parent final answer integrates all three exact Risk-ID values and source paths;
- no foreign skill, memory, app, plugin, or MCP contamination is observed;
- the combined live scorer passes and the original Codex state is restored exactly.

The parent thread uses a read-only sandbox. The harness also reads each spawned child thread before app-server shutdown so a nested delegation attempt cannot quietly disappear behind a cheerful final report.

## Validity controls

The harnesses treat environment isolation as a hard precondition:

- fixtures use Node.js, already required by the npm Codex launcher;
- runners print explicit started, pass, and fail markers on stdout;
- shell chaining cannot turn a failed verification into false-positive evidence;
- an unmeasured app-server inventory phase discovers effective plugins;
- a model-free runtime phase discovers compatibility and extension MCP registrations;
- transport-complete disabled rows preserve those names as startup vetoes;
- a second model-free thread verifies that vetoed names expose no tools;
- top-level thread MCP rows are omitted so they cannot replace valid startup transports;
- discovered foreign skill paths are disabled;
- apps, memories, JavaScript REPL, foreign plugins, and remote plugin catalogs are disabled;
- any ready MCP server, foreign skill-file read, or Codex-memory read marks a measured campaign invalid and skips scoring;
- `summary.json` is written for PASS, FAIL, INVALID, and harness-error outcomes; every non-PASS result also writes diagnostics.

Authentication files are never copied, parsed, printed, or moved.

## Artifacts

Positive campaigns:

```text
.eval-runs/codex-live-smoke/<campaign>/
```

Negative-trigger campaigns:

```text
.eval-runs/codex-negative-smoke/<campaign>/
```

Repeatability campaigns:

```text
.eval-runs/codex-core-repeatability/<campaign>/
```

Bounded-delegation campaigns:

```text
.eval-runs/codex-bounded-delegation-smoke/<campaign>/
```

Review `trace.jsonl` before sharing it because model traces and repository content can contain local paths or environment metadata. The bundled fixtures themselves contain no secrets.

## Result meanings

- `PASS`: the measured campaign cleared its behavior and scorer gates.
- `FAIL`: the environment was valid, but behavior or regression gates failed.
- `INVALID`: ambient capabilities contaminated the comparison; the scorer was not run.
- `HARNESS_ERROR`: the harness or runtime failed before a trustworthy comparison completed.
- repeatability `PASS`: every requested child passed under one stable identity and the combined minimum-repetition scorer passed.

A passing repeatability campaign covers only the included Codex CLI cases. Full qualification still requires the remaining case, package, and client matrix in [`qualification.md`](qualification.md).