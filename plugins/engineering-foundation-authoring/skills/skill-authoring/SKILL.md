---
name: skill-authoring
description: Create or revise a compact Agent Skill or plugin package with precise trigger boundaries, progressive disclosure, provider adapters, provenance, deterministic helpers, and positive and negative evals. Use for skill or plugin maintenance. Do not publish broad untested prompts, duplicate provider schemas, copy third-party text, or add privileged hooks and MCP services without an explicit threat model.
---


# Skill Authoring

## Design

1. Define one reusable capability, its intended trigger, near misses, and non-goals.
2. Write a concise `description` that states when to use and when not to use the skill.
3. Keep the common workflow and stop condition in `SKILL.md`.
4. Move detailed templates, checklists, and edge cases into one-level `references/` or `assets/` paths.
5. Use deterministic scripts for parsing, validation, packaging, or transformation instead of asking the model to regenerate mechanics.
6. Keep portable behavior separate from provider-specific manifests and profiles.
7. Define permission, secret, filesystem, network, and destructive-action boundaries.
8. Record provenance and license decisions; synthesize original instructions rather than copying upstream prose.

## Evaluate

Cover intended implicit activation, explicit invocation, a near miss that must not trigger, the smallest task that should skip, failure evidence, unavailable tools, interruption/handoff, and overlap with neighboring skills. Separate static schema/tests from live provider behavior.

A trigger change is routing behavior and needs eval coverage. Patch the smallest section; do not rewrite a working skill merely to alter voice. Run repository validation, package checks, and live provider qualification before declaring a stable release.

See `references/release-checklist.md` for the publishing gate.
