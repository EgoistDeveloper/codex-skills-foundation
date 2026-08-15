# Upstream adoption matrix

Accessed: 2026-08-15. Re-check upstream before release because these formats and clients change quickly.

| Source | Adopt | Do not adopt wholesale | Local decision |
|---|---|---|---|
| Agent Plugins 1.0.0 | Root `plugin.json`, fixed `skills/`, optional `mcp.json`, path containment, closed schema | Pretending every client supports every component | Portable manifest per plugin plus separate Codex/Claude adapters |
| Agent Skills specification | `SKILL.md`, precise trigger description, progressive disclosure, focused references | Large always-loaded bodies or broad experimental tool grants | Skills stay portable and under repository limits |
| OpenAI plugins / Codex docs | `.codex-plugin/plugin.json`, local marketplace policy, skill discovery, bounded subagents, evidence and trace-based evals | Copying the curated marketplace, hard-coding model names, or assuming write-heavy parallelism is free | Minimal Codex adapter generated from catalog plus optional project-scoped read-only profiles |
| Anthropic skills / Claude Code docs | Plugin auto-discovery, concise skills, strict plugin validation, baseline-on/off evals, report-only subagents | Claude-only frontmatter in portable skills; huge preloaded instruction files; silent project-agent installation | Minimal Claude adapter plus explicit optional project-scoped read-only profiles |
| GitHub Spec Kit | Requirement -> plan -> tasks -> implementation traceability for complex work | Mandatory artifact ceremony for tiny tasks | Durable plan only when complexity/risk warrants it |
| OpenAI Harness Engineering | Short repository map, plans as first-class artifacts, deterministic tools, fast feedback | Treating repository docs as an encyclopedic dump | Short AGENTS.md plus focused docs and checks |
| Superpowers | Skill behavior testing, systematic debugging, TDD/review discipline | Installing every workflow or allowing conflicting lifecycle owners | Selected principles rewritten and measured locally |
| Compound Engineering | Research before plan, evidence-oriented review, compounding durable knowledge | Full package due context and overlap cost | Selected review and knowledge patterns only |
| Laravel Boost | Version-aware project context and official Laravel documentation tools | Copying changing framework guidance into this repo | Optional project-local package; Boost remains external source |
| Google `design.md` | Token+rationale contract, lint/diff, accessibility semantics | Making an alpha format mandatory | Consume and lint when present; optional otherwise |
| `open-design` | Visual QA breadth and design-system decomposition | 100+ skills/plugins in a general engineering core | Use as design research, not dependency |
| ECC | Broad harness ideas, memory/review/testing catalog | Wholesale installation and duplicate path/config layers | No runtime dependency |
| `andrej-karpathy-skills` | Caution, simplicity, explicit uncertainty | Treating short principles as a tested harness | Principles only |
| Codex-Orchestration | Root authority, bounded roles, external credential caution | Mandatory cross-provider router and repeated review loops | Host-native bounded delegation, no external router |
| 12 Factor Agents | Own prompts/context/control flow, compact errors, deterministic code boundary | Treating principles as an installable runtime | Design doctrine |
| mini-swe-agent | Minimal loop as complexity benchmark | Chasing a benchmark score as package architecture | Reference only |
| MCP specification | Official protocol, authorization and transport requirements | Auto-installing reference/community servers | Deny-by-default admission gate |
| Pydantic AI / OpenAI Agents SDK | Typed eval/tracing and handoff concepts | Python runtime dependency in this instruction repository | Reference for schemas and evaluation design |
| mattpocock/skills | Small composable skills and user/model invocation distinction | Duplicating overlapping workflow packs | Trigger-boundary reference |
| kepano/obsidian-skills | Focused domain skill packaging | Using domain-specific content as engineering process authority | Format example only |

## Primary source URLs

- https://agent-plugins.org/
- https://github.com/agentplugins/agent-plugins-spec
- https://agentskills.io/specification
- https://developers.openai.com/codex/build-skills
- https://developers.openai.com/codex/build-plugins
- https://developers.openai.com/codex/subagents
- https://github.com/openai/plugins
- https://code.claude.com/docs/en/skills
- https://code.claude.com/docs/en/plugins
- https://github.com/anthropics/skills
- https://github.com/github/spec-kit
- https://github.com/laravel/boost
- https://github.com/modelcontextprotocol/modelcontextprotocol
- https://github.com/obra/superpowers
- https://github.com/EveryInc/compound-engineering-plugin
- https://github.com/humanlayer/12-factor-agents
- https://github.com/SWE-agent/mini-swe-agent
- https://github.com/google-labs-code/design.md
