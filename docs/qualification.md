# Release qualification

Repository validation, provider package validation, and live behavior qualification are separate evidence classes.

## Static and provider package gates

| Gate | Required | Evidence |
|---|---:|---|
| Linux bootstrap | yes | GitHub Actions `Validate foundation / ubuntu-latest` |
| Windows bootstrap | yes | GitHub Actions `Validate foundation / windows-latest` |
| Claude plugin strict validation | yes | pinned Claude Code CLI validates marketplace and every package |
| Codex marketplace/install smoke | yes | pinned Codex CLI adds the local marketplace and installs every package |
| deterministic ZIPs and SHA-256 | yes | bootstrap package step and CI artifact |

Actual run IDs and results for the released revision belong in `docs/release-evidence.md`.

## Live behavior matrix

| Surface | Install | Positive trigger | Negative trigger | Behavior | Safety | Evidence | Status |
|---|---:|---:|---:|---:|---:|---:|---|
| ChatGPT/Codex desktop | required | required | required | required | required | required | NOT_RUN |
| Codex CLI authenticated session | PASS | PASS (debug 3/3; delegation 1/1) | PASS (tiny edit 3/3) | PASS (3 core cases) | PASS | PASS | PARTIAL |
| Codex Cloud | required | required | required | required | required | required | NOT_RUN |
| Claude Code authenticated session | required | required | required | required | required | required | NOT_RUN |
| Agent Plugins reference client | required | required | required | required | required | required | NOT_RUN |

The Codex CLI row records four related evidence records for core `0.2.2`:

- one initial explicit-positive `systematic-debugging` case, documented in [`live-evidence/codex-cli-core-0.2.2-2026-08-15.md`](live-evidence/codex-cli-core-0.2.2-2026-08-15.md);
- one initial natural-exposure negative-trigger case in which a tiny edit did not read planning/orchestration skills or spawn agents, documented in [`live-evidence/codex-cli-core-0.2.2-negative-trigger-2026-08-16.md`](live-evidence/codex-cli-core-0.2.2-negative-trigger-2026-08-16.md);
- one stable-identity parent campaign that repeated both cases three times and restored the exact original Codex state, documented in [`live-evidence/codex-cli-core-0.2.2-repeatability-2026-08-16.md`](live-evidence/codex-cli-core-0.2.2-repeatability-2026-08-16.md);
- one explicit positive bounded-delegation campaign in which two direct MultiAgentV2 children remained read-only, depth-one, inspectable, and parent-integrated, documented in [`live-evidence/codex-cli-core-0.2.2-bounded-delegation-2026-08-16.md`](live-evidence/codex-cli-core-0.2.2-bounded-delegation-2026-08-16.md).

The repeatability parent completed six child campaigns and twelve authenticated turns with every task, safety, activation/non-activation, evidence, and environment gate passing. Each negative candidate recorded zero core skill reads and zero spawned agents. The separate bounded-delegation candidate opened two direct children, opened no nested child, changed no files, covered every source-backed risk, and restored Codex state exactly.

These records now support both a tested non-delegation case and a tested positive-delegation case. The scorer still reported `COVERAGE_NOT_ASSESSED` because positive delegation has one repetition, only three core cases are represented, and only one client surface has live evidence. A small pile of green campaigns is finally evidence, but it still is not universal agent enlightenment.

The repository may publish a statically and provider-package-validated release while this matrix remains incomplete, but it must not describe that release as fully live-model-qualified. Precision is less glamorous than a giant green badge, yet strangely more useful.

## Release-critical cases

- tiny edit skips durable plan and subagents;
- completion does not trigger a speculative rewrite;
- required failed, omitted, or unrun evidence prevents completion;
- multi-agent fan-out remains bounded with one writer per file;
- review suppresses unsupported style noise;
- handoff is compact and verifiable;
- current-source research activates only when repository evidence is insufficient;
- Laravel reads installed versions and demands measured database/performance evidence;
- design chooses one direction and verifies rendered states;
- cloud readiness does not silently enable network or expose credentials;
- authoring includes positive and negative eval coverage.

## Live campaign record

Record campaign ID, provider/client/version, operating system, authentication mode, relevant model/capability settings, harness commit, subject versions/commits, case revisions, repetitions, redacted traces/artifacts/diffs/commands/screenshots, token/tool/duration/agent/churn metrics, and grader identity/version where subjective grading is used.