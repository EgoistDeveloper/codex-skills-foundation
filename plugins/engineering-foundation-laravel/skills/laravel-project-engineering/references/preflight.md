# Laravel preflight checklist

Use only commands available in the repository. Examples, not mandates:

```bash
php -v
composer show laravel/framework --locked
php artisan about
php artisan route:list
php artisan test --filter=<target>
./vendor/bin/pint --test
./vendor/bin/phpstan analyse
```

Inspect `composer.lock` rather than assuming the latest release. Confirm the actual database in runtime/test configuration before writing engine-specific SQL. Never expose secrets from `.env` in logs or reports.
