---
name: laravel-engineering
description: Implement or review Laravel and PHP work using the project's actual versions, conventions, authorization, database behavior, tests, routes, and performance evidence. Use for Laravel code; do not impose generic architecture.
---

# Laravel Engineering

## Discover first

Inspect:

- `composer.json` and `composer.lock`;
- PHP and Laravel versions;
- installed first-party and analysis packages;
- Blade, Livewire, Inertia/Vue, API, queue, cache, and database choices;
- nearby controllers, actions, requests, policies, resources, jobs, models, and tests;
- Laravel Boost availability and project guidance.

Use version-matched official documentation for uncertain framework behavior.

## Implementation rules

- Match the project's existing architecture before adding a layer.
- Use Form Requests, policies/gates, resources, jobs, transactions, or events when the actual boundary warrants them.
- Validate at ingress and authorize the resource action.
- Keep Eloquent queries explicit; prevent N+1 behavior and accidental unbounded loads.
- Add indexes only from real query patterns and migration safety analysis.
- Use expand-and-contract for risky schema changes.
- Preserve queue idempotency and transaction boundaries.
- Keep notifications/toasts owned by one layer; do not emit duplicates from controller and client.
- Public URLs should express the domain, not implementation nouns. Avoid unnecessary `/urun`, `/kategori`, or equivalent prefixes when canonical, collision-safe routes can be cleaner.
- Maintain backward-compatible redirects and canonical metadata when changing public routes.
- Measure admin or query performance before caching or rewriting.

## Verification ladder

1. targeted test;
2. related feature/unit tests;
3. static analysis or type checks configured by the project;
4. Pint/formatter in the project's chosen mode;
5. full required suite;
6. database-specific lane when behavior differs from SQLite;
7. final diff and migration review.

## Completion lock

Do not re-architect a passing Laravel change after verification. Reopen only for failed evidence, missed behavior, concrete framework/security/performance finding, or user scope change.

See `references/laravel-checklist.md`.
