#!/usr/bin/env python3
"""Compatibility entry point for Core's canonical packaged evidence gate."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType


CANONICAL_GATE = (
    Path(__file__).resolve().parents[1]
    / "plugins"
    / "engineering-foundation-core"
    / "skills"
    / "verify-before-completion"
    / "scripts"
    / "evidence_gate.py"
)


def _load_canonical_gate() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "engineering_foundation_core_evidence_gate",
        CANONICAL_GATE,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load canonical evidence gate: {CANONICAL_GATE}")
    implementation = importlib.util.module_from_spec(spec)
    previous_bytecode_setting = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(implementation)
    finally:
        sys.dont_write_bytecode = previous_bytecode_setting
    return implementation


_IMPLEMENTATION = _load_canonical_gate()
validate_contract = _IMPLEMENTATION.validate_contract
validate = _IMPLEMENTATION.validate
load_json = _IMPLEMENTATION.load_json


def main() -> int:
    return _IMPLEMENTATION.main()


if __name__ == "__main__":
    sys.exit(main())
