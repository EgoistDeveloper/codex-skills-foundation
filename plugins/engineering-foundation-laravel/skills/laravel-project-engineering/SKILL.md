---
name: laravel-project-engineering
description: Inspect and change an existing Laravel/PHP project using its installed versions, local architecture, tests, database engine, frontend stack, and Laravel Boost when available. Use for Laravel features, fixes, migrations, queues, authorization, APIs, Inertia, Livewire, Blade, Pest, or PHPUnit. Do not use as generic framework advice detached from the repository.
license: MIT
metadata:
  author: EgoistDeveloper
  version: "0.2.0"
---

# Laravel Project Engineering

## Preflight

Read the nearest repository guidance and inspect:

- `composer.json` and `composer.lock`;
- PHP and Laravel versions;
- database driver and migration conventions;
- test framework and commands;
- Pint/static-analysis configuration;
- Blade, Livewire, Inertia/Vue, or API boundaries;
- adjacent domain patterns;
- Laravel Boost installation and health.

When Boost is present, use its version-aware documentation and project tools. Treat it as current context, not as permission to ignore the codebase or tests. Do not copy volatile framework guidance into this skill.

## Change protocol

- Put validation, authorization, transactions, events, queues, and side effects in the repository's established owning layer.
- Preserve tenant, policy, scope, soft-delete, and audit boundaries.
- Use explicit eager loading and pagination when query shape requires them.
- Diagnose N+1 and performance with query evidence before adding caches or indexes.
- Add an index only for a demonstrated query pattern and consider write cost.
- Use expand-and-contract for risky production schema changes.
- Keep route names, URLs, redirects, and client contracts backward compatible unless the task explicitly changes them.
- Ensure user feedback has one owner; avoid duplicate controller/component notifications.

## Verification

Run the narrowest relevant test first, then broader checks proportional to risk. Typical evidence may include:

- focused Pest/PHPUnit tests;
- policy/authorization tests;
- database-specific integration tests;
- queue/event assertions;
- route and response-contract checks;
- frontend build/type checks;
- Pint/static analysis;
- query count, SQL plan, or migration rollback evidence.

After acceptance passes, do not perform an unrelated architecture rewrite.
