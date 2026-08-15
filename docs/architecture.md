# Architecture

## Principles

1. **Portable workflow, separate adapters.** Agent Skills contain behavior. Agent Plugins `plugin.json`, Codex `.codex-plugin/plugin.json`, and Claude `.claude-plugin/plugin.json` remain distinct validated outputs.
2. **Progressive disclosure.** Keep discovery metadata narrow and skill bodies concise; load focused references only when needed.
3. **Modular installation.** Core, Laravel, and design are separate packages so irrelevant skills do not consume discovery budget or trigger accidentally.
4. **Single-agent default.** Delegation is a bounded optimization for separable work, not the default lifecycle.
5. **Evidence over status language.** Goal trackers, checklists, and model confidence never replace commands, artifacts, and diff inspection.
6. **Static and behavioral validation are separate.** A parser unit test cannot prove a model follows a skill.
7. **No ambient authority.** The package ships no MCP, hook, global installer, credential, or network dependency.
8. **Generated metadata, authored behavior.** Provider manifests are generated from one catalog; skill behavior is reviewed as source, not emitted from an opaque generator.

## Core versus optional custom agents

The core `bounded-orchestration` skill uses host-native subagents and does not require permanent custom roles. Provider-specific agent formats are adapters and may not exist on every desktop, cloud, CLI, or API surface.

The repository nevertheless supplies three **optional project-scoped** profiles for repeated read-only work:

- explorer;
- diff reviewer;
- completion-evidence auditor.

They are model-neutral, installed only through an explicit dry-run-first script, and deliberately exclude an implementer. The parent or host-native worker owns edits and integration. This keeps the portable contract independent from a provider format while still giving qualified local clients reusable specialist roles.

## State model

```text
INTAKE -> CONTRACT -> [PLAN] -> [DELEGATE] -> IMPLEMENT/DIAGNOSE
       -> VERIFY -> [REVIEW] -> COMPLETE -> [HANDOFF]
```

Transitions in brackets are conditional. `COMPLETE` reopens only for failed evidence, unmet acceptance, changed requirements, or a material regression/security finding. A required `NOT_RUN` keeps the state `PARTIAL`; disclosure alone does not magically turn absence into proof.

## Source of truth

- `catalog/plugins.json`: shared package metadata.
- generated provider manifests: distribution adapters.
- portable `skills/*/SKILL.md`: behavior contract.
- `AGENTS.md`: repository-development contract.
- `profiles/`: optional provider-specific project agent adapters.
- `docs/exec-plans/`: durable plans for long work.
- task contract + completion evidence: acceptance traceability.
- eval run records + artifacts: behavioral qualification evidence.
