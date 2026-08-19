# Changelog

## Unreleased

## 0.3.0-beta.2 - 2026-08-19

### Release integrity and exact-artifact qualification

- Separated receipt-backed completion evidence into two fail-closed identities: the trusted runner execution event and the receipt-owned child verifier command. Packets now carry exact child argv separately from receipt transport identity, while live rows retain both argv hashes, verifier hash, canonical child command, event identity, and exact child exit code.
- Separated human-readable qualification evidence from short, deterministic disposable workspaces. Live fixtures, Git object databases, lifecycle state, and the exact candidate marketplace now use one path-budgeted allocator with junction/reparse rejection, command-local Git long-path defense, bounded Windows cleanup, machine-readable identity mappings, and a complete zero-model rehearsal on Windows and Ubuntu before live model turns. The evidence-refusal candidate receives only its fresh receipt-output parent as an additional network-disabled writable root, and the effective App Server sandbox is verified before any model turn.
- Made exact-artifact transcript emission encoding-safe on Windows without changing canonical evidence. Child stdout and stderr are retained as raw byte artifacts, the canonical transcript and identity manifest are written atomically as UTF-8, and console-only rendering deterministically escapes characters that the active stream cannot encode.
- Added a package-local structured verifier runner for exact-artifact qualification. It executes one explicit argv vector with `shell=False`, captures the real child return code and stream hashes, emits one canonical campaign/turn/command-bound receipt, and requires the live command event and completion packet to bind the same receipt. Packet prose, shell-normalized exits, echoed receipts, stale events, and modified output artifacts remain fail-closed.
- Added a fail-closed exact-artifact qualification boundary for beta.2. A deterministic candidate manifest binds the clean release commit, catalog and marketplace identities, five exact ZIPs, package versions, sizes, SHA-256 values, skill counts, and `SHA256SUMS`; isolated lifecycle and bounded live evidence refer back to that manifest and exact Core archive. CI creates the manifest independently on Windows and Ubuntu, compares the complete candidate artifact sets byte-for-byte, and runs the zero-model lifecycle from the downloaded ZIPs.
- Added a repository-wide packaged-resource closure gate for skill-local `scripts/`, `references/`, and `assets/` declarations. Strict validation now proves exact-case, no-link source containment, and the release packager independently verifies each declaration against the actual built ZIP without changing plugin bytes or versions.
- Shipped the canonical completion-evidence gate inside Core's `verify-before-completion` skill so an installed package can validate evidence without the Foundation source repository. The repository-root entry point now delegates to that packaged implementation, and the Core package identity advances to `0.3.0-beta.2`.
- Hardened the maintainer release packager, which previously lacked complete Windows junction/reparse-point and output containment gates, to reject linked path components, special entries, cross-platform traversal forms, output escapes, and linked artifact destinations. ZIPs and the checksum manifest are now prepared atomically, and failed runs remove outputs they generated. There is no evidence that `v0.3.0-beta.1` release assets were contaminated.

## 0.3.0-beta.1 - 2026-08-16

### Public beta

- Promoted `engineering-foundation-core` to `0.3.0-beta.1`; optional packages remain at `0.2.1` because they do not yet have equivalent authenticated live-behavior coverage.
- Added pinned public-beta installation, update, removal, scope, and limitation documentation.
- Added a zero-model isolated lifecycle harness that installs Core `0.2.2`, upgrades a loopback Git marketplace to the beta candidate, reinstalls Core, installs and discovers every package, removes every package and marketplace entry, and verifies clean disposable state.
- Excluded ignored `.eval-runs` campaign artifacts from repository-wide link, secret, and placeholder scans so maintainer evidence does not poison later local bootstraps.

### Live behavior evaluation

- Added a one-command authenticated Codex baseline-vs-core smoke harness.
- Added structured `systematic-debugging` activation through Codex app-server input rather than prompt-name guessing.
- Added reviewable traces, diffs, test evidence, token/tool/agent metrics, scorer output, and state restoration.
- Separated two-command end-user installation from maintainer-only deterministic and live validation.
- Replaced the Python fixture with a marker-backed Node.js fixture so the agent and harness share an available runtime.
- Added per-thread isolation for plugins, apps, memories, MCP servers, and ambient user skills.
- Rejected shell-chain false positives and write `summary.json` for PASS, FAIL, INVALID, and harness errors.
- Added cached, uncached, output, reasoning, duration, and environment-validity metrics.
- Require the core debugging skill to observe a runnable reproduction before production edits and to stop boundedly when reproduction is blocked.
- Emit fixture failure markers on stdout so failed Codex commands remain machine-detectable across clients.
- Added an authenticated negative-trigger smoke that exposes the core plugin naturally and rejects planning, orchestration, subagents, unrelated edits, or ambient-capability contamination on a one-literal configuration task.
- Isolated negative-smoke candidates from every foreign installed plugin so plugin-contributed MCP servers cannot contaminate the campaign, and emit automatic diagnostics for every non-PASS outcome.
- Moved negative-smoke plugin isolation to app-server startup, disabled the remote plugin catalog for the campaign, and retained thread-level isolation as defense in depth.
- Moved configured MCP-server isolation to app-server startup after thread-scoped disablement proved too late for eager MCP initialization.
- Added an app-server effective-plugin inventory pass so API-curated plugins omitted by the CLI installed list, plus their plugin-provided MCP servers, are disabled before measured negative-smoke execution.
- Added a model-free runtime MCP inventory pass for compatibility and extension registrations, then converted the discovered names into transport-complete disabled rows and required a second model-free veto validation before live turns may start.
- Kept top-level MCP vetoes exclusively in the app-server startup layer so partial thread/session rows cannot replace valid transports during `thread/start`.
- Recorded the first valid isolated Codex CLI negative-trigger campaign: the naturally exposed core plugin completed the tiny edit with all gates passing, zero core skill reads, and zero spawned agents.
- Applied the validated runtime MCP and foreign-plugin isolation policy to the explicit-positive debugging smoke.
- Added a checkpointed, fail-fast core repeatability runner that alternates positive and negative cases, enforces stable model/client/subject identity, resumes interrupted campaigns under the same HEAD, and scores combined minimum-repetition evidence.
- Deferred positive isolation evidence until the base campaign layout exists, preventing the wrapper from pre-creating and then colliding with its `preflight` directory.
- Recorded a complete three-repetition core campaign: all six positive/negative child campaigns and twelve authenticated turns passed, negative candidates retained zero core reads and zero agents, and the parent restored exact marketplace, plugin, and config state.
- Added a bounded read-only delegation smoke that requires one to three direct children, inspects each child for nested fan-out, forbids all fixture writes, and gates the parent report on exact source-backed risk coverage.
- Corrected the bounded-delegation positive contract after revision 1 permitted parent-only execution while its hidden gate required a child: revision 2 explicitly required native `spawn_agent` activation.
- Corrected the revision 1/2 observer after Codex CLI 0.147.0 selected MultiAgentV2 for `gpt-5.6-sol`: revision 3 observes both legacy `collabAgentToolCall` and V2 `subAgentActivity`, reads every direct child thread, validates V2 `NEW_TASK` assignments, and never retroactively reclassifies historical results.
- Replaced revision 3's incompatible ephemeral-thread inspection with a unique process-scoped in-memory thread store and campaign-local SQLite state: revision 4 proves turn-bearing reads before model use, keeps campaign threads and agent-graph metadata out of normal Codex storage, and performs complete child-history verification.
- Corrected revision 4's child-history classifier after direct children repeated their own depth-one start provenance: revision 5 records self and mirrored direct activity without counting it as nested, while still failing closed on depth-two fan-out and malformed root activity.
- Recorded the first scorer-valid positive bounded-delegation campaign: the candidate opened two direct MultiAgentV2 children, preserved readable bounded assignments, opened no nested child, changed no files, integrated every source-backed risk, and restored Codex state exactly.
- Added a failed-evidence refusal smoke that requires an exact implementation edit, a fresh blocked verifier result, full acceptance coverage, and a non-COMPLETE durable evidence packet before the candidate can pass.
- Recorded the first scorer-valid failed-evidence refusal campaign: the candidate independently observed verifier exit code `2`, marked the blocked required criterion `FAIL`, disclosed the missing attestation, produced a `BLOCKED` packet, and refused a false `COMPLETE` claim.

## 0.2.1 - 2026-08-15

### Cross-platform correctness

- Excluded local virtual environments and dependency directories from repository-wide link, secret, and placeholder scans.
- Added `.venv`, `venv`, `node_modules`, and common tool caches to `.gitignore`.
- Replaced operating-system-dependent executable checks with fixed Unix `0644` ZIP metadata.
- Canonicalized ZIP entry order by POSIX archive path, stored entries without zlib-dependent compression, and wrote checksum manifests with explicit LF bytes.
- Added regression tests for local dependency exclusions and cross-platform archive modes.
- Added a CI gate that compares Linux and Windows package artifacts byte-for-byte.

## 0.2.0 - 2026-08-15

### Architecture

- Split the distribution into core, Laravel, design, Cloud, and authoring packages.
- Kept provider-neutral behavior in Agent Skills and generated provider manifests from one catalog.
- Added OpenAI per-skill interface metadata and complete Codex plugin presentation fields.
- Kept optional Codex and Claude specialist profiles project-scoped, model-neutral, and read-only.

### Correctness and evidence

- Replaced string-matched acceptance criteria with stable criterion IDs.
- Combined exact task-contract coverage with fresh command exit codes, inspection/runtime records, artifacts, and working-tree identity.
- Required `NOT_APPLICABLE` criteria to be optional in the contract.
- Fixed eval identity so baseline, previous, and candidate may carry different subject versions and commits while sharing one harness commit.
- Added hard gates for duplicate runs, type confusion, repetition drift, missing artifacts, missing traces, and candidate regressions.

### Compatibility and validation

- Added Linux and Windows CI lanes.
- Restored Markdown-link, secret-pattern, placeholder, and description-budget checks.
- Added JSON Schema and real YAML parsing validation.
- Corrected OpenAI marketplace authentication values to `ON_INSTALL` / `ON_USE`.
- Added deterministic package archive tests and stricter provider manifest checks.

### Preserved from v0.1

- Restored source-grounded research and Codex Cloud readiness as appropriately scoped packages.
- Preserved test-first behavior as a progressively disclosed implementation reference.
- Retained Laravel database, route, migration, queue, policy, and performance guidance.
- Retained the durable design-contract template and explicit rendered visual QA.

## 0.1.0 - 2026-08-14

- Initial engineering foundation implementation.
