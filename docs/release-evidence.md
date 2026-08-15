# v0.2.0 release evidence

This file is updated from the final GitHub revision after CI completes.

## Source

- release version: `0.2.0`
- branch: `feat/agent-skills-foundation-v2`
- source commit: `PENDING_FINAL_COMMIT`

## Deterministic validation

| Check | Result | Evidence |
|---|---|---|
| local Linux bootstrap | PASS | 39 unit tests, strict validator, schemas/YAML/links/security, evidence negatives, scorer self-test, deterministic ZIPs |
| GitHub Linux bootstrap | PENDING | final workflow run |
| GitHub Windows bootstrap | PENDING | final workflow run |
| Claude strict plugin validation | PENDING | final provider workflow run |
| Codex marketplace/install smoke | PENDING | final provider workflow run |

## Live model behavior

No authenticated Codex, Codex Cloud, ChatGPT desktop, or Claude Code behavior campaign is represented as completed by this release evidence file. The checked-in eval fixture is synthetic and reports `NOT_QUALIFIED` by design.
