# Codex Skills Foundation

A portable, evidence-driven engineering foundation for Codex, ChatGPT, Codex Cloud, Claude Code, and clients that implement Agent Skills or Agent Plugins.

The repository is intentionally modular. Install the small core everywhere, then add only the domain packages a project needs. This keeps discovery context smaller and reduces accidental activation.

## Packages

| Package | Install when | Skills |
|---|---|---|
| `engineering-foundation-core` | General engineering work | task contract, planning, bounded orchestration, implementation, debugging, source-grounded research, review, verification, handoff |
| `engineering-foundation-laravel` | Laravel/PHP repositories | project-aware Laravel engineering |
| `engineering-foundation-design` | Web/product UI work | design direction, rendered visual verification |
| `engineering-foundation-cloud` | Codex Cloud or remote-agent setup | safe environment readiness |
| `engineering-foundation-authoring` | Creating or maintaining skills/plugins | skill and plugin authoring |

## Design principles

- One accountable writing agent by default.
- Delegate only independent, bounded, evidence-producing work.
- One writer per file and delegation depth one.
- Use the smallest coherent change that satisfies the task contract.
- Stop after accepted evidence passes; no speculative post-success rewrite.
- Treat static validation, live behavior evals, and release qualification as different claims.
- Keep provider-specific metadata and agent profiles outside the portable skill contract.

## Requirements

- Python 3.11+
- Development validation dependencies:

```bash
python -m pip install -r requirements-dev.txt
```

Run the complete cross-platform validation:

```bash
python scripts/bootstrap.py
```

Wrappers are also available:

```bash
./scripts/bootstrap.sh
```

```powershell
./scripts/bootstrap.ps1
```

## Codex / ChatGPT marketplace

```bash
codex plugin marketplace add EgoistDeveloper/codex-skills-foundation --ref main
codex plugin add engineering-foundation-core@egoist-engineering-foundation
```

Install Laravel, design, cloud, or authoring only when needed, then start a new thread so discovery metadata reloads. The marketplace manifest is `.agents/plugins/marketplace.json`. Every skill includes a minimal `agents/openai.yaml`; provider-neutral behavior remains in `SKILL.md`.

## Claude Code marketplace

```bash
claude plugin validate . --strict
claude plugin marketplace add EgoistDeveloper/codex-skills-foundation
claude plugin install engineering-foundation-core@egoist-engineering-foundation
```

Install optional packages with the same marketplace suffix. During local development, Claude Code can load a plugin directory directly:

```bash
claude --plugin-dir ./plugins/engineering-foundation-core
```

## Optional project-scoped agents

Three narrow read-only profiles are supplied for repeated exploration, diff review, and evidence audit work. Preview before installation:

```bash
python scripts/install_agent_profiles.py --provider codex --target /path/to/project
python scripts/install_agent_profiles.py --provider claude --target /path/to/project
```

Add `--apply` after reviewing the destination. Existing conflicting files are not overwritten unless `--force` is explicit.

## Evidence and evals

- `schemas/task-contract.schema.json` defines stable acceptance IDs.
- `schemas/completion-evidence.schema.json` records fresh commands, inspections, runtime observations, and artifacts.
- `scripts/evidence_gate.py` requires exact contract coverage before `COMPLETE`.
- `scripts/score_eval_runs.py` compares plugin-disabled baseline, previous release, and candidate without pretending they share the same commit.
- Synthetic fixtures test scorer mechanics only and can never qualify a release.

See [`docs/evals.md`](docs/evals.md), [`docs/qualification.md`](docs/qualification.md), and [`docs/release-evidence.md`](docs/release-evidence.md).

## Security

The default distribution ships no MCP server, hooks, telemetry, credential bridge, network client, model pin, recursive delegation, global installer, or destructive automation. See [`SECURITY.md`](SECURITY.md), [`PRIVACY.md`](PRIVACY.md), and [`docs/security.md`](docs/security.md).
