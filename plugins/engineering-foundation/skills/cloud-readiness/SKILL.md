---
name: cloud-readiness
description: Prepare or audit a repository for Codex Cloud setup, caching, secrets, network controls, and deterministic verification. Use for Cloud environment work; do not silently enable network or install optional services.
---

# Cloud Readiness

## Audit

1. Identify required runtimes and project package managers.
2. Separate:
   - setup-time dependency installation;
   - maintenance-time refresh;
   - agent-time tests and tools.
3. Make setup idempotent and non-interactive.
4. Pin versions where reproducibility requires it.
5. Ensure required test/lint/build commands work without agent-phase internet.
6. Confirm secrets are not required by the agent. Use test doubles or setup-produced non-secret artifacts.
7. Keep network off by default. Document exact allowlist domains and HTTP methods for exceptions.
8. Verify cached-container behavior and maintenance cost.
9. Record the Cloud prompt contract: baseline, goal, checks, permissions, delegation, and PR behavior.

## Prohibited defaults

- unrestricted agent internet;
- secrets printed or written into the repository;
- global shell/Git mutation without need;
- unreviewed `curl | sh`;
- installing every optional tool or MCP server;
- setup that depends on current working-directory accidents;
- claiming Cloud readiness without executing the setup and verification path in a comparable environment.

## Stop condition

Return a setup script, maintenance script, environment requirements, network policy, and known limitations. Do not configure a remote environment unless the user requested that write.
