# Security policy

## Default security posture

The distributed plugins contain instructions and local validation utilities only. They ship no MCP server, hook, telemetry, credential flow, remote executable, network client, global installer, automatic Git mutation, migration, deployment, or recursive agent chain.

Optional specialist profiles are read-only and project-scoped. Installers are dry-run-first and refuse conflicting files unless `--force` is explicit.

## Reporting

Report suspected vulnerabilities privately through the repository owner's preferred GitHub security contact. Do not include live credentials, private source, personal data, or unredacted provider traces in a public issue.

## Admission rule for future executable integrations

Any proposed MCP server, hook, monitor, network integration, or credential flow requires provenance, version pinning, least-privilege filesystem/network scope, secret-flow analysis, threat model, tests, uninstall behavior, and rollback documentation before inclusion.
