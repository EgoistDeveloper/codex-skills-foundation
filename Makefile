.PHONY: validate render test

validate:
	./scripts/bootstrap.sh

render:
	python3 scripts/render_manifests.py

test:
	python3 -m unittest discover -s tests -v
