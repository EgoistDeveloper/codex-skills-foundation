#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
python3 scripts/check_python.py
python3 scripts/render_manifests.py --check
python3 scripts/validate_repository.py --strict
python3 -m unittest discover -s tests -v
python3 -m compileall -q scripts tests
python3 scripts/evidence_gate.py examples/completion-evidence.pass.json --contract examples/task-contract.static-validation.json
for fixture in examples/completion-evidence.fail.json examples/completion-evidence.partial.json; do
  if output="$(python3 scripts/evidence_gate.py "$fixture" 2>&1)"; then
    echo "ERROR: non-complete evidence fixture was accepted: $fixture" >&2
    exit 1
  else
    status=$?
    if [[ $status -ne 1 ]]; then
      printf '%s\n' "$output" >&2
      echo "ERROR: evidence gate failed unexpectedly with exit code $status: $fixture" >&2
      exit 1
    fi
    printf 'negative evidence fixture rejected: PASS (%s)\n' "$fixture"
  fi
done
python3 scripts/score_eval_runs.py evals/fixtures/sample-runs.jsonl --allow-synthetic
printf '%s\n' 'bootstrap: PASS'
