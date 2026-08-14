# Research record

Research date: **2026-08-14**

This foundation was synthesized from current official specifications and selected engineering repositories. Third-party skill text was not copied. The revisions below record the exact upstream state inspected for the user-supplied repositories; they are evidence, not vendored dependencies.

## Primary specifications and official sources

- OpenAI Codex: AGENTS.md discovery, skills, plugins, subagents, Cloud environments, internet access, and custom review rules.
  - https://learn.chatgpt.com/docs/agent-configuration/agents-md
  - https://learn.chatgpt.com/docs/agent-configuration/subagents
  - https://learn.chatgpt.com/docs/build-skills
  - https://learn.chatgpt.com/docs/build-plugins
  - https://learn.chatgpt.com/docs/environments/cloud-environment
  - https://learn.chatgpt.com/docs/cloud/internet-access
  - https://developers.openai.com/blog/custom-code-review-rules-for-codex
  - https://developers.openai.com/blog/designing-delightful-frontends-with-gpt-5-4
- OpenAI plugin examples and Codex source:
  - https://github.com/openai/plugins
  - https://github.com/openai/codex
- Agent Plugins specification 1.0.0:
  - https://github.com/agentplugins/agent-plugins-spec
- Agent Skills specification:
  - https://agentskills.io/specification
- Anthropic public skills and official plugin directory:
  - https://github.com/anthropics/skills
  - https://github.com/anthropics/claude-plugins-official
- Google DESIGN.md:
  - https://github.com/google-labs-code/design.md
- Laravel Boost:
  - https://github.com/laravel/boost

## User-supplied repositories reviewed

| Repository | Inspected revision | Pattern adopted | Pattern intentionally not adopted |
|---|---|---|---|
| `mattpocock/skills` | `8b78b531ab965735c5dc74f6f7a219e1e37326df` | small composable skills, domain vocabulary, bounded implementation | unconditional commit behavior and one methodology owning every project |
| `kepano/obsidian-skills` | `a1dc48e68138490d522c04cbf5822214c6eb1202` | clean Agent Skills portability and open formats | domain-specific Obsidian behavior |
| `Cjbuilds/Codex-Orchestration` | `2c0a4b83f1d12618c5452333962393ab6412dedc` | explicit roles, root orchestrator authority, activation truthfulness | provider routing, subscription bridges, fixed current model names |
| `google-labs-code/design.md` | `9bf8eae67128b6cc55ad9bf86665767deb4c11cd` | machine-readable tokens plus human rationale | making one experimental format mandatory for every project |
| `nexu-io/open-design` | `30fc648f6f615fde5b162cbee1177f94ea2dba6c` | design contract, visual artifact verification, multi-client thinking | large runtime, cloud service, BYOK proxy, media pipeline |
| `affaan-m/ECC` | `c9de8f5b2b3a225bca9befa2b7700aa5e3a4d1b8` | research-first operation, memory/eval/security awareness | hundreds of always-available skills and overlapping installation paths |
| `multica-ai/andrej-karpathy-skills` | `2c606141936f1eeef17fa3043a72095b4765b9c2` | simplicity, surgical changes, explicit assumptions, goal evidence | one global file as the entire workflow |
| `obra/superpowers` | `b36e0829c6d0140e93cfef2ca599b1b07d4a7797` | systematic debugging, verification before completion, skill behavior evals | mandatory TDD for every surface and automatic subagent workflow for ordinary tasks |

## Additional engineering references

- `github/spec-kit`: specification and traceability artifacts.
- `EveryInc/compound-engineering-plugin`: research, review, and knowledge compounding.
- `humanlayer/advanced-context-engineering-for-coding-agents`: intentional context management.
- `agentsmd/agents.md`: repository instruction convention.
- `NousResearch/hermes-agent`: Agent Skills compatibility and progressive disclosure.

## Provenance policy

Before importing code or text:

1. inspect the exact license;
2. pin the source revision;
3. identify whether the material is copied, adapted, or independently synthesized;
4. preserve required notices;
5. reject sources with unclear rights when copying is unnecessary.

This repository currently uses independent synthesis and ordinary factual references only.
