# Repository working agreement

## Authority

- This file is the repository-wide engineering contract.
- More specific `AGENTS.md` files may narrow these rules for their directory.
- Provider adapters must not silently change the portable workflow contract.

## Work method

1. Read the nearest guidance and inspect the working tree before editing.
2. Define acceptance criteria and evidence before implementation.
3. Use the smallest coherent diff that satisfies the task.
4. Default to one agent. Delegate only independent, read-heavy, or specialist work.
5. Keep one writer per file. Reviewers and verifiers are report-only unless explicitly assigned a fix.
6. Run targeted checks first, then the broadest affordable relevant checks.
7. Do not claim a check passed unless it ran in the current workspace.
8. After acceptance and evidence pass, do not reopen the task for speculative cleanup.

## Repository checks

```bash
python scripts/render_manifests.py --check
python scripts/validate_repository.py --strict
python -m unittest discover -s tests -v
python -m compileall -q scripts tests
```

## Safety

- Do not add MCP servers, hooks, network calls, secrets, global installers, or destructive commands without an explicit scoped decision and tests.
- Do not commit generated drift. Update `catalog/plugins.json`, run the renderer, and review the generated diff.
- Treat live-model evals separately from static validation. Never label an unrun eval as passed.
