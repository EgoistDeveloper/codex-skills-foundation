# Security model

## Threats

- prompt injection in repository, issue, web, or documentation content;
- plugin path traversal or symlink escape;
- malicious or over-privileged MCP servers;
- hooks executing unexpected commands;
- credentials embedded in manifests, environment fields, logs, or handoffs;
- automatic destructive actions;
- dependency or GitHub Action supply-chain drift;
- a reviewer/verifier mutating the work it is supposed to judge.

## Controls

- Agent Plugins paths stay within plugin root.
- No MCP or hooks ship in the default candidate.
- Portable skills do not grant `allowed-tools`.
- Host sandbox and approvals remain authoritative.
- Reviewer and verifier are report-only by default.
- External research records provenance and date.
- CI actions are pinned to a full commit SHA.
- Generated manifests are checked for drift.
- Handoffs exclude secrets and raw logs.

## MCP admission gate

A future MCP server requires owner/provenance, pinned version, transport and auth model, minimum filesystem/network scope, command-execution analysis, secret flow, data retention, threat model, tests, and uninstall/rollback. Reference servers are not automatically production-safe.
