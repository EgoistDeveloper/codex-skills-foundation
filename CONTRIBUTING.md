# Contributing

A contribution must solve an observed failure mode, not merely add another attractive-sounding prompt.

## Required evidence

- State the behavior problem and a representative task.
- Capture a baseline run without the change when practical.
- Add or update activation and behavior eval cases.
- Keep the skill body concise and move optional detail to focused references.
- Run all repository checks.
- Record live provider qualification separately; static tests are not a substitute.

## Skill acceptance

A new skill is justified only when all are true:

1. The workflow is reused across projects.
2. Existing guidance cannot express it without becoming ambiguous or bloated.
3. Its trigger boundary can be tested.
4. Its outcome can be evaluated.
5. Its expected value exceeds its discovery and maintenance cost.

Prefer improving an existing skill over adding a near-duplicate.
