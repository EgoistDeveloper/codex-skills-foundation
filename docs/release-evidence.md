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

## Post-release core 0.2.2 live smoke

After the `systematic-debugging` reproduction-gate repair, one authenticated isolated Codex CLI campaign passed all task, safety, explicit activation, evidence, and environment-isolation gates. The scorer reported `PASS` with `COVERAGE_NOT_ASSESSED`; this is partial live evidence rather than release qualification.

See [`live-evidence/codex-cli-core-0.2.2-2026-08-15.md`](live-evidence/codex-cli-core-0.2.2-2026-08-15.md) for campaign identity, metrics, and limitations.

## Evidence boundary

The released `v0.2.1` artifacts remain statically validated, provider-package validated, and cross-platform reproducible. A later `engineering-foundation-core` `0.2.2` candidate now has one passing authenticated Codex CLI explicit-positive smoke. Negative triggers, implicit activation, repeated runs, ChatGPT/Codex desktop, Codex Cloud, Claude Code, and an Agent Plugins reference client remain unassessed. The repository must therefore not describe either the release or the package family as fully live-model-qualified.
