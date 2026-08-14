#!/usr/bin/env python3
"""Run deterministic repository validation and unit tests."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys


def run(command: list[str]) -> None:
    print("+", " ".join(command), flush=True)
    subprocess.run(command, check=True)


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    run([sys.executable, str(root / "scripts" / "validate_repository.py"), "--strict"])
    run([sys.executable, "-m", "unittest", "discover", "-s", str(root / "tests"), "-v"])


if __name__ == "__main__":
    main()
