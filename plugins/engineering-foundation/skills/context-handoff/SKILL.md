---
name: context-handoff
description: Compact a long or interrupted engineering task into a durable evidence-focused handoff. Use before context reset, model/client transfer, or pausing complex work; do not dump raw logs.
---

# Context Handoff

Create a compact artifact another agent can trust.

Include:

- goal and non-goals;
- repository, branch, baseline SHA, and worktree state;
- accepted decisions and rejected alternatives;
- files changed and why;
- commands run with outcomes;
- requirement evidence;
- unresolved blockers and uncertainty;
- exact next action;
- valid completion-reopen reasons.

Exclude:

- raw search history;
- full test logs when a command and result suffice;
- speculative ideas not adopted;
- credentials or private environment values;
- claims not supported by repository state.

Prefer checked-in `docs/progress/<task>.md` only when the project benefits from a durable artifact. Otherwise return the handoff in chat.

## Stop condition

The handoff is complete when a fresh agent can continue without repeating broad exploration and can distinguish fact, decision, and open question.
