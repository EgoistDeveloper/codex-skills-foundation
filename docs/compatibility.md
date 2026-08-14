# Compatibility matrix

| Client | Portable skills | Plugin install | Specialist agents | Notes |
|---|---:|---:|---:|---|
| Codex app / CLI / IDE | Yes | Yes | Optional TOML install | Root Agent Plugins manifest plus Codex overlay |
| Codex Cloud | Yes | Repository-dependent | Project `.codex/agents` | Use deterministic setup and maintenance scripts |
| Claude Code | Yes | Yes | Native bundled agents | `.claude-plugin` marketplace and manifest |
| Hermes Agent | Yes | Skills/tap compatible | Harness-managed | Uses Agent Skills progressive disclosure |
| Other Agent Skills clients | Core skills | Client-dependent | Client-dependent | Ignore unsupported extensions |

## Graceful degradation

Every skill must remain useful without custom agents. If a client cannot spawn specialists, the primary agent performs the same workflow sequentially.

If a browser tool is unavailable, UI work must report that visual verification was not run rather than claiming polish.

If current external documentation is unavailable, source-sensitive decisions are marked unverified instead of guessed.

## Goals and plans

When a host provides a durable Goal feature, the host remains the owner of goal state. The foundation translates the active goal into a local acceptance/evidence contract; it does not create a competing goal database.

When a host provides a built-in Plan mode, use it for the bounded plan. Do not duplicate the same plan in multiple state systems unless a checked-in artifact is required for handoff.
