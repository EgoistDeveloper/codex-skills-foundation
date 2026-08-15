# v0.2.0 release evidence

This record separates deterministic repository/provider validation from authenticated model-behavior qualification. A green parser is not suddenly a sentient software engineer, however persuasive the badge may look.

## Source

- release version: `0.2.0`
- integration pull request: `#2`
- first fully green implementation revision: `c3220ab1f57fe906b92a50d571cc893d29ced39f`
- release tag: `v0.2.0` after the reviewed pull request is merged to `main`

## Deterministic validation

| Check | Result | Evidence |
|---|---|---|
| local Linux bootstrap | **PASS** | strict repository validator; 39 unit tests; Python compile; schemas, YAML, Markdown links, security scan, negative evidence fixtures, scorer self-test, deterministic packages |
| GitHub Linux bootstrap | **PASS** | workflow run `31877375363`, job `94994996918` |
| GitHub Windows bootstrap | **PASS** | workflow run `31877375363`, job `94994996931` |
| Claude marketplace and plugin validation | **PASS** | Claude Code `2.1.220`, strict validation of the root marketplace and all five plugin manifests in workflow run `31877375293` |
| Codex marketplace and install smoke | **PASS** | Codex CLI `0.146.0`; marketplace registration plus installation and enablement of all five packages in workflow run `31877375293` |
| CI-produced package reproducibility | **PASS** | artifact `9245097184`; all five CI ZIPs matched the locally generated ZIPs byte-for-byte |

## Release packages

| Package | SHA-256 |
|---|---|
| `engineering-foundation-core-0.2.0.zip` | `71a8051b210b1e9581d2b523c3b1e954948df828ac94199d3613e71a2bfb3503` |
| `engineering-foundation-laravel-0.2.0.zip` | `01845751accd1f3723fdc78c2eb7482fd312fcfaa7885b720fe68a1e32f8a11b` |
| `engineering-foundation-design-0.2.0.zip` | `92efe1d7ecc3e1e16a0eb4fbb7453191c2f2c1ef1dc833916db64a95a7f49b4b` |
| `engineering-foundation-cloud-0.2.0.zip` | `5518a3d4de0c7dfd6084f6c9d5a75442ea01020b64b4acbc4e51ca11948a0485` |
| `engineering-foundation-authoring-0.2.0.zip` | `eb4103ae32d770695e011ad2888a25d11c49ff562a2297b3a3c26e14036458bc` |

## Evidence boundary

Authenticated behavior campaigns for ChatGPT/Codex desktop, Codex CLI model sessions, Codex Cloud, Claude Code model sessions, and an Agent Plugins reference client remain `NOT_RUN`. The checked-in eval rows are synthetic scorer fixtures and report `NOT_QUALIFIED` by design. This release is therefore statically validated and provider-package validated, not represented as live-model-qualified.
