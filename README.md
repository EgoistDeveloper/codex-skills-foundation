# Codex Skills Foundation v0.2 Candidate

A lean, provider-neutral engineering foundation for Codex, ChatGPT, Claude Code, and clients that implement the open Agent Skills or Agent Plugins specifications.

This tree is a **clean-room candidate**, not a verified patch against Pull Request #1. The source PR was not readable from the environment that produced this package. Compare it with the actual branch before merging; matching file names are not evidence of matching behavior.

## Package model

| Package | Install by default? | Purpose |
|---|---:|---|
| `engineering-foundation-core` | Yes | Contracts, planning, bounded orchestration, implementation, debugging, review, verification, and handoff |
| `engineering-foundation-laravel` | Only for Laravel/PHP repos | Project-local Laravel workflow; delegates current framework guidance to Laravel Boost when present |
| `engineering-foundation-design` | Only for UI work | Design direction, typography/tokens, implementation states, and visual verification |

The split is deliberate. Skill names and descriptions consume discovery context before a skill body loads. Installing only the relevant package is cheaper and reduces accidental activation.

## Compatibility layers

Each plugin directory contains three independent manifests:

- `plugin.json`: Agent Plugins 1.0.0 portable manifest.
- `.codex-plugin/plugin.json`: OpenAI ChatGPT/Codex package manifest.
- `.claude-plugin/plugin.json`: Claude Code package manifest.

Shared metadata is generated from `catalog/plugins.json`; provider manifests remain separate because their schemas and runtime behavior are not identical.

## Requirements and validation

Repository checks require Python 3.11 or newer. No third-party Python package is needed for the normal bootstrap.

Linux/macOS/WSL:

```bash
./scripts/bootstrap.sh
```

Windows PowerShell:

```powershell
./scripts/bootstrap.ps1
```

Direct checks:

```bash
python scripts/render_manifests.py --check
python scripts/validate_repository.py --strict
python -m unittest discover -s tests -v
python scripts/evidence_gate.py \
  examples/completion-evidence.pass.json \
  --contract examples/task-contract.static-validation.json
python scripts/score_eval_runs.py \
  evals/fixtures/sample-runs.jsonl \
  --allow-synthetic
```

The sample eval rows are synthetic and test only the scorer. A green scorer result is not a provider qualification result. Live release runs must satisfy the complete surface/case matrix in `docs/qualification.md`.

## Optional project-scoped agents

The portable workflow works with host-native subagents. Three narrow, model-neutral, read-only project profiles are also supplied for repeated exploration, review, and evidence-audit work.

Dry run first:

```bash
python scripts/install_agent_profiles.py --provider codex --target /path/to/project
python scripts/install_agent_profiles.py --provider claude --target /path/to/project
```

Add `--apply` only after reviewing destinations. Existing conflicting files are not overwritten unless `--force` is explicit. See `docs/agent-profiles.md`.

## Installation testing

Use the provider's current local-marketplace workflow. Do not copy files into global configuration silently. Validate a local install, restart or reload the client when required, and execute `docs/qualification.md` before sharing a release.

## Intentionally absent

- No MCP server.
- No lifecycle hook that can block or mutate user work.
- No credentials, telemetry, or external-model router.
- No hard-coded model names.
- No recursive agent delegation.
- No automatic commits, pushes, merges, migrations, or deployment.
- No claim that static unit tests prove model behavior.

See `AUDIT_REPORT_TR.md` for the research-backed decisions and `MIGRATION_FROM_PR1.md` for a safe comparison workflow.
