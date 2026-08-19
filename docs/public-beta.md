# Engineering Foundation public beta

`v0.3.0-beta.2` is the current public beta of `engineering-foundation-core`; `v0.3.0-beta.1` remains available as the immutable first public beta. The beta is intended for real project use with reviewable safeguards, not as a claim that probabilistic agents have suddenly become incapable of error. Software marketing has tried that sentence before; reality was unimpressed.

## Release scope

| Package | Version in this repository release | Evidence level |
|---|---:|---|
| `engineering-foundation-core` | `0.3.0-beta.2` | static/provider validation plus exact-artifact authenticated Codex CLI behavior evidence |
| `engineering-foundation-laravel` | `0.2.1` | static/provider validation |
| `engineering-foundation-design` | `0.2.1` | static/provider validation |
| `engineering-foundation-cloud` | `0.2.1` | static/provider validation |
| `engineering-foundation-authoring` | `0.2.1` | static/provider validation |

The optional packages are included because they remain installable and cross-platform reproducible. They are not presented as having the same live-behavior coverage as Core.

## Pinned Codex installation

Use the release tag for a reproducible installation:

```text
codex plugin marketplace add EgoistDeveloper/codex-skills-foundation --ref v0.3.0-beta.2
codex plugin add engineering-foundation-core@egoist-engineering-foundation
```

Start a new Codex thread after installation so skill discovery metadata reloads.

Install optional packages only when the project needs them:

```text
codex plugin add engineering-foundation-laravel@egoist-engineering-foundation
codex plugin add engineering-foundation-design@egoist-engineering-foundation
codex plugin add engineering-foundation-cloud@egoist-engineering-foundation
codex plugin add engineering-foundation-authoring@egoist-engineering-foundation
```

Inspect the installed state:

```text
codex plugin list --marketplace egoist-engineering-foundation
```

## Updating

### From an older tracked branch

A marketplace configured against a moving branch can be refreshed and the package reinstalled in place:

```text
codex plugin marketplace upgrade egoist-engineering-foundation
codex plugin add engineering-foundation-core@egoist-engineering-foundation
```

### From one pinned release tag to another

Pinned tags do not move. Remove the old marketplace source, add the newer tag, and reinstall:

```text
codex plugin remove engineering-foundation-core@egoist-engineering-foundation
codex plugin marketplace remove egoist-engineering-foundation
codex plugin marketplace add EgoistDeveloper/codex-skills-foundation --ref <new-release-tag>
codex plugin add engineering-foundation-core@egoist-engineering-foundation
```

Optional packages can be removed and reinstalled by the same pattern. This is less magical than an invisible updater, which is exactly why its state is reviewable.

## Removing

Remove installed packages first, then remove the marketplace:

```text
codex plugin remove engineering-foundation-core@egoist-engineering-foundation
codex plugin marketplace remove egoist-engineering-foundation
```

If optional packages were installed, remove those before removing the marketplace.

## Tested Core behavior

Authenticated Codex CLI campaigns support the following bounded claims under the recorded test identities:

- explicit `systematic-debugging` follows reproduction and fresh-verification gates;
- a tiny edit avoids durable planning and subagents across three repetitions;
- a separable read-only audit uses direct child agents, keeps delegation depth at one, changes no files, and leaves integration with the parent;
- a blocked required verifier produces a structured `BLOCKED` result rather than a false `COMPLETE` claim.

See [`qualification.md`](qualification.md) and the records in [`live-evidence/`](live-evidence/).

## What the beta does not promise

The beta does not retrain the model, eliminate hallucinations, guarantee every delegation decision, or make an agent's prose true merely because it sounds professionally disappointed. It provides portable operating rules and evidence gates designed to reduce:

- unsupported completion claims;
- scope drift and unrelated edits;
- speculative post-success rewrites;
- unnecessary planning and subagent fan-out;
- unbounded delegation;
- technical claims made without current repository or source evidence.

Live evidence currently covers Codex CLI, not every desktop, Cloud, Claude Code, or reference Agent Plugins surface. Optional package behavior remains less qualified than Core.

## Maintainer lifecycle check

The final release-candidate lifecycle uses an isolated `CODEX_HOME`, a loopback-only temporary Git marketplace, and zero model calls:

```text
python scripts/run_public_beta_lifecycle.py
```

At the published `v0.3.0-beta.2` tag, the exact-artifact lifecycle installs the five frozen release archives, discovers fourteen skills, verifies archive-derived installed content, removes every package and marketplace entry, and proves that the disposable configuration is restored. End users do not run this harness.

For future release candidates, maintainers build a deterministic `release-candidate.json` and run the exact-artifact wrapper. This path extracts the five qualified ZIPs into a disposable marketplace, verifies installed content against the archive-derived content hashes, uses a disposable `CODEX_HOME`, makes zero model calls for lifecycle qualification, and removes every candidate package and marketplace entry:

```bash
python scripts/release_candidate.py build --artifacts dist
python scripts/run_exact_artifact_qualification.py \
  --candidate-manifest dist/release-candidate.json \
  --artifacts dist \
  --lifecycle-only
```

The published `v0.3.0-beta.2` release is bound to commit `98658cd359a05022247622ae00e805ada6c7cfbd` and candidate-manifest SHA-256 `a22be1e252142da8abcab84a0f18006319245702f5f8f03c872c3c85d101ddcc`. Its exact package hashes and bounded qualification record are in [`releases/v0.3.0-beta.2.md`](releases/v0.3.0-beta.2.md). Qualification remains `PARTIAL`: the in-scope Codex CLI cases passed, while ChatGPT/Codex desktop, Codex Cloud, authenticated Claude Code, and the Agent Plugins reference client remain `NOT_RUN`.
