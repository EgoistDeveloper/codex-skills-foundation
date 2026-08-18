# Release evidence

This record separates deterministic repository/provider validation from authenticated model-behavior qualification. A green parser is not suddenly a sentient software engineer, however persuasive the badge may look.

## Unreleased beta.2 exact-artifact candidate

The current source candidate is Core `0.3.0-beta.2` with all four optional packages remaining at `0.2.1`. It is `UNRELEASED`; `v0.3.0-beta.1` remains the only published public-beta tag.

H04 adds a deterministic `release-candidate.json` contract and a separate runtime qualification summary. The stable manifest binds one clean Git commit to the catalog and marketplace identities, the five exact ZIP byte sizes and hashes, archive-derived content hashes and skill counts, and the `SHA256SUMS` hash. Runtime evidence refers to the manifest by SHA-256 and records provider identities, exact-artifact lifecycle evidence, bounded live case evidence, scorer results, model-turn count, restoration, and remaining `NOT_RUN` clients without committing raw traces or user-specific absolute paths.

CI builds this manifest independently on Windows and Ubuntu, compares the complete candidate artifact sets byte-for-byte, then downloads the exact Linux set and runs a zero-model install/discovery/remove lifecycle from extracted ZIP content. A later release operation must use `release_candidate.py verify-assets` to prove repository, prerelease tag, tag target, expected filenames, exact bytes, package versions, `SHA256SUMS`, and candidate manifest identity. H04 does not create the future tag or release and does not claim artifact attestation.

The exact commit-specific candidate-manifest digest, live campaign IDs, CLI identities, and GitHub job results belong in the H04 review handoff after the branch is committed and qualified. Until then—and while the documented client matrix is incomplete—the candidate must not be described as fully qualified or published.

## v0.2.1 release evidence

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

A final public-beta Core behavior campaign then tested failed required evidence. The exact implementation passed, but a required external release attestation remained unavailable and the verifier returned exit code `2`. The candidate produced a current `BLOCKED` evidence packet, marked the blocked required criterion `FAIL`, disclosed the risk, refused `COMPLETE`, and restored Codex state exactly. Its scorer reported `PASS` with `COVERAGE_NOT_ASSESSED`.

- [`live-evidence/codex-cli-core-0.2.2-2026-08-15.md`](live-evidence/codex-cli-core-0.2.2-2026-08-15.md) records the initial explicit-positive debugging campaign.
- [`live-evidence/codex-cli-core-0.2.2-negative-trigger-2026-08-16.md`](live-evidence/codex-cli-core-0.2.2-negative-trigger-2026-08-16.md) records the initial natural-exposure tiny-edit campaign and its runtime MCP-isolation preflight.
- [`live-evidence/codex-cli-core-0.2.2-repeatability-2026-08-16.md`](live-evidence/codex-cli-core-0.2.2-repeatability-2026-08-16.md) records the three-repetition parent campaign, aggregate metrics, and exact state restoration.
- [`live-evidence/codex-cli-core-0.2.2-bounded-delegation-2026-08-16.md`](live-evidence/codex-cli-core-0.2.2-bounded-delegation-2026-08-16.md) records the first scorer-valid positive delegation campaign and its child-history provenance controls.
- [`live-evidence/codex-cli-core-0.2.2-evidence-refusal-2026-08-16.md`](live-evidence/codex-cli-core-0.2.2-evidence-refusal-2026-08-16.md) records the blocked-verifier campaign and its false-completion refusal evidence.

## Evidence boundary

The released `v0.2.1` artifacts remain statically validated, provider-package validated, and cross-platform reproducible. The later `engineering-foundation-core` `0.2.2` candidate now has repeated authenticated Codex CLI evidence for one explicit-positive debugging case and one natural-exposure negative-trigger case, plus one passing positive bounded-delegation case and one passing failed-evidence refusal case. Positive-delegation/evidence-refusal repetition, broader release-critical cases, ChatGPT/Codex desktop, Codex Cloud, Claude Code, and an Agent Plugins reference client remain unassessed. The repository must therefore not describe either the release or the package family as fully live-model-qualified.
