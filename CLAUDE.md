@AGENTS.md

# Claude Code adapter

- Treat `AGENTS.md` as canonical repository guidance.
- Use plugin skills on demand; do not preload every skill into a subagent.
- Prefer auto-discovery from each plugin's root `skills/` directory.
- Provider-specific frontmatter must not be added to portable skills unless the compatibility tradeoff is documented and tested.
