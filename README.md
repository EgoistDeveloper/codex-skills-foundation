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

## Codex end-user install

A normal Codex user needs only the marketplace and the package they intend to use:

```bash
codex plugin marketplace add EgoistDeveloper/codex-skills-foundation --ref main
codex plugin add engineering-foundation-core@egoist-engineering-foundation
```

Install Laravel, design, cloud, or authoring only when needed, then start a new thread so discovery metadata reloads. End users do not run the repository's Python validation, package hashes, JSON-RPC probes, or live evaluation harness.

The marketplace manifest is `.agents/plugins/marketplace.json`. Every skill includes a minimal `agents/openai.yaml`; provider-neutral behavior remains in `SKILL.md`.

## Claude Code end-user install

```bash
claude plugin marketplace add EgoistDeveloper/codex-skills-foundation
claude plugin install engineering-foundation-core@egoist-engineering-foundation
```

Install optional packages with the same marketplace suffix. During plugin development, Claude Code can load a directory directly:

```bash
claude --plugin-dir ./plugins/engineering-foundation-core
```

## Maintainer validation

Maintainers need Python 3.11+ and the development dependencies:

```bash
python -m pip install -r requirements-dev.txt
python scripts/bootstrap.py
```

Wrappers are also available:

```bash
./scripts/bootstrap.sh
```

```powershell
./scripts/bootstrap.ps1
```

The deterministic bootstrap validates structure, schemas, tests, evidence fixtures, and release packages. It does not call a model.

The one-command authenticated Codex behavior smoke is separate:

```bash
python scripts/run_codex_live_smoke.py --confirm-live
```

It runs one plugin-disabled baseline and one explicitly activated core-skill candidate, writes reviewable artifacts under `.eval-runs/`, and restores the original Codex plugin/config state. See [`docs/live-smoke.md`](docs/live-smoke.md).

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
- `scripts/run_codex_live_smoke.py` produces one authenticated baseline/candidate smoke, not full release qualification.

See [`docs/evals.md`](docs/evals.md), [`docs/qualification.md`](docs/qualification.md), [`docs/live-smoke.md`](docs/live-smoke.md), and [`docs/release-evidence.md`](docs/release-evidence.md).

## Security

The default distribution ships no MCP server, hooks, telemetry, credential bridge, network client, model pin, recursive delegation, global installer, or destructive automation. The optional live smoke uses the user's existing authenticated Codex session only after explicit confirmation; it never copies credential files. See [`SECURITY.md`](SECURITY.md), [`PRIVACY.md`](PRIVACY.md), and [`docs/security.md`](docs/security.md).
