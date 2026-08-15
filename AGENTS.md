# Repository working agreement

## Authority

- This file is the repository-wide engineering contract.
- More specific guidance may narrow these rules for a directory.
- Provider adapters must not silently change portable skill behavior.

## Work method

1. Inspect the working tree, nearest instructions, and relevant existing patterns.
2. Define acceptance IDs and evidence before non-trivial implementation.
3. Make the smallest coherent change that satisfies the contract.
4. Default to one writing agent. Delegate only independent, bounded work.
5. Keep one writer per file. Reviewers and evidence auditors are report-only.
6. Run targeted checks first, then the broadest affordable relevant checks.
7. Do not claim a check passed unless it ran in the current workspace.
8. After acceptance and evidence pass, do not reopen work for speculative cleanup.

## Repository checks

```bash
python -m pip install -r requirements-dev.txt
python scripts/bootstrap.py
```

## Safety

- Do not add MCP servers, hooks, network calls, secrets, telemetry, global installers, or destructive commands without an explicit scoped decision and tests.
- Do not pin reusable agent profiles to a current model name unless a release-specific benchmark justifies it.
- Do not commit generated manifest drift. Update `catalog/plugins.json`, render, and review the diff.
- Treat static checks, provider validation, and live-model behavior evals as different evidence classes.
- Never label an unrun eval as passed.

## Review

Flag behavior that permits omitted acceptance criteria, stale command evidence, required `NOT_RUN`, overlapping write ownership, recursive delegation, post-success scope expansion, unsupported manifest fields, or provider paths that escape the plugin root.
