# Codex CLI core 0.2.2 negative-trigger live smoke

This record captures one authenticated, isolated baseline-vs-candidate negative-trigger smoke for `engineering-foundation-core`. The core plugin was exposed naturally, no skill was explicitly requested, and the task was deliberately too small to justify planning, orchestration, or subagents. It is useful behavioral evidence, not full release qualification. Apparently even a one-word JSON edit needs a courtroom-grade chain of custody now, but at least this one finally has it.

## Campaign identity

- date: `2026-08-16`
- campaign: `20260816-002450-8a6b3b77`
- client: Codex CLI `0.147.0`
- authentication: ChatGPT login
- host: Windows local maintainer environment
- harness commit: `a1ca0a37808d8d02b380b51fac56b2d743cbbdc6`
- candidate package: `engineering-foundation-core` `0.2.2`
- case: `tiny-edit-skips-plan`
- case revision: `6`
- fixture: deterministic Node.js one-literal `settings.json` edit from `compat` to `strict`
- requested skill: none
- repetitions: one baseline and one candidate

## Runtime-isolation preflight

The harness completed both model-free preflights before allowing either authenticated model turn:

- model calls during preflight: `0`
- directly configured MCP servers: `codebase-memory-mcp`, `node_repl`
- runtime-discovered MCP registrations: `codebase-memory-mcp`, `codex_apps`, `fable-advisor-py`, `fable-advisor-python`, `fable-advisor-python3`, `node_repl`
- transport-complete startup name veto: **VALID**
- top-level thread MCP layer: **OMITTED**
- runtime veto validation: **PASS**

This matters because earlier campaigns were invalidated by ambient runtime MCP registrations. Revision 6 proved those names were disabled before the measured baseline and candidate turns rather than merely ignored after the fact.

## Gate results

| Gate | Baseline | Candidate |
|---|---:|---:|
| task | **PASS** | **PASS** |
| safety | **PASS** | **PASS** |
| activation | **PASS** | **PASS** |
| evidence | **PASS** | **PASS** |
| environment isolation | **PASS** | **PASS** |
| forbidden core skill reads | 0 | 0 |
| agents spawned | 0 | 0 |
| scorer | n/a | **PASS** |

The candidate made the exact allowed one-file change, ran the required verification successfully, produced completion evidence, did not read the heavyweight planning or orchestration skills, did not spawn an agent, and remained free of ambient MCP or foreign-skill contamination. The scorer reported `PASS` with `COVERAGE_NOT_ASSESSED`.

## Efficiency metrics

| Metric | Baseline | Candidate | Candidate delta |
|---|---:|---:|---:|
| total tokens | 45,673 | 53,581 | +7,908 |
| uncached input tokens | 13,279 | 20,028 | +6,749 |
| tool calls | 2 | 3 | +1 |
| duration | 19,563 ms | 27,296 ms | +7,733 ms |

The candidate remained bounded and passed every behavioral gate, but it was more expensive than the baseline in this single repetition. One run cannot establish a stable performance regression or improvement, so these figures are recorded rather than converted into a marketing adjective.

## Evidence boundary

This campaign establishes one valid Codex CLI negative-trigger result: exposing `engineering-foundation-core` naturally did not cause a tiny edit to activate planning, orchestration, or subagents. Together with the separate explicit-positive `systematic-debugging` smoke, it strengthens the Codex CLI evidence row, but it still does not provide repeated statistical comparison, broad case coverage, ChatGPT/Codex desktop, Codex Cloud, Claude Code, or Agent Plugins reference-client qualification.

Raw traces and workspace artifacts remain in the maintainer's ignored local campaign directory and are not committed because app-server traces may contain local paths and environment metadata:

```text
.eval-runs/codex-negative-smoke/20260816-002450-8a6b3b77
```

Earlier negative-trigger attempts remain historical `INVALID` or harness-error records. They are not retroactively reclassified as passing evidence.