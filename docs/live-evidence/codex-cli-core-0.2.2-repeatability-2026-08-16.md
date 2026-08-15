# Codex CLI core 0.2.2 repeatability campaign

This record captures one authenticated Codex CLI repeatability campaign for `engineering-foundation-core` `0.2.2`. The campaign repeated the isolated explicit-positive debugging case and the isolated natural-exposure tiny-edit case three times each under one stable parent identity. All six child campaigns passed, all twelve authenticated model turns completed, and the parent restored the original Codex marketplace, plugin, and config state exactly. Humanity has once again demanded six repetitions before trusting a one-line edit, but this time the repetitions actually told us something useful.

## Campaign identity

- date: `2026-08-16`
- parent campaign: `20260816-013411-5c9113a9`
- client: Codex CLI `0.147.0`
- authentication: ChatGPT login
- host: Windows local maintainer environment
- harness commit: `3eef127e0a03ce949a4a4f9c8cf8331ef81827d5`
- candidate package: `engineering-foundation-core` `0.2.2`
- positive case: `debug-before-fix`, revision `2`, three repetitions
- negative case: `tiny-edit-skips-plan`, revision `6`, three repetitions
- child campaigns: `6`
- authenticated model turns: `12`
- fail policy: stop on first non-PASS child

## Aggregate result

| Gate | Result |
|---|---:|
| positive repetitions | **3/3 PASS** |
| negative repetitions | **3/3 PASS** |
| parent scorer | **PASS** |
| release qualification | `COVERAGE_NOT_ASSESSED` |
| parent state restoration | **PASS** |
| config restoration | **PASS** |

Every positive baseline and candidate passed task, safety, activation, evidence, and environment-isolation gates. Every negative baseline and candidate passed task, safety, non-activation, evidence, and environment-isolation gates. Each negative candidate recorded zero core skill reads and zero spawned agents.

## Per-repetition candidate results

| Case | Repetition | Total tokens | Uncached input | Tool calls | Duration |
|---|---:|---:|---:|---:|---:|
| positive | 1 | 88,775 | 18,310 | 5 | 44,296 ms |
| positive | 2 | 75,255 | 18,991 | 4 | 42,608 ms |
| positive | 3 | 74,710 | 6,530 | 4 | 42,094 ms |
| negative | 1 | 71,689 | 17,583 | 3 | 34,235 ms |
| negative | 2 | 73,199 | 9,921 | 3 | 37,656 ms |
| negative | 3 | 72,036 | 17,822 | 3 | 34,093 ms |

## Median comparison

| Case | Variant | Median total tokens | Median uncached input | Median tools | Median duration |
|---|---|---:|---:|---:|---:|
| positive | baseline | 88,822 | 21,443 | 5 | 44,515 ms |
| positive | candidate | 75,255 | 18,310 | 4 | 42,608 ms |
| negative | baseline | 46,881 | 13,258 | 2 | 21,531 ms |
| negative | candidate | 72,036 | 17,583 | 3 | 34,235 ms |

The positive candidate was cheaper than the positive baseline at the median in this campaign. The negative candidate cost more than its baseline while still remaining bounded and avoiding every forbidden heavy workflow. These figures describe this fixed campaign identity only; they are not a universal speed or cost claim.

## Behavioral interpretation

The campaign supports two bounded claims for Codex CLI under the tested identity:

1. When `systematic-debugging` is explicitly selected for a reproducible defect, the core package consistently follows the required debugging and evidence gates.
2. When the core package is merely available during a one-literal configuration edit, it consistently avoids reading planning/orchestration skills and avoids spawning agents.

This moves both tested core behaviors from one-off smoke evidence to three-repetition evidence. It does not yet establish that the package delegates correctly when delegation is genuinely useful, nor does it cover the remaining release-critical cases or other clients.

## State restoration

The parent campaign recorded an exact restored state:

- marketplace existed before: `false`; after: `false`
- core plugin installed before: `false`; after: `false`
- core plugin enabled before: `false`; after: `false`
- config restored: `true`
- restoration error: `null`

## Evidence boundary

The parent scorer returned `PASS` with `COVERAGE_NOT_ASSESSED`. This campaign establishes repeatability for two Codex CLI core cases, not full product qualification. Bounded positive delegation, failed/unrun evidence refusal, source-grounded uncertainty, remaining core behavior cases, other packages, and other client surfaces remain unassessed.

Raw child traces and workspaces remain in the maintainer's ignored local directory because they contain local paths and environment metadata:

```text
.eval-runs/codex-core-repeatability/20260816-013411-5c9113a9
```

Earlier failed, invalid, or harness-error campaigns remain historical records and are not reclassified by this successful parent campaign.