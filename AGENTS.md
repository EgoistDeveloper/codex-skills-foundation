# Repository instructions

## Purpose

This repository publishes a portable engineering workflow plugin. Treat behavior, compatibility, and evidence contracts as public API.

## Working rules

- Keep the portable core provider-neutral. Put platform-specific behavior under an adapter or manifest.
- Default to one writing agent. Delegate only independent, bounded work.
- Never add recursive delegation. The primary agent remains responsible for integration and final verification.
- Make the smallest change that satisfies the stated requirement. Do not refactor adjacent code.
- Once verification passes, do not reopen implementation for aesthetic cleanup unless a concrete defect, failed criterion, security issue, or user-requested scope change exists.
- Keep skill descriptions specific and compact because clients load them into the initial context.
- Put long checklists and edge cases under `references/` to preserve progressive disclosure.
- Do not add an MCP server, external executable, production dependency, credential flow, or network requirement without an explicit threat model and user approval.
- Do not copy third-party skill text. Record provenance and synthesize original instructions.

## Required verification

For every repository change, run:

```bash
python scripts/validate_repository.py --strict
python -m unittest discover -s tests -v
```

Also review the complete diff. A passing unit test does not prove documentation, manifest, or marketplace correctness.

## Review rules

- Flag any behavior that lets an agent claim completion without fresh evidence.
- Flag any workflow that makes multi-agent the default or permits overlapping write ownership.
- Flag any skill that silently expands scope after acceptance criteria pass.
- Flag model names, prices, limits, or product behavior presented as durable facts without a dated source.
- Flag unsupported manifest fields or paths that escape the plugin root.
- Flag design guidance that creates multiple unsolicited variants, generic dashboard-card mosaics, or inaccessible light/dark states.
