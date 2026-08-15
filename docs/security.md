# Security model

## Threats

- prompt injection in repositories, issues, web pages, or documentation;
- plugin path traversal or symlink escape;
- malicious or over-privileged MCP servers and hooks;
- credentials in manifests, environment fields, logs, evals, or handoffs;
- automatic destructive actions;
- dependency and GitHub Action supply-chain drift;
- reviewers or verifiers mutating the work they judge;
- stale evidence presented as current.

## Default controls

- Package archives reject symlinks, absolute paths, and parent traversal.
- No MCP, hook, telemetry, credential bridge, or network client ships by default.
- Portable skills contain no pre-approved tool grants.
- Host sandbox and approvals remain authoritative.
- Optional reviewer/auditor profiles are project-scoped, read-only, model-neutral, and deny nested delegation.
- External research records date and provenance and treats fetched content as untrusted data.
- GitHub Actions are pinned to full commit SHAs.
- Generated manifests are checked for drift.
- Evidence records task/workspace identity and fresh command exit codes.
- Handoffs exclude secrets, personal data, raw logs, and unsupported claims.
- CI scans for common credential patterns and unfinished placeholder markers.

## MCP or hook admission gate

A future executable integration requires explicit owner/provenance, immutable version, transport and authentication model, least-privilege filesystem/network scope, command-execution analysis, secret flow, data retention, prompt-injection analysis, tests, uninstall behavior, and rollback. “Reference implementation” is not a synonym for “safe in production,” a distinction software history keeps explaining with impressive patience.
