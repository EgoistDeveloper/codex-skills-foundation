#!/usr/bin/env python3
"""Validate manifests, skills, adapters, links, and deterministic eval fixtures."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import re
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "engineering-foundation"
SKILL_NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SEMVER_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$")
SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def read_json(path: Path, errors: list[str]) -> dict[str, Any] | None:
    if not path.is_file():
        errors.append(f"missing JSON file: {path.relative_to(ROOT)}")
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"invalid JSON {path.relative_to(ROOT)}: {exc}")
        return None
    if not isinstance(value, dict):
        errors.append(f"JSON root must be an object: {path.relative_to(ROOT)}")
        return None
    return value


def parse_frontmatter(path: Path, errors: list[str]) -> tuple[dict[str, str], str]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        errors.append(f"cannot read {path.relative_to(ROOT)}: {exc}")
        return {}, ""
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        errors.append(f"missing frontmatter: {path.relative_to(ROOT)}")
        return {}, text
    try:
        end = lines.index("---", 1)
    except ValueError:
        errors.append(f"unclosed frontmatter: {path.relative_to(ROOT)}")
        return {}, text

    data: dict[str, str] = {}
    for raw in lines[1:end]:
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if ":" not in raw:
            errors.append(f"unsupported frontmatter line in {path.relative_to(ROOT)}: {raw}")
            continue
        key, value = raw.split(":", 1)
        value = value.strip()
        if value.startswith('"') and value.endswith('"'):
            value = value[1:-1]
        data[key.strip()] = value
    return data, "\n".join(lines[end + 1 :]).strip()


def validate_manifests(errors: list[str]) -> None:
    portable = read_json(PLUGIN / "plugin.json", errors)
    codex = read_json(PLUGIN / ".codex-plugin" / "plugin.json", errors)
    claude = read_json(PLUGIN / ".claude-plugin" / "plugin.json", errors)
    codex_market = read_json(ROOT / ".agents/plugins/marketplace.json", errors)
    claude_market = read_json(ROOT / ".claude-plugin/marketplace.json", errors)
    if not all((portable, codex, claude, codex_market, claude_market)):
        return

    expected_name = "engineering-foundation"
    versions = {portable.get("version"), codex.get("version"), claude.get("version")}
    if portable.get("$schema") != "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json":
        errors.append("portable plugin schema must be Agent Plugins 1.0.0")
    for label, manifest in (("portable", portable), ("codex", codex), ("claude", claude)):
        if manifest.get("name") != expected_name:
            errors.append(f"{label} manifest name mismatch")
    if len(versions) != 1 or not SEMVER_RE.fullmatch(str(next(iter(versions)))):
        errors.append("plugin manifest versions must match strict semver")
    if codex.get("skills") not in {"skills", "./skills", "./skills/"}:
        errors.append("Codex manifest must expose ./skills/")
    if claude.get("skills") not in {"skills", "./skills", "./skills/"}:
        errors.append("Claude manifest must expose ./skills/")
    if claude.get("agents") not in {"agents", "./agents", "./agents/"}:
        errors.append("Claude manifest must expose ./agents/")

    codex_plugins = codex_market.get("plugins")
    if not isinstance(codex_plugins, list) or len(codex_plugins) != 1:
        errors.append("Codex marketplace must contain exactly one plugin")
    else:
        entry = codex_plugins[0]
        if not isinstance(entry, dict) or entry.get("name") != expected_name:
            errors.append("Codex marketplace plugin name mismatch")
        source = entry.get("source") if isinstance(entry, dict) else None
        path = source.get("path") if isinstance(source, dict) else None
        if path != "./plugins/engineering-foundation":
            errors.append("Codex marketplace source path mismatch")
        policy = entry.get("policy") if isinstance(entry, dict) else None
        if not isinstance(policy, dict) or policy.get("installation") != "AVAILABLE":
            errors.append("Codex marketplace installation policy must be AVAILABLE")

    claude_plugins = claude_market.get("plugins")
    if not isinstance(claude_plugins, list) or len(claude_plugins) != 1:
        errors.append("Claude marketplace must contain exactly one plugin")
    else:
        entry = claude_plugins[0]
        if not isinstance(entry, dict) or entry.get("name") != expected_name:
            errors.append("Claude marketplace plugin name mismatch")
        if isinstance(entry, dict) and entry.get("source") != "./plugins/engineering-foundation":
            errors.append("Claude marketplace source path mismatch")


def validate_skills(errors: list[str], warnings: list[str]) -> None:
    skills_root = PLUGIN / "skills"
    if not skills_root.is_dir():
        errors.append("missing skills directory")
        return

    descriptions: list[str] = []
    names: set[str] = set()
    for skill_dir in sorted(path for path in skills_root.iterdir() if path.is_dir()):
        skill_file = skill_dir / "SKILL.md"
        if not skill_file.is_file():
            errors.append(f"skill missing SKILL.md: {skill_dir.name}")
            continue
        frontmatter, body = parse_frontmatter(skill_file, errors)
        name = frontmatter.get("name", "")
        description = frontmatter.get("description", "")
        if name != skill_dir.name:
            errors.append(f"skill name mismatch: {skill_dir.name} != {name}")
        if not SKILL_NAME_RE.fullmatch(name):
            errors.append(f"invalid skill name: {name}")
        if name in names:
            errors.append(f"duplicate skill name: {name}")
        names.add(name)
        if not description or len(description) > 500:
            errors.append(f"skill description must be 1-500 characters: {name}")
        elif len(description) > 300:
            warnings.append(f"long skill description may consume index budget: {name}")
        descriptions.append(description)
        if len(body) < 120:
            errors.append(f"skill body too short: {name}")
        if "Stop condition" not in body and "Completion lock" not in body:
            errors.append(f"skill lacks an explicit stop condition: {name}")
        if ("[" + "TODO:") in skill_file.read_text(encoding="utf-8"):
            errors.append(f"skill contains TODO placeholder: {name}")

    if len(names) < 10:
        errors.append("foundation must contain at least ten bounded skills")
    if len(set(descriptions)) != len(descriptions):
        errors.append("skill descriptions must be unique")
    if sum(len(item) for item in descriptions) > 8000:
        errors.append("combined skill descriptions exceed the 8,000-character fallback budget")


def validate_agents(errors: list[str]) -> None:
    required = {"name", "description", "model", "color"}
    agents_root = PLUGIN / "agents"
    for path in sorted(agents_root.glob("*.md")):
        frontmatter, body = parse_frontmatter(path, errors)
        missing = required - set(frontmatter)
        if missing:
            errors.append(f"Claude agent {path.name} missing: {', '.join(sorted(missing))}")
        if "Use this agent when" not in frontmatter.get("description", ""):
            errors.append(f"Claude agent description lacks trigger: {path.name}")
        if "When to invoke" not in body:
            errors.append(f"Claude agent body lacks invocation section: {path.name}")
        if len(body) < 150:
            errors.append(f"Claude agent body too short: {path.name}")

    adapter_root = PLUGIN / "adapters" / "codex" / "agents"
    project_root = ROOT / ".codex" / "agents"
    adapter_names = {path.name for path in adapter_root.glob("*.toml")}
    project_names = {path.name for path in project_root.glob("*.toml")}
    if adapter_names != project_names:
        errors.append("Codex adapter and project agent file sets differ")
    for name in sorted(adapter_names & project_names):
        if (adapter_root / name).read_bytes() != (project_root / name).read_bytes():
            errors.append(f"Codex adapter drift: {name}")


def validate_links(errors: list[str]) -> None:
    link_re = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")
    for path in ROOT.rglob("*.md"):
        text = path.read_text(encoding="utf-8")
        for target in link_re.findall(text):
            target = target.strip()
            if not target or target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            clean = target.split("#", 1)[0]
            if not clean:
                continue
            resolved = (path.parent / clean).resolve()
            if not resolved.exists():
                errors.append(
                    f"broken local link in {path.relative_to(ROOT)}: {target}"
                )


def validate_security(errors: list[str]) -> None:
    for path in ROOT.rglob("*"):
        if not path.is_file() or ".git" in path.parts:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                errors.append(f"possible secret in {path.relative_to(ROOT)}")
        if ("[" + "TODO:") in text:
            errors.append(f"TODO placeholder in {path.relative_to(ROOT)}")
    if (PLUGIN / "mcp.json").exists() or (PLUGIN / ".mcp.json").exists():
        errors.append("v0.1 must not ship an MCP server configuration")


def validate_evals(errors: list[str]) -> None:
    router = load_module(
        "foundation_route_task",
        PLUGIN / "scripts" / "route_task.py",
    )
    gate = load_module(
        "foundation_evidence_gate",
        PLUGIN / "scripts" / "evidence_gate.py",
    )

    for path in sorted((ROOT / "evals" / "routing").glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        expected = payload.pop("expected_mode", None)
        actual = router.route_task(payload)["mode"]
        if actual != expected:
            errors.append(
                f"routing eval {path.name}: expected {expected}, got {actual}"
            )

    evidence_dir = ROOT / "evals" / "evidence"
    for path in sorted(evidence_dir.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        expected = payload.pop("expected_pass", None)
        actual = not gate.validate_packet(payload)
        if actual is not expected:
            errors.append(
                f"evidence eval {path.name}: expected {expected}, got {actual}"
            )


def validate_repository() -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    validate_manifests(errors)
    validate_skills(errors, warnings)
    validate_agents(errors)
    validate_links(errors)
    validate_security(errors)
    validate_evals(errors)
    return errors, warnings


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    errors, warnings = validate_repository()
    result = {
        "ok": not errors and (not args.strict or not warnings),
        "errors": errors,
        "warnings": warnings,
    }
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["ok"] else 1)


if __name__ == "__main__":
    main()
