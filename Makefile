.PHONY: bootstrap validate render test package live-smoke live-negative-smoke live-repeatability live-bounded-delegation

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
	python scripts/run_codex_positive_smoke_isolated.py --confirm-live

live-negative-smoke:
	python scripts/run_codex_negative_smoke_v4.py --confirm-live

live-repeatability:
	python scripts/run_codex_core_repeatability.py --confirm-live --repetitions 3

live-bounded-delegation:
	python scripts/run_codex_bounded_delegation_smoke.py --confirm-live
