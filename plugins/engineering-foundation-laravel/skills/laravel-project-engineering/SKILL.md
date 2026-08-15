---
name: laravel-project-engineering
description: Inspect and change an existing Laravel/PHP project using installed versions, local architecture, tests, database engine, frontend stack, and Laravel Boost when available. Use for Laravel features, fixes, migrations, queues, authorization, APIs, Inertia, Livewire, Blade, Pest, or PHPUnit. Do not use as generic framework advice detached from the repository.
---


# Laravel Project Engineering

## Preflight

Read the nearest repository guidance and inspect:

- `composer.json`, `composer.lock`, PHP and Laravel versions;
- database driver, migration conventions, and production/local differences;
- Pest/PHPUnit commands, Pint, static analysis, and CI lanes;
- Blade, Livewire, Inertia/Vue, API, queue, cache, and event boundaries;
- adjacent controllers, actions, requests, policies, resources, jobs, models, and tests;
- Laravel Boost installation and health.

When Boost is present, use its version-aware documentation and project tools. Treat it as current context, not permission to ignore code or tests. Do not copy volatile framework guidance into this reusable skill.

## Change protocol

- Match the repository's owning layer before introducing another abstraction.
- Validate at ingress and authorize the actual resource action.
- Preserve tenant, scope, policy, soft-delete, audit, transaction, and idempotency boundaries.
- Make Eloquent query shape explicit; use eager loading and pagination when evidence requires them.
- Diagnose N+1 and performance with query counts/plans before adding caches or indexes.
- Add an index only for a demonstrated query pattern and account for write cost.
- Use expand-and-contract for risky production schema changes; prove rollback or forward recovery.
- Keep route names, public URLs, redirects, canonical metadata, events, and client contracts compatible unless the task changes them explicitly.
- Give notifications and user feedback one owner; avoid duplicate server/client emission.

## Verification ladder

1. Focused Pest/PHPUnit regression test.
2. Related feature/unit tests and policy/authorization tests.
3. Database-specific integration, queue/event, route, and response-contract checks as relevant.
4. Frontend build/type checks for Inertia/Vue boundaries.
5. Pint/static analysis in the project's configured mode.
6. Required broader suite, query evidence, and migration review proportional to risk.
7. Final diff and working-tree inspection.

After acceptance passes, do not re-architect the change. See `references/preflight.md` for the compact repository survey.
