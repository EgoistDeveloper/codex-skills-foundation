# Changelog

## Unreleased

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
