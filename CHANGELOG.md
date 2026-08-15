# Changelog

All notable changes to this project are documented here. Versions follow semantic versioning once a release is qualified and tagged.

## 0.2.0-candidate - 2026-08-15

### Added

- Three installable packages: core, Laravel, and design.
- Agent Plugins 1.0.0, Codex, Claude, and local marketplace manifests generated from one catalog.
- Eleven portable skills with bounded trigger descriptions.
- Optional project-scoped read-only Codex and Claude agent profiles with a dry-run-first installer.
- Task-contract, completion-evidence, handoff, eval-case, and eval-run schemas.
- Twelve behavioral eval case definitions and a JSONL scorer.
- Repository validation, manifest drift checks, evidence gate, unit tests, Python-version guard, and cross-platform bootstrap scripts.

### Hardened

- OpenAI marketplace installation/authentication policy and publisher metadata.
- Claude manifest schema declaration and display metadata.
- Completion gate now rejects required `NOT_RUN` and detects omitted contract acceptance criteria when a contract is supplied.
- Eval loader rejects string booleans, duplicate identities, mixed synthetic/live rows, metadata/repetition drift, and unsafe or missing live artifacts.
- Scorer no longer labels a passing subset as release-qualified; full matrix coverage remains a separate requirement.
- PowerShell bootstrap now fails on every unexpected native-process exit code, including malformed negative fixtures.

### Not qualified

- Pull Request #1 diff comparison.
- Live Codex desktop, CLI, cloud, or ChatGPT plugin behavior.
- Live Claude Code plugin and custom-agent behavior.
- Token-cost claims across real projects.
