# Task contract template

```yaml
task_id: task-slug
objective: Observable outcome
context:
  - Verified repository fact
assumptions:
  - Narrow assumption required to proceed
acceptance:
  - id: A1
    criterion: Observable criterion
    required: true
    evidence_hint: Command, runtime observation, or artifact
non_goals:
  - Explicitly excluded adjacent work
constraints:
  - Compatibility, security, data, tooling, or permission boundary
risk:
  level: medium
  summary: Why this risk level applies
reopen_conditions:
  - Failed evidence
  - Changed requirement
```
