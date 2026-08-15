# Changelog

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
