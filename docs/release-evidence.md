# v0.2.1 release evidence

This record separates deterministic repository/provider validation from authenticated model-behavior qualification. A green parser is not suddenly a sentient software engineer, however persuasive the badge may look.

## Source

- release version: `0.2.1`
- integration pull request: `#3`
- first fully green repair revision: `761c58684b573eeda01afa836ea891c99f6c4a76`
- release tag: `v0.2.1` after the reviewed pull request is merged to `main`

## Deterministic validation

| Check | Result | Evidence |
|---|---:|---|
| strict repository validator | **PASS** | 0 errors and 0 warnings in workflow run `31884055490` |
| unit tests | **PASS** | 40 tests in workflow run `31884055490` |
| GitHub Linux bootstrap | **PASS** | workflow run `31884055490`, job `95010621032` |
| GitHub Windows bootstrap | **PASS** | workflow run `31884055490`, job `95010621130` |
| Linux/Windows package byte identity | **PASS** | workflow run `31884055490`, job `95010676338` |
| Claude marketplace and plugin validation | **PASS** | Claude Code `2.1.220` in workflow run `31884055487`, job `95010621044` |
| Codex marketplace and install smoke | **PASS** | Codex CLI `0.146.0` in workflow run `31884055487`, job `95010621044` |

## Repaired defects

- Repository-wide scans no longer descend into `.venv`, `venv`, `node_modules`, or common local tool caches.
- Plugin archives use fixed Unix regular-file mode `0644` rather than host-dependent executable checks.
- ZIP entries are ordered by canonical POSIX archive path, stored without zlib-dependent compression, and checksum manifests use explicit LF bytes.
- CI now compares Linux and Windows package artifacts byte-for-byte.

## Release packages

| Package | SHA-256 |
|---|---|
| `engineering-foundation-core-0.2.1.zip` | `541470441ce809f6a2f99c2fece3a18db80b49f5296d1ba860aad27b26a4aa61` |
| `engineering-foundation-laravel-0.2.1.zip` | `64fb34691d66b7051c77c0a90058631ef7e0b308cd010878777642696d65a79c` |
| `engineering-foundation-design-0.2.1.zip` | `3f7d5f37d264e7aa1d2ab94dea12a62806e5cef1728225319845429a33a63296` |
| `engineering-foundation-cloud-0.2.1.zip` | `4fe88385d98e3ef2b36aa2b304b891c76db61db99f88480e211efb6b7a575982` |
| `engineering-foundation-authoring-0.2.1.zip` | `cbd7906aa03af50e850b253f4ecf17ced202b126f4fa33ba120036f5f196f07b` |

## Post-release core 0.2.2 live evidence

After the `systematic-debugging` reproduction-gate repair, an authenticated isolated Codex CLI explicit-positive campaign passed all task, safety, activation, evidence, and environment-isolation gates. A later authenticated isolated negative-trigger campaign exposed the core plugin naturally on a tiny edit and passed task, safety, non-activation, evidence, and environment-isolation gates with zero core skill reads and zero spawned agents.

A stable-identity parent campaign then repeated both cases three times. All six child campaigns and all twelve authenticated model turns completed, every required gate passed, every negative candidate retained zero core reads and zero spawned agents, and the parent restored the original marketplace, plugin, and config state exactly. The parent scorer reported `PASS` with `COVERAGE_NOT_ASSESSED`.

A separate explicit positive bounded-delegation campaign then opened two direct MultiAgentV2 children for genuinely separable read-only work. The candidate preserved depth one, produced two readable assignment packets, changed no files, integrated every exact source-backed risk, and restored Codex state exactly. Its scorer also reported `PASS` with `COVERAGE_NOT_ASSESSED`.

- [`live-evidence/codex-cli-core-0.2.2-2026-08-15.md`](live-evidence/codex-cli-core-0.2.2-2026-08-15.md) records the initial explicit-positive debugging campaign.
- [`live-evidence/codex-cli-core-0.2.2-negative-trigger-2026-08-16.md`](live-evidence/codex-cli-core-0.2.2-negative-trigger-2026-08-16.md) records the initial natural-exposure tiny-edit campaign and its runtime MCP-isolation preflight.
- [`live-evidence/codex-cli-core-0.2.2-repeatability-2026-08-16.md`](live-evidence/codex-cli-core-0.2.2-repeatability-2026-08-16.md) records the three-repetition parent campaign, aggregate metrics, and exact state restoration.
- [`live-evidence/codex-cli-core-0.2.2-bounded-delegation-2026-08-16.md`](live-evidence/codex-cli-core-0.2.2-bounded-delegation-2026-08-16.md) records the first scorer-valid positive delegation campaign and its child-history provenance controls.

## Evidence boundary

The released `v0.2.1` artifacts remain statically validated, provider-package validated, and cross-platform reproducible. The later `engineering-foundation-core` `0.2.2` candidate now has repeated authenticated Codex CLI evidence for one explicit-positive debugging case and one natural-exposure negative-trigger case, plus one passing positive bounded-delegation case. Failed/unrun evidence refusal, positive-delegation repetition, broader release-critical cases, ChatGPT/Codex desktop, Codex Cloud, Claude Code, and an Agent Plugins reference client remain unassessed. The repository must therefore not describe either the release or the package family as fully live-model-qualified.