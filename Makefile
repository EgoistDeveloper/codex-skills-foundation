.PHONY: bootstrap validate render test package live-smoke live-negative-smoke

bootstrap:
	python scripts/bootstrap.py

validate:
	python scripts/validate_repository.py --strict

render:
	python scripts/render_manifests.py

test:
	python -m unittest discover -s tests -v

package:
	python scripts/package_plugins.py --output dist

live-smoke:
	python scripts/run_codex_live_smoke.py --confirm-live

live-negative-smoke:
	python scripts/run_codex_negative_smoke.py --confirm-live
