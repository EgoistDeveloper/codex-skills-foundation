#!/usr/bin/env python3
"""Run the complete deterministic validation and packaging pipeline."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


def run(args: list[str], *, expected: set[int] | None = None) -> None:
    expected_codes = expected or {0}
    print("+", " ".join(args), flush=True)
    result = subprocess.run(args, cwd=ROOT, text=True)
    if result.returncode not in expected_codes:
        raise SystemExit(
            f"command returned {result.returncode}; expected {sorted(expected_codes)}: {' '.join(args)}"
        )


def main() -> int:
    run([PYTHON, "scripts/check_python.py"])
    run([PYTHON, "scripts/render_manifests.py", "--check"])
    run([PYTHON, "scripts/validate_repository.py", "--strict"])
    run([PYTHON, "-m", "unittest", "discover", "-s", "tests", "-v"])
    run([PYTHON, "-m", "compileall", "-q", "scripts", "tests"])
    run(
        [
            PYTHON,
            "scripts/evidence_gate.py",
            "examples/completion-evidence.pass.json",
            "--contract",
            "examples/task-contract.static-validation.json",
        ]
    )
    for fixture in (
        "examples/completion-evidence.fail.json",
        "examples/completion-evidence.partial.json",
    ):
        run([PYTHON, "scripts/evidence_gate.py", fixture], expected={1})
    run(
        [
            PYTHON,
            "scripts/score_eval_runs.py",
            "evals/fixtures/sample-runs.jsonl",
            "--allow-synthetic",
            "--require-previous",
        ]
    )
    run([PYTHON, "scripts/package_plugins.py", "--output", "dist", "--check"])
    print("bootstrap: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
