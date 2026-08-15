# Release qualification matrix

A release is not qualified because repository validation is green or because the scorer accepted a convenient subset of rows.

| Surface | Static install | Positive trigger | Negative trigger | Behavior cases | Safety | Evidence | Status |
|---|---:|---:|---:|---:|---:|---:|---|
| ChatGPT/Codex desktop app | required | required | required | required | required | required | NOT_RUN |
| Codex CLI | required | required | required | required | required | required | NOT_RUN |
| Codex cloud | required | required | required | required | required | required | NOT_RUN |
| Claude Code CLI/desktop surface | required | required | required | required | required | required | NOT_RUN |
| Agent Plugins reference client | required | required | required | selected | required | required | NOT_RUN |

## Optional-agent adapter checks

These are separate from portable plugin qualification:

| Adapter | Parse/discover | Read-only runtime | No nested delegation | Representative invocation | Status |
|---|---:|---:|---:|---:|---|
| Codex `.codex/agents/*.toml` | required | required | required | required | NOT_RUN |
| Claude `.claude/agents/*.md` | required | required | required | required | NOT_RUN |

## Release-critical cases

- tiny task skips plan and subagents;
- post-pass refactor does not occur;
- required failed or unrun checks keep completion partial;
- completion evidence covers every task-contract acceptance item;
- multi-agent fan-out remains bounded;
- review suppresses unsupported style noise;
- handoff is compact and verifiable;
- Laravel uses repository versions and measured evidence;
- design chooses one direction and verifies rendered states.

## Evidence record

Record:

- campaign ID;
- provider, client, client version, authentication mode, operating system, and execution surface;
- model/capability tier and relevant runtime settings;
- package commit and case revision;
- baseline, previous, and candidate repetitions;
- redacted traces, artifacts, diffs, commands, screenshots, and exit codes;
- token/tool/duration/subagent/churn metrics;
- grader identity/version where subjective grading is used.

A matrix cell changes from `NOT_RUN` only when its evidence artifact exists and is reviewable. A summary sentence does not qualify a surface. Apparently this has to be written down.
