# Contributing

1. Create a focused branch and preserve unrelated work.
2. Define acceptance IDs and evidence for behavior changes.
3. Edit `catalog/plugins.json` for shared metadata, then run `python scripts/render_manifests.py`.
4. Keep portable `SKILL.md` frontmatter to `name` and `description`; put Codex display metadata in `agents/openai.yaml`.
5. Add positive and negative activation cases when a trigger changes.
6. Update schemas and regression tests when evidence or eval contracts change.
7. Install pinned development dependencies and run `python scripts/bootstrap.py` on the final tree.
8. Review the complete diff, generated manifests, package archives, and remaining risks.

A new skill must solve a repeated, independently triggerable capability. Prefer a focused reference when material belongs to an existing skill. Do not copy third-party prompt bodies; record provenance and synthesize original instructions.

Live provider results belong under ignored `evals/runs/` and must be redacted before sharing. Static success must not be relabeled as live-model qualification merely because release notes look lonely.
