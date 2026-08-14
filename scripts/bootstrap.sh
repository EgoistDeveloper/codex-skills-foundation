#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

python3 scripts/validate_repository.py --strict
python3 -m unittest discover -s tests -v
python3 -m compileall -q scripts plugins/engineering-foundation/scripts tests

echo "Foundation validation passed."
