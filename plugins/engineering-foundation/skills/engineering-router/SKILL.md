---
name: engineering-router
description: Route a software-engineering request to the smallest reliable workflow. Use for mixed, non-trivial, or unclear coding tasks; do not use when the user already selected a narrower skill.
---

# Engineering Router

Choose the workflow before consuming implementation context.

## Route

1. Read the applicable `AGENTS.md`, user request, repository state, and available verification commands.
2. Classify the task:
   - question or current-source research;
   - bug diagnosis;
   - bounded implementation;
   - refactor or migration;
   - code review;
   - Laravel/PHP;
   - UI/product design;
   - Cloud/environment work.
3. Build a compact task profile: risk, uncertainty, estimated files, independent workstreams, shared write surfaces, external research, visual validation, and user delegation constraints.
4. If the bundled script is available, run:

   ```bash
   python <skill-root>/../../scripts/route_task.py <profile.json>
   ```

5. Select one route:
   - **single-agent** — default for small, coupled, or write-heavy work;
   - **single-agent-with-specialists** — primary writer plus bounded read-only research, planning, review, or verification;
   - **bounded-multi-agent** — only for genuinely independent workstreams.
6. Load only the domain skills needed for this task.
7. Keep the primary agent responsible for the goal contract, integration, final diff, and completion claim.

## Hard rules

- An explicit “no subagents” instruction disables delegation.
- Do not spawn agents merely because the feature exists.
- Do not assign overlapping file ownership.
- Do not create planner/advisor loops without a material unresolved question.
- Do not expose a lengthy routing ceremony to the user for trivial work.
- Prefer one capable agent over several agents repeating the same exploration.

## Stop condition

Routing is complete when the task has one owner, a bounded skill set, an evidence target, and no ambiguous write ownership. Continue into the selected workflow; do not keep reconsidering the route unless scope materially changes.

See `references/routing.md` for the decision table.
