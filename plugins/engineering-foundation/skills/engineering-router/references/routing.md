# Routing table

| Signal | Preferred route |
|---|---|
| One to five coupled files, one domain, clear tests | single-agent |
| Small bug with reproducible symptom | single-agent |
| Large read-only codebase exploration | single-agent-with-specialists or bounded-multi-agent |
| Current docs plus implementation | researcher specialist, then primary writer |
| UI implementation needing visual critique | primary writer plus read-only designer/verifier |
| High-risk migration with one shared schema | primary writer plus planner/reviewer/verifier |
| Two or more independent modules with exclusive files | bounded-multi-agent may be justified |
| Shared write surface, broad rename, cross-cutting refactor | single-agent integration |
| User says no subagents | single-agent |
| Unclear goal | goal-contract before routing write work |

## Delegation budget

Default limits:

- at most three concurrent specialists;
- one delegation level;
- at most two plan-review cycles;
- one independent code review;
- one re-review only after material fixes.

A subagent result is an evidence packet, not authority. The primary agent verifies it.
