#!/usr/bin/env python3
"""Deterministically route an engineering task to a bounded agent topology."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

RISK_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}
UNCERTAINTY_ORDER = {"low": 0, "medium": 1, "high": 2}


class ProfileError(ValueError):
    pass


def _bool(profile: dict[str, Any], key: str, default: bool = False) -> bool:
    value = profile.get(key, default)
    if not isinstance(value, bool):
        raise ProfileError(f"`{key}` must be a boolean")
    return value


def _int(profile: dict[str, Any], key: str, default: int = 0) -> int:
    value = profile.get(key, default)
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ProfileError(f"`{key}` must be a non-negative integer")
    return value


def _enum(
    profile: dict[str, Any],
    key: str,
    allowed: dict[str, int],
    default: str,
) -> str:
    value = profile.get(key, default)
    if not isinstance(value, str) or value not in allowed:
        raise ProfileError(f"`{key}` must be one of: {', '.join(allowed)}")
    return value


def _domains(profile: dict[str, Any]) -> list[str]:
    value = profile.get("specialist_domains", [])
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item.strip() for item in value
    ):
        raise ProfileError("`specialist_domains` must be an array of non-empty strings")
    return list(dict.fromkeys(item.strip() for item in value))


def route_task(profile: dict[str, Any]) -> dict[str, Any]:
    risk = _enum(profile, "risk", RISK_ORDER, "medium")
    uncertainty = _enum(profile, "uncertainty", UNCERTAINTY_ORDER, "medium")
    estimated_files = _int(profile, "estimated_files", 1)
    workstreams = _int(profile, "independent_workstreams", 1)
    shared_write = _bool(profile, "shared_write_surface")
    exclusive_writes = _bool(profile, "exclusive_write_ownership")
    read_heavy = _bool(profile, "read_heavy")
    external_research = _bool(profile, "external_research")
    visual_validation = _bool(profile, "visual_validation")
    irreversible = _bool(profile, "irreversible")
    no_subagents = _bool(profile, "explicit_no_subagents")
    domains = _domains(profile)

    reasons: list[str] = []
    specialists: list[str] = []

    if external_research:
        specialists.append("researcher")
        reasons.append("current or external evidence is required")
    if visual_validation:
        specialists.append("designer")
        reasons.append("the task needs independent visual-system analysis")
    if uncertainty == "high" or read_heavy:
        specialists.append("explorer")
        reasons.append("read-heavy or high-uncertainty exploration should stay out of the main context")
    if risk in {"high", "critical"} or irreversible:
        specialists.extend(["planner", "reviewer", "verifier"])
        reasons.append("risk requires fresh planning and verification")

    domain_specialist_needed = (
        RISK_ORDER[risk] >= RISK_ORDER["high"]
        or UNCERTAINTY_ORDER[uncertainty] >= UNCERTAINTY_ORDER["high"]
        or estimated_files >= 8
    )
    if domain_specialist_needed:
        for domain in domains:
            if domain == "laravel":
                specialists.append("laravel-reviewer")
            elif domain not in {"general", "ui", "research"}:
                specialists.append(f"{domain}-specialist")

    specialists = list(dict.fromkeys(specialists))

    if no_subagents:
        mode = "single-agent"
        specialists = []
        reasons = ["the user explicitly disabled subagents"]
    else:
        safe_parallel_reads = workstreams >= 2 and read_heavy and not shared_write
        safe_parallel_writes = (
            workstreams >= 2
            and exclusive_writes
            and not shared_write
            and RISK_ORDER[risk] <= RISK_ORDER["medium"]
        )
        if safe_parallel_reads or safe_parallel_writes:
            mode = "bounded-multi-agent"
            reasons.append("independent workstreams have non-overlapping ownership")
        elif specialists:
            mode = "single-agent-with-specialists"
        else:
            mode = "single-agent"
            reasons.append("the work is small or coupled; one writer is safer and cheaper")

    if mode == "bounded-multi-agent":
        max_specialists = min(3, max(2, workstreams))
    elif mode == "single-agent-with-specialists":
        max_specialists = min(3, max(1, len(specialists)))
    else:
        max_specialists = 0

    specialists = specialists[:max_specialists]

    complexity = (
        estimated_files
        + (2 * workstreams)
        + (3 * RISK_ORDER[risk])
        + (2 * UNCERTAINTY_ORDER[uncertainty])
        + (3 if external_research else 0)
        + (3 if visual_validation else 0)
        + (4 if irreversible else 0)
    )
    budget = "compact" if complexity <= 8 else "standard" if complexity <= 18 else "expanded"

    return {
        "mode": mode,
        "primary_writer": True,
        "specialists": specialists,
        "max_concurrent_specialists": max_specialists,
        "delegation_depth": 1 if max_specialists else 0,
        "context_budget": budget,
        "reasons": reasons,
        "completion_owner": "primary",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("profile", type=Path)
    args = parser.parse_args()

    try:
        payload = json.loads(args.profile.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ProfileError("profile must contain a JSON object")
        result = route_task(payload)
    except (OSError, json.JSONDecodeError, ProfileError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        raise SystemExit(2) from exc

    print(json.dumps({"ok": True, **result}, indent=2))


if __name__ == "__main__":
    main()
