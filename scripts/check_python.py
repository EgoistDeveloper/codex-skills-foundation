#!/usr/bin/env python3
"""Fail with a clear message when the repository's Python floor is not met."""
from __future__ import annotations

import sys

MINIMUM = (3, 11)


def main() -> int:
    if sys.version_info < MINIMUM:
        current = ".".join(map(str, sys.version_info[:3]))
        required = ".".join(map(str, MINIMUM))
        print(f"ERROR: Python {required}+ is required; found {current}.", file=sys.stderr)
        return 1
    print(f"python version check: PASS ({sys.version.split()[0]})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
