# Safe comparison with Pull Request #1

This candidate was produced without read access to Pull Request #1. Do not replace the PR branch wholesale and do not assume the earlier claim summary exactly describes its current files.

## Recommended sequence

1. Fetch the actual PR branch locally and record its exact commit SHA.
2. Create a comparison branch from that SHA.
3. Unpack this candidate outside the repository or add it as a temporary sibling worktree.
4. Compare by concern, not by file count:
   - package and manifest model;
   - skill inventory and trigger boundaries;
   - goal / plan / milestone / handoff contract;
   - orchestration limits and provider-agent adapters;
   - completion evidence and review gates;
   - live eval records and scoring;
   - Laravel and design modularity;
   - security and installation surfaces.
5. Preserve any PR implementation that has stronger evidence than this candidate.
6. Apply changes in small commits. Suggested order:
   - generated manifests and validators;
   - marketplace installation/authentication policy;
   - completion contract and evidence-gate semantics;
   - eval identity, artifact checks, and anti-false-qualification changes;
   - core skill consolidation;
   - optional Laravel/design package split;
   - optional provider-agent profiles;
   - documentation and qualification matrix.
7. Run both repositories' checks after each commit.
8. Run live A/B qualification before merging.

## High-priority semantic comparisons

### Marketplace manifests

Confirm OpenAI marketplace entries contain valid `policy.installation`, `policy.authentication`, category, and paths. Confirm Claude manifests declare their schema and pass the current strict provider validator. Do not infer that one provider's accepted JSON is valid for the other.

### Completion evidence

A gate must reject:

- `PARTIAL` or `BLOCKED` presented as complete;
- any required `FAIL` or `NOT_RUN`;
- empty evidence;
- duplicate criteria;
- a matrix that silently omits task-contract acceptance criteria.

The parser still cannot establish that an external command truly ran. Preserve that limitation in output instead of upgrading structured confidence into reality.

### Eval scorer

A scorer must reject missing candidate/baseline rows, type confusion such as string `"false"`, duplicate run identities, mismatched repetitions, mixed synthetic/live rows, missing live artifacts, and candidate regressions. A synthetic fixture must never produce a release-qualified status. A passing subset must report coverage as unassessed until the entire qualification matrix is accounted for.

### Agent profiles

Provider-specific profiles are adapters, not portable behavior. Check them in only when project-scoped installation is explicit, conflicts are preserved, models are not unnecessarily pinned, read-only boundaries work at runtime, and nested delegation is actually blocked.

## Do not infer equivalence

Matching names do not mean matching behavior. Static route fixtures do not prove agent routing. Unit tests for an evidence JSON parser do not prove the model supplies truthful evidence. A real comparison must inspect traces, diffs, commands, artifacts, repeated outcomes, and the client versions that produced them.
