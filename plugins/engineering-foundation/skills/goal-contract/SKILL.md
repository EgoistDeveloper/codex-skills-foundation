---
name: goal-contract
description: Convert a non-trivial request into explicit acceptance criteria, constraints, non-goals, and proof. Use before implementation when success is not already unambiguous; skip for obvious one-line edits.
---

# Goal Contract

Create a small contract that lets the agent finish without guessing.

## Contract fields

- **Goal:** observable outcome, not an implementation preference.
- **Context:** repository state and relevant domain facts.
- **Constraints:** compatibility, security, performance, style, tools, branch, and permission boundaries.
- **Acceptance criteria:** independently verifiable behaviors.
- **Non-goals:** nearby work that must remain untouched.
- **Assumptions:** only those required to proceed.
- **Evidence:** command, runtime observation, screenshot, query plan, or diff property that proves each criterion.

## Process

1. Extract explicit requirements from the user's words.
2. Inspect repository context before asking questions that code can answer.
3. Ask only when ambiguity blocks a safe or correct choice. Otherwise state the narrow assumption and proceed.
4. Write criteria at the behavior boundary. Avoid “clean,” “best,” or “professional” without observable meaning.
5. Keep implementation choices out of the goal unless the user made them constraints.
6. If the host exposes a durable Goal, treat it as the source of intent. Do not create a competing goal state.
7. Update the contract only when the user changes scope or new evidence invalidates an assumption.

## Stop condition

The contract is ready when every requested outcome has a proof method and every excluded adjacent change is visible. Do not continue interviewing after implementation can proceed safely.
