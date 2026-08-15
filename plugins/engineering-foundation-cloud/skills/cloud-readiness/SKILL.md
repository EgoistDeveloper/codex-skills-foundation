---
name: cloud-readiness
description: Prepare or audit a repository for Codex Cloud or another remote coding-agent environment with idempotent setup, caching, secret safety, network controls, and reproducible checks. Use for remote environment work. Do not silently enable network access, expose credentials, mutate global configuration, or claim readiness without executing a comparable setup path.
---


# Cloud Readiness

## Audit

1. Identify required runtimes, package managers, system packages, and project commands.
2. Separate setup-time dependency installation, maintenance-time refresh, and agent-time tests/tools.
3. Make setup idempotent, non-interactive, scoped to the workspace, and pinned where reproducibility requires it.
4. Ensure required build/test/lint commands can run without agent-phase internet when practical.
5. Keep secrets out of prompts, logs, repository files, and generated artifacts; use test doubles or setup-produced non-secret state.
6. Keep network off by default. Document exact domains, protocols, and methods for every exception.
7. Verify cache keys, invalidation, cached-container behavior, and maintenance cost.
8. Record the environment contract: baseline, setup, permissions, checks, known limitations, and rollback/cleanup.

## Prohibited defaults

- unrestricted agent internet;
- unreviewed `curl | sh`, `irm | iex`, or equivalent remote execution;
- global shell, Git, package-manager, or credential-store mutation without need;
- installation of every optional tool, plugin, or MCP server;
- setup that depends on accidental current directory or interactive prompts;
- production credentials available to an implementation agent;
- readiness claims based only on reading scripts.

Return the setup and maintenance commands, environment requirements, network/secret policy, cache behavior, evidence, and known limitations. Do not configure a remote environment unless the user authorized that write.
