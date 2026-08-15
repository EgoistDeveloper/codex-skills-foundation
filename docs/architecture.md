# Architecture

## Package model

The repository publishes five independent packages:

| Package | Default | Responsibility |
|---|---:|---|
| `engineering-foundation-core` | yes | task contract, planning, orchestration, implementation, debugging, current-source research, review, verification, handoff |
| `engineering-foundation-laravel` | Laravel/PHP only | repository-aware framework, database, authorization, queue, route, and test guidance |
| `engineering-foundation-design` | UI work only | one design direction and rendered visual verification |
| `engineering-foundation-cloud` | remote-agent work only | Codex Cloud and remote environment setup, cache, network, and secret boundaries |
| `engineering-foundation-authoring` | maintainers only | skill and plugin authoring, provenance, validation, and eval design |

The split is behavioral, not decorative. Skill names and descriptions participate in discovery before bodies load, so installing unrelated domains increases context cost and accidental activation risk.

## Distribution layers

Each package contains three deliberately separate manifests:

- `plugin.json`: portable Agent Plugins 1.0.0 metadata;
- `.codex-plugin/plugin.json`: Codex/OpenAI presentation and discovery metadata;
- `.claude-plugin/plugin.json`: Claude Code metadata;
- `skills/`: provider-neutral behavior;
- `skills/*/agents/openai.yaml`: Codex-facing skill presentation metadata.

Shared metadata is authored once in `catalog/plugins.json` and rendered by `scripts/render_manifests.py`. Provider schemas and runtime behavior are not falsely collapsed into one manifest.

## Runtime principles

1. **Progressive disclosure.** Discovery metadata is narrow; long checklists and templates live under `references/` or `assets/`.
2. **Single-agent default.** Delegation is an optimization for separable work, not a quality badge.
3. **One writer per file.** The parent owns integration, the final diff, and the only completion claim.
4. **Evidence over confidence.** Goal trackers and model statements never replace current commands, runtime observations, artifacts, and diff inspection.
5. **Stop after proof.** A task reopens only for failed evidence, unmet acceptance, changed requirements, or a concrete regression/security finding.
6. **No ambient authority.** Default packages ship no MCP server, hook, telemetry, credential bridge, network client, global installer, or destructive automation.
7. **Static and live evidence are different.** Parser tests prove parsers; they do not prove probabilistic agent behavior.

## State model

```text
INTAKE -> CONTRACT -> [PLAN] -> [DELEGATE] -> IMPLEMENT / DIAGNOSE
       -> VERIFY -> [REVIEW] -> COMPLETE -> [HANDOFF]
```

Bracketed transitions are conditional. A required `FAIL`, `NOT_RUN`, or omitted acceptance item prevents `COMPLETE`.

## Optional custom agents

Portable orchestration works with host-native subagents and does not depend on permanent roles. Three optional project-scoped adapters are provided for repeated read-only work:

- explorer;
- diff reviewer;
- completion-evidence auditor.

They pin no model, deny editing, prohibit nested delegation, and deliberately exclude an implementer. Provider-specific agent formats remain an adapter qualification surface, not part of the portable Agent Skills contract.

## Sources of truth

- `catalog/plugins.json`: package metadata;
- generated manifests: provider distribution adapters;
- `plugins/*/skills/*/SKILL.md`: portable behavior;
- `AGENTS.md`: repository development contract;
- `schemas/`: task, evidence, handoff, and eval contracts;
- `profiles/`: optional provider-specific project agents;
- `docs/exec-plans/`: durable plans for long work;
- eval JSONL plus artifacts: live behavior evidence.
