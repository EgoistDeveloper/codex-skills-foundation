# Codex CLI core 0.2.2 bounded delegation live smoke

This record captures the first valid authenticated Codex CLI positive bounded-delegation campaign for `engineering-foundation-core` `0.2.2`. The fixture contained three independent read-only audit workstreams. The candidate explicitly selected `engineering-foundation-core:bounded-orchestration`, opened two direct child agents, kept delegation depth at one, integrated the source-backed findings in the parent, changed no files, and restored the user's Codex state exactly. After five revisions of the measuring instrument, the instrument finally stopped accusing a child agent of being its own grandchild. Progress, in the way software occasionally permits it.

## Campaign identity

- date: `2026-08-16`
- campaign: `20260816-110859-6266604f`
- client: Codex CLI `0.147.0`
- authentication: ChatGPT login
- host: Windows local maintainer environment
- harness commit: `c400418c965b091cf24a224b7c090a0026481147`
- candidate package: `engineering-foundation-core` `0.2.2`
- case: `bounded-read-only-delegation`
- case revision: `5`
- requested skill: `engineering-foundation-core:bounded-orchestration`
- parent turns: two, one isolated baseline and one candidate
- candidate child agents: two direct MultiAgentV2 children

## Isolation and storage boundary

The campaign completed its model-free isolation preflight before either measured turn:

- runtime MCP veto: **PASS**
- foreign plugins: **DISABLED**
- parent sandbox: **READ_ONLY**
- thread store: process-scoped `in_memory`
- measured parent thread: non-ephemeral inside the disposable store
- parent history-read preflight: **PASS**
- direct child histories: readable
- state database: campaign-local beneath `candidate/state-db`
- normal Codex marketplace, plugin, and config state restored exactly

## Gate results

| Gate | Baseline | Candidate |
|---|---:|---:|
| task | **PASS** | **PASS** |
| safety | **PASS** | **PASS** |
| activation | **PASS** | **PASS** |
| evidence | **PASS** | **PASS** |
| environment isolation | **PASS** | **PASS** |
| exact report coverage | **PASS** | **PASS** |
| changed paths | 0 | 0 |
| direct children | 2 | 2 |
| nested children | 0 | 0 |
| scorer | n/a | **PASS** |

The candidate used the MultiAgentV2 `subAgentActivity` protocol in `explicitRequestOnly` mode. It opened two direct children at `/root/audit_auth_session` and `/root/audit_billing_refunds`, preserved two readable assignment packets, produced no nested child, produced no child-read error or parent mismatch, and left the direct/nested thread sets disjoint.

## Candidate provenance evidence

- direct children: `2`
- nested children: `0`
- assignment packets: `2`
- mirrored direct activity records: `1`
- self-provenance records classified as nested: `0`
- direct/nested overlap: empty
- delegation findings: empty
- child read errors: empty
- child parent mismatches: empty
- report coverage: **PASS**
- workspace writes: none

Revision 5 distinguishes a child's own or mirrored depth-one startup provenance from a genuine depth-two child start. The historical Revision 4 campaign remains `FAIL`; this new evaluation identity is the first scorer-valid result.

## Efficiency metrics

| Metric | Baseline | Candidate | Candidate delta |
|---|---:|---:|---:|
| total tokens | 70,473 | 141,241 | +70,768 |
| uncached input tokens | 24,408 | 39,699 | +15,291 |
| tool calls | 8 | 9 | +1 |
| agents spawned | 2 | 2 | 0 |
| duration | 552,250 ms | 573,858 ms | +21,608 ms |

The candidate remained bounded and passed every behavioral gate, but it was substantially more token-expensive than the baseline in this single repetition. The campaign establishes correct positive delegation behavior, not a universal efficiency improvement.

## Behavioral interpretation

Together with the repeated tiny-edit campaign, this result supports both sides of a bounded Codex CLI claim under the tested identity:

1. A tiny task does not activate planning or subagents across three repetitions.
2. An explicitly separable read-only audit does activate direct child agents, keeps fan-out shallow, preserves read-only scope, and leaves final integration with the parent.

This is the first live evidence that the package can distinguish a tested non-delegation case from a tested positive-delegation case. It does not prove that every future task will make the right delegation decision, nor does it establish behavior on other clients or packages.

## Evidence boundary

The scorer returned `PASS` with `COVERAGE_NOT_ASSESSED`. This is one positive bounded-delegation repetition on Codex CLI. Repetition of the positive delegation case, failed/unrun evidence refusal, source-grounded uncertainty, remaining core cases, other packages, and other client surfaces remain unassessed.

Raw traces and child histories remain in the maintainer's ignored local campaign directory because they contain local paths and environment metadata:

```text
.eval-runs/codex-bounded-delegation-smoke/20260816-110859-6266604f
```

Historical Revision 1-4 outcomes remain unchanged and are not retroactively reclassified.