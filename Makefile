.PHONY: bootstrap validate render test package

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
