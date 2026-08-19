# Codex Skills Foundation

A portable, evidence-driven engineering foundation for Codex, ChatGPT, Codex Cloud, Claude Code, and clients that implement Agent Skills or Agent Plugins.

**Public beta:** `engineering-foundation-core` `0.3.0-beta.2`. See [`docs/public-beta.md`](docs/public-beta.md) for scope, installation, updates, removal, tested behavior, and limitations.

The repository is intentionally modular. Install the small core everywhere, then add only the domain packages a project needs. This keeps discovery context smaller and reduces accidental activation.

## Packages

| Package | Version in this release | Install when | Skills |
|---|---:|---|---|
| `engineering-foundation-core` | `0.3.0-beta.2` | General engineering work | task contract, planning, bounded orchestration, implementation, debugging, source-grounded research, review, verification, handoff |
| `engineering-foundation-laravel` | `0.2.1` | Laravel/PHP repositories | project-aware Laravel engineering |
| `engineering-foundation-design` | `0.2.1` | Web/product UI work | design direction, rendered visual verification |
| `engineering-foundation-cloud` | `0.2.1` | Codex Cloud or remote-agent setup | safe environment readiness |
| `engineering-foundation-authoring` | `0.2.1` | Creating or maintaining skills/plugins | skill and plugin authoring |

Only Core has the expanded authenticated live-behavior evidence used for this beta. Optional packages remain statically and provider-package validated at their existing versions.

## Design principles

- One accountable writing agent by default.
- Delegate only independent, bounded, evidence-producing work.
- One writer per file and delegation depth one.
- Use the smallest coherent change that satisfies the task contract.
- Stop after accepted evidence passes; no speculative post-success rewrite.
- Treat static validation, live behavior evals, and release qualification as different claims.
- Keep provider-specific metadata and agent profiles outside the portable skill contract.

## Codex end-user install

Use the pinned beta tag for a reproducible installation:

```bash
codex plugin marketplace add EgoistDeveloper/codex-skills-foundation --ref v0.3.0-beta.2
codex plugin add engineering-foundation-core@egoist-engineering-foundation
```

Install Laravel, design, cloud, or authoring only when needed, then start a new thread so discovery metadata reloads. End users do not run the repository's Python validation, package hashes, JSON-RPC probes, or live evaluation harnesses.

The marketplace manifest is `.agents/plugins/marketplace.json`. Every skill includes a minimal `agents/openai.yaml`; provider-neutral behavior remains in `SKILL.md`.

Update and removal commands are documented in [`docs/public-beta.md`](docs/public-beta.md).

## Claude Code end-user install

```bash
claude plugin marketplace add EgoistDeveloper/codex-skills-foundation
claude plugin install engineering-foundation-core@egoist-engineering-foundation
```

Install optional packages with the same marketplace suffix. During plugin development, Claude Code can load a directory directly:

```bash
claude --plugin-dir ./plugins/engineering-foundation-core
```

Claude manifests and packages are validated, but the recorded authenticated behavior matrix currently covers Codex CLI rather than Claude Code.

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

Authenticated Codex behavior campaigns are separate:

```bash
python scripts/run_codex_positive_smoke_isolated.py --confirm-live
python scripts/run_codex_negative_smoke_v4.py --confirm-live
python scripts/run_codex_core_repeatability.py --confirm-live --repetitions 3
python scripts/run_codex_bounded_delegation_smoke_v5.py --confirm-live
python scripts/run_codex_evidence_refusal_smoke.py --confirm-live
```

The final zero-model public-beta lifecycle check is:

```bash
python scripts/run_public_beta_lifecycle.py
```

It uses a disposable `CODEX_HOME` and loopback-only temporary Git marketplace to test previous-version install, marketplace upgrade, Core reinstall/update, all-package discovery, complete removal, and clean isolated state. See [`docs/live-smoke.md`](docs/live-smoke.md).

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
- Live campaign records cover repeated debugging/non-activation, positive bounded delegation, and failed-evidence refusal on Codex CLI.

See [`docs/evals.md`](docs/evals.md), [`docs/qualification.md`](docs/qualification.md), [`docs/live-smoke.md`](docs/live-smoke.md), [`docs/public-beta.md`](docs/public-beta.md), and [`docs/release-evidence.md`](docs/release-evidence.md).

## Security

The default distribution ships no MCP server, hooks, telemetry, credential bridge, network client, model pin, recursive delegation, global installer, or destructive automation. Optional live smokes use the user's existing authenticated Codex session only after explicit confirmation and never copy credential files. The lifecycle smoke makes zero model calls and confines all plugin state to a disposable home. See [`SECURITY.md`](SECURITY.md), [`PRIVACY.md`](PRIVACY.md), and [`docs/security.md`](docs/security.md).
