# Contributing

1. Create a focused branch from `main`.
2. Keep each change traceable to one behavior or compatibility requirement.
3. Update or add a deterministic eval case for behavior changes.
4. Run the repository validator and unit tests.
5. Document external sources with an exact date and, for Git repositories, a commit SHA when practical.
6. Open a pull request; do not merge based only on an agent's completion claim.

New skills must:

- use a stable kebab-case folder and matching `name`;
- provide a precise trigger description;
- keep the common path in `SKILL.md`;
- move large references to `references/`;
- define a stop condition and verification evidence;
- avoid provider-specific assumptions in the portable core;
- include at least one positive and one negative eval scenario when routing behavior changes.

Third-party text may not be copied unless licensing and attribution are explicit. Prefer original synthesis.
