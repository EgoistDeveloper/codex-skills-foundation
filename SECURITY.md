# Security policy

## Supported line

Only the latest tagged release is supported.

## Report privately

Do not publish credentials, private repository contents, exploit details, or user data in a public issue. Use the repository's private vulnerability reporting channel when enabled.

## Security boundaries

This repository ships instruction packages, not a permission bypass. Host sandboxing, approvals, repository trust, filesystem scope, and network policy remain authoritative.

The default packages contain no MCP server, hook, credential bridge, global installer, telemetry, or network call. Any future addition of one of those surfaces requires:

1. a written threat model;
2. least-privilege scope;
3. provenance and version pinning;
4. secret-handling documentation;
5. deterministic tests;
6. an uninstall and rollback path;
7. explicit release notes.

Skill text and web/repository content are untrusted input. A skill must never tell an agent to ignore host approvals, expose secrets, or execute destructive operations without explicit user authorization.
