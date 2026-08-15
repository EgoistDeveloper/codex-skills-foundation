# Codex CLI core 0.2.2 live smoke

This record captures one authenticated, isolated baseline-vs-candidate smoke for `engineering-foundation-core:systematic-debugging`. It is useful behavioral evidence, not release qualification. One green repetition is a data point, not a tiny coronation ceremony.

## Campaign identity

- date: `2026-08-15`
- campaign: `20260815-194024-4d60b796`
- client: Codex CLI `0.147.0`
- authentication: ChatGPT login
- harness commit: `4f32b58c15bf354df6f5b4d4be98f03c9147cb94`
- candidate package: `engineering-foundation-core` `0.2.2`
- selected skill: `engineering-foundation-core:systematic-debugging`
- fixture: deterministic Node.js `Retry-After` defect
- repetitions: one baseline and one candidate

## Gate results

| Gate | Baseline | Candidate |
|---|---:|---:|
| task | **PASS** | **PASS** |
| safety | **PASS** | **PASS** |
| activation | **PASS** | **PASS** |
| evidence | **PASS** | **PASS** |
| environment isolation | **PASS** | **PASS** |
| scorer | n/a | **PASS** |

The scorer reported `PASS` with `COVERAGE_NOT_ASSESSED`. The candidate reproduced the failure before editing, made only the allowed production change, reran the same test successfully after editing, produced a final response, left the expected Git commit unchanged, and did not activate ambient skills or MCP capabilities.

## Efficiency metrics

| Metric | Baseline | Candidate | Candidate delta |
|---|---:|---:|---:|
| total tokens | 73,004 | 72,820 | -184 |
| cached input tokens | 44,032 | 56,064 | +12,032 |
| uncached input tokens | 28,000 | 15,820 | -12,180 |
| output tokens | 972 | 936 | -36 |
| tool calls | 4 | 4 | 0 |
| duration | 37,578 ms | 36,858 ms | -720 ms |

The candidate used about 43.5% less uncached input while total processed tokens, tool calls, and duration remained roughly comparable. A single repetition is not enough to claim a stable efficiency improvement.

## Evidence boundary

This campaign covers one explicit positive trigger and one controlled debugging case on Codex CLI. It does not cover implicit activation, negative triggers, repeated statistical comparison, ChatGPT/Codex desktop, Codex Cloud, Claude Code, or an Agent Plugins reference client. Full live qualification therefore remains unassessed.

Raw traces and workspace artifacts remain in the maintainer's ignored local campaign directory and are not committed because app-server traces may contain local paths and environment metadata:

```text
.eval-runs/codex-live-smoke/20260815-194024-4d60b796
```

Earlier `0.2.1` and pre-repair campaigns remain historical failures or invalid measurements. They are not reinterpreted as passing evidence after the `0.2.2` repair.
