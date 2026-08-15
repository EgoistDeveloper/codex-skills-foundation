# Optional project agent profiles

The portable `bounded-orchestration` skill works with host-native subagents and does not require permanent custom roles. Three narrow project profiles are included for teams that repeatedly need the same read-only work:

- `foundation-explorer`: maps an execution path;
- `foundation-reviewer`: reports material diff risks;
- `foundation-evidence-auditor`: audits completion evidence.

They deliberately exclude an implementer. The parent agent or the host's built-in worker owns implementation and integration. This avoids two agents rewriting the same files while congratulating each other for parallelism.

## Install into one project

Dry run first:

```powershell
python scripts/install_agent_profiles.py --provider codex --target D:\path\to\project
python scripts/install_agent_profiles.py --provider claude --target D:\path\to\project
```

Apply after reviewing the destinations:

```powershell
python scripts/install_agent_profiles.py --provider codex --target D:\path\to\project --apply
python scripts/install_agent_profiles.py --provider claude --target D:\path\to\project --apply
```

Codex profiles install under `.codex/agents/`. Claude profiles install under `.claude/agents/`. Existing conflicting files are never overwritten unless `--force` is explicitly supplied.

## Runtime policy

- Keep the parent as contract, integration, and completion owner.
- Use at most three concurrent workers even when a host allows more.
- Keep delegation depth at one; the supplied Claude profiles deny the `Agent` tool, and Codex profiles instruct workers not to delegate.
- Profiles pin no model. Select capability and cost at runtime rather than fossilizing today's product names in a reusable repository.
- Read-only profiles inspect and report. The parent runs any validation command that may mutate caches or generated files, then gives the resulting evidence to the auditor.

Custom-agent formats are provider-specific and can evolve. Treat profile installation as an adapter qualification step, not as part of the portable Agent Skills contract.
