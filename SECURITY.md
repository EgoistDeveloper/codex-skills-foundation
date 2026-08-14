# Security policy

## Supported versions

Security fixes are applied to the latest released minor version.

## Trust model

Skills and plugins are executable influence over an agent. Review every source before installation. This repository intentionally ships no MCP server, no credential collector, no network daemon, and no automatic provider configuration.

The foundation follows these defaults:

- agent-phase network access off;
- least-privilege specialist agents;
- no recursive delegation;
- no secret material in prompts, logs, fixtures, or manifests;
- no unpinned executable downloads in bootstrap scripts;
- no command that modifies user-global configuration without an explicit `--apply`;
- no overwrite of existing custom-agent files unless `--force` is supplied.

## Reporting

Report suspected vulnerabilities privately to the repository owner through GitHub's private vulnerability reporting feature. Include affected path, reproduction steps, impact, and a minimal safe fix when available.

Do not include real credentials, private source code, or exploit payloads that target third parties.
