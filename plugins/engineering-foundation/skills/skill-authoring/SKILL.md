---
name: skill-authoring
description: Create or revise a compact Agent Skill with precise triggers, progressive disclosure, deterministic helpers, and positive/negative evals. Use for skill maintenance; do not publish untested broad prompts.
---

# Skill Authoring

## Design

1. Define one reusable capability and its non-goals.
2. Write a specific `description` that distinguishes when the skill should and should not trigger.
3. Put the common workflow and stop condition in `SKILL.md`.
4. Move detailed references, templates, and edge cases to `references/` or `assets/`.
5. Use a script for deterministic parsing, validation, or transformation instead of asking the model to regenerate it.
6. Keep provider-specific behavior in adapters.
7. Define security and permission boundaries.

## Evaluate

Add cases for:

- intended implicit trigger;
- explicit invocation;
- near-miss that must not trigger;
- smallest task that should skip the skill;
- failed evidence;
- interruption or missing-tool behavior;
- overlap with neighboring skills.

Run repository validation and live behavior evals before calling the skill stable.

## Change discipline

Patch the smallest section. Do not rewrite a working skill merely to change voice or formatting. A changed trigger description is routing behavior and requires eval coverage.

## Stop condition

The skill is ready when its trigger is discriminative, instructions are bounded, references resolve, deterministic checks pass, and known client differences are documented.
