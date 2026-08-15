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
| Codex CLI authenticated session | PASS | PASS (1 explicit case) | NOT_RUN | PASS (1 case) | PASS | PASS | PARTIAL |
| Codex Cloud | required | required | required | required | required | required | NOT_RUN |
| Claude Code authenticated session | required | required | required | required | required | required | NOT_RUN |
| Agent Plugins reference client | required | required | required | selected | required | required | NOT_RUN |

The Codex CLI row records one isolated authenticated `systematic-debugging` smoke for core `0.2.2`. Its scorer status was `PASS`, but coverage remained `COVERAGE_NOT_ASSESSED`. See [`live-evidence/codex-cli-core-0.2.2-2026-08-15.md`](live-evidence/codex-cli-core-0.2.2-2026-08-15.md). A single explicit-positive case does not satisfy negative-trigger, implicit-activation, repetition, or full-surface requirements.

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
