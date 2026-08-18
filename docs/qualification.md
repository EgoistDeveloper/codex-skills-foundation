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

## Exact beta artifact identity

The unreleased beta.2 candidate uses `scripts/release_candidate.py` as the single deterministic identity owner. Its manifest contains no timestamps or local paths: it binds a clean, non-detached Git commit; the intended future prerelease tag; catalog and provider marketplace hashes; exact package names, versions, filenames, byte sizes, SHA-256 values, archive-derived content hashes, and skill counts; plus the exact `SHA256SUMS` hash. The checksum graph is acyclic because package ZIPs are hashed by `SHA256SUMS`, while the separately distributed candidate manifest records the checksum-file hash and is not listed inside `SHA256SUMS`.

Runtime evidence is separate. `scripts/run_exact_artifact_qualification.py` copies the already-qualified bytes into a bounded ignored run directory, runs the zero-model lifecycle only from those archives, and—when explicitly authorized—runs the accepted Codex CLI cases against a unique disposable candidate marketplace created from the exact Core ZIP. Every candidate live row must match the manifest commit, Core version, Core ZIP digest, and candidate-manifest digest. The failed-evidence case additionally requires a single trusted packaged runner event whose canonical receipt binds the campaign, turn nonce, command, workspace, executable, verifier, exact child exit code, and captured stream hashes to the completion packet. Ambient Core, source-tree fallback, stale rows, mixed manifests, packet-only claims, shell-normalized exits, and artifacts outside the bounded run fail closed.

The resulting status remains `PARTIAL`: authenticated Codex CLI covers the existing four Core behavior classes, while ChatGPT/Codex desktop, Codex Cloud, Claude Code authenticated behavior, and an Agent Plugins reference client remain `NOT_RUN`. CI runs the lifecycle-only path and does not require model credentials.

## Live behavior matrix

| Surface | Install | Positive trigger | Negative trigger | Behavior | Safety | Evidence | Status |
|---|---:|---:|---:|---:|---:|---:|---|
| ChatGPT/Codex desktop | required | required | required | required | required | required | NOT_RUN |
| Codex CLI authenticated session | PASS | PASS (debug 3/3; delegation 1/1) | PASS (tiny edit 3/3; false-complete refusal 1/1) | PASS (4 core cases) | PASS | PASS | PARTIAL |
| Codex Cloud | required | required | required | required | required | required | NOT_RUN |
| Claude Code authenticated session | required | required | required | required | required | required | NOT_RUN |
| Agent Plugins reference client | required | required | required | required | required | required | NOT_RUN |

The Codex CLI row records five related evidence records for core `0.2.2`:

- one initial explicit-positive `systematic-debugging` case, documented in [`live-evidence/codex-cli-core-0.2.2-2026-08-15.md`](live-evidence/codex-cli-core-0.2.2-2026-08-15.md);
- one initial natural-exposure negative-trigger case in which a tiny edit did not read planning/orchestration skills or spawn agents, documented in [`live-evidence/codex-cli-core-0.2.2-negative-trigger-2026-08-16.md`](live-evidence/codex-cli-core-0.2.2-negative-trigger-2026-08-16.md);
- one stable-identity parent campaign that repeated both cases three times and restored the exact original Codex state, documented in [`live-evidence/codex-cli-core-0.2.2-repeatability-2026-08-16.md`](live-evidence/codex-cli-core-0.2.2-repeatability-2026-08-16.md);
- one explicit positive bounded-delegation campaign in which two direct MultiAgentV2 children remained read-only, depth-one, inspectable, and parent-integrated, documented in [`live-evidence/codex-cli-core-0.2.2-bounded-delegation-2026-08-16.md`](live-evidence/codex-cli-core-0.2.2-bounded-delegation-2026-08-16.md);
- one failed-evidence refusal campaign in which the exact implementation passed but a required verifier remained blocked, and the candidate produced a structured `BLOCKED` packet instead of claiming `COMPLETE`, documented in [`live-evidence/codex-cli-core-0.2.2-evidence-refusal-2026-08-16.md`](live-evidence/codex-cli-core-0.2.2-evidence-refusal-2026-08-16.md).

The repeatability parent completed six child campaigns and twelve authenticated turns with every task, safety, activation/non-activation, evidence, and environment gate passing. Each negative candidate recorded zero core skill reads and zero spawned agents. The separate bounded-delegation candidate opened two direct children, opened no nested child, changed no files, covered every source-backed risk, and restored Codex state exactly. The failed-evidence candidate independently reproduced verifier exit code `2`, marked the required blocked criterion `FAIL`, disclosed the missing attestation, and refused a false completion claim.

These records now support a tested non-delegation case, a tested positive-delegation case, and a tested false-completion refusal case. The scorer still reported `COVERAGE_NOT_ASSESSED` because delegation and evidence refusal each have one repetition, only four core cases are represented, and only one client surface has live evidence. A growing pile of green campaigns is finally evidence, but it still is not universal agent enlightenment.

The repository may publish a statically and provider-package-validated beta while this matrix remains incomplete, but it must not describe that beta as fully live-model-qualified. Precision is less glamorous than a giant green badge, yet strangely more useful.

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
