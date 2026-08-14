# Plugin package rules

- Immediate children of `skills/` are public workflow names. Renaming one is a breaking change.
- A skill folder name must match its frontmatter `name`.
- Skill descriptions must say when the skill applies and avoid overlapping another skill without a clear routing distinction.
- Keep the common path in `SKILL.md`; move deep checklists into `references/`.
- Every skill must define a stop condition, evidence expectations, and what it must not do.
- Specialist agents are read-only by default. The primary agent owns all integration writes.
- Do not add platform-specific syntax to the portable instructions unless it is inside a clearly labeled adapter section.
