# Laravel checklist

## HTTP and domain

- Route names, model binding, canonical URL, redirects, locale, and collision analysis.
- Request validation and authorization order.
- Resource serialization and error semantics.
- No mass-assignment or ownership bypass.

## Database

- Transaction includes all consistency-critical writes.
- Locking and idempotency considered for concurrent operations.
- Migration works on the production database engine.
- Rollback is safe or explicitly documented.
- Query count and selected columns are intentional.

## Async work

- Jobs are serializable and retry-safe.
- Unknown commit/timeout behavior is handled where external side effects exist.
- Events/listeners do not duplicate synchronous side effects.
- Notification delivery has a single owner.

## Frontend boundary

- Inertia/Livewire/Vue state follows existing project conventions.
- Validation errors, loading, empty, success, and failure states are represented.
- Flash/toast messages are not emitted twice.
- Forms preserve focus and accessible feedback.

## Tests

- Behavior is asserted through public boundaries where possible.
- Authorization denial and validation failure are tested.
- Regression test fails without the fix.
- Database engine differences are not hidden by SQLite-only tests.
