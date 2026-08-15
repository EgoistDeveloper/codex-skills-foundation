#!/usr/bin/env python3
"""Dependency-free repository validator for manifests, skills, examples, and evals."""
from __future__ import annotations

import argparse
import json
import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PORTABLE_SCHEMA = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
PORTABLE_FIELDS = {"$schema", "name", "version", "description", "author", "homepage", "repository", "license", "keywords", "extensions"}
NAME_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$")
PLUGIN_NAME_RE = re.compile(r"^(?!.*(?:--|\.\.))[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?$")


class Report:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def error(self, message: str) -> None:
        self.errors.append(message)

    def warn(self, message: str) -> None:
        self.warnings.append(message)


def load_json(path: Path, report: Report):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        report.error(f"missing JSON: {path.relative_to(ROOT)}")
    except json.JSONDecodeError as exc:
        report.error(f"invalid JSON {path.relative_to(ROOT)}: {exc}")
    return None


def parse_frontmatter(path: Path, report: Report) -> tuple[dict[str, object], str]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        report.error(f"missing YAML frontmatter: {path.relative_to(ROOT)}")
        return {}, text
    try:
        end = lines.index("---", 1)
    except ValueError:
        report.error(f"unterminated YAML frontmatter: {path.relative_to(ROOT)}")
        return {}, text
    data: dict[str, object] = {}
    current_map: dict[str, str] | None = None
    current_key: str | None = None
    for raw in lines[1:end]:
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if raw.startswith("  ") and current_map is not None and ":" in raw:
            key, value = raw.strip().split(":", 1)
            current_map[key.strip()] = value.strip().strip('"\'')
            continue
        if ":" not in raw:
            report.error(f"unsupported frontmatter line in {path.relative_to(ROOT)}: {raw}")
            continue
        key, value = raw.split(":", 1)
        key, value = key.strip(), value.strip()
        if value == "":
            current_map = {}
            current_key = key
            data[key] = current_map
        else:
            data[key] = value.strip('"\'')
            current_map = None
            current_key = None
    return data, "\n".join(lines[end + 1:]).strip()


def validate_plugin(root: Path, report: Report) -> None:
    portable = load_json(root / "plugin.json", report)
    codex = load_json(root / ".codex-plugin" / "plugin.json", report)
    claude = load_json(root / ".claude-plugin" / "plugin.json", report)
    if not all(isinstance(x, dict) for x in (portable, codex, claude)):
        return
    name = root.name
    unknown = set(portable) - PORTABLE_FIELDS
    if unknown:
        report.error(f"{name}: unknown Agent Plugins fields: {sorted(unknown)}")
    if portable.get("$schema") != PORTABLE_SCHEMA:
        report.error(f"{name}: incorrect portable $schema")
    if portable.get("name") != name or not PLUGIN_NAME_RE.fullmatch(name):
        report.error(f"{name}: invalid or mismatched portable name")
    for adapter_name, manifest in (("codex", codex), ("claude", claude)):
        if manifest.get("name") != name:
            report.error(f"{name}: {adapter_name} manifest name mismatch")
        if manifest.get("version") != portable.get("version"):
            report.error(f"{name}: {adapter_name} version drift")
    if claude.get("$schema") != "https://json.schemastore.org/claude-code-plugin-manifest.json":
        report.error(f"{name}: Claude manifest must declare the canonical editor schema")
    if not isinstance(claude.get("displayName"), str) or not claude["displayName"].strip():
        report.error(f"{name}: Claude displayName missing")
    if codex.get("skills") != "./skills/":
        report.error(f"{name}: Codex skills path must be ./skills/")
    if "skills" in claude:
        report.warn(f"{name}: Claude manifest can rely on skills/ auto-discovery; explicit field needs runtime qualification")
    if (root / "mcp.json").exists() or (root / ".mcp.json").exists():
        report.warn(f"{name}: MCP configuration present; run security admission review")
    if (root / "hooks").exists() or (root / "hooks.json").exists():
        report.warn(f"{name}: hooks present; run security admission review")

    skills_dir = root / "skills"
    skills = sorted(skills_dir.glob("*/SKILL.md"))
    if not skills:
        report.error(f"{name}: no skills found")
    for skill_path in skills:
        meta, body = parse_frontmatter(skill_path, report)
        skill_name = skill_path.parent.name
        if meta.get("name") != skill_name:
            report.error(f"{skill_path.relative_to(ROOT)}: name must match directory")
        if not NAME_RE.fullmatch(skill_name) or "--" in skill_name:
            report.error(f"{skill_path.relative_to(ROOT)}: invalid skill name")
        description = meta.get("description")
        if not isinstance(description, str) or not (1 <= len(description) <= 1024):
            report.error(f"{skill_path.relative_to(ROOT)}: description must be 1..1024 chars")
        elif "Use " not in description or "Do not " not in description:
            report.warn(f"{skill_path.relative_to(ROOT)}: description should state positive and negative trigger boundaries")
        if "allowed-tools" in meta:
            report.error(f"{skill_path.relative_to(ROOT)}: portable skills must not pre-approve tools")
        if not body:
            report.error(f"{skill_path.relative_to(ROOT)}: empty body")
        if len(body.splitlines()) > 500:
            report.error(f"{skill_path.relative_to(ROOT)}: body exceeds 500 lines")
        for ref in skill_path.parent.glob("references/**/*.md"):
            if len(ref.relative_to(skill_path.parent / "references").parts) > 1:
                report.warn(f"{ref.relative_to(ROOT)}: keep references one level deep")


def validate_marketplaces(catalog: dict, report: Report) -> None:
    expected = {p["name"]: p for p in catalog["plugins"]}
    openai = load_json(ROOT / ".agents/plugins/marketplace.json", report)
    claude = load_json(ROOT / ".claude-plugin/marketplace.json", report)
    if isinstance(openai, dict):
        entries = {p.get("name"): p for p in openai.get("plugins", []) if isinstance(p, dict)}
        if set(entries) != set(expected):
            report.error("OpenAI marketplace plugin set differs from catalog")
        for name, entry in entries.items():
            source = entry.get("source", {})
            path = source.get("path") if isinstance(source, dict) else None
            if name in expected and path != f"./{expected[name]['path']}":
                report.error(f"OpenAI marketplace path mismatch: {name}")
            if isinstance(path, str) and not (ROOT / path.removeprefix("./")).is_dir():
                report.error(f"OpenAI marketplace path does not exist: {path}")
            policy = entry.get("policy")
            if not isinstance(policy, dict):
                report.error(f"OpenAI marketplace policy missing: {name}")
            else:
                installation = policy.get("installation")
                authentication = policy.get("authentication")
                if installation not in {"AVAILABLE", "INSTALLED_BY_DEFAULT", "NOT_AVAILABLE"}:
                    report.error(f"OpenAI marketplace invalid installation policy: {name}")
                if authentication not in {"ON_INSTALL", "ON_FIRST_USE"}:
                    report.error(f"OpenAI marketplace invalid authentication policy: {name}")
            if not isinstance(entry.get("category"), str) or not entry.get("category"):
                report.error(f"OpenAI marketplace category missing: {name}")
    if isinstance(claude, dict):
        entries = {p.get("name"): p for p in claude.get("plugins", []) if isinstance(p, dict)}
        if set(entries) != set(expected):
            report.error("Claude marketplace plugin set differs from catalog")
        for name, entry in entries.items():
            path = entry.get("source")
            if name in expected and path != f"./{expected[name]['path']}":
                report.error(f"Claude marketplace path mismatch: {name}")
            if isinstance(path, str) and not (ROOT / path.removeprefix("./")).is_dir():
                report.error(f"Claude marketplace path does not exist: {path}")


def validate_eval_cases(catalog: dict, report: Report) -> set[str]:
    packages = {p["name"] for p in catalog["plugins"]}
    all_skills = {p.parent.name for p in ROOT.glob("plugins/*/skills/*/SKILL.md")}
    cases = list((ROOT / "evals/cases").glob("*.json"))
    if len(cases) < 10:
        report.error("at least ten eval cases are required")
    seen: set[str] = set()
    for path in cases:
        case = load_json(path, report)
        if not isinstance(case, dict):
            continue
        required = {"id", "revision", "package", "prompt", "expected_activation", "behavior_assertions", "risk"}
        missing = required - set(case)
        if missing:
            report.error(f"{path.relative_to(ROOT)}: missing {sorted(missing)}")
            continue
        if case["id"] != path.stem or case["id"] in seen:
            report.error(f"{path.relative_to(ROOT)}: id mismatch or duplicate")
        if type(case.get("revision")) is not int or case["revision"] < 1:
            report.error(f"{path.relative_to(ROOT)}: revision must be a positive integer")
        seen.add(case["id"])
        if case["package"] not in packages:
            report.error(f"{path.relative_to(ROOT)}: unknown package")
        for skill in case.get("expected_activation", []) + case.get("forbidden_activation", []):
            if skill not in all_skills:
                report.error(f"{path.relative_to(ROOT)}: unknown skill {skill}")
        if not case["behavior_assertions"]:
            report.error(f"{path.relative_to(ROOT)}: no behavior assertions")
    return seen


def validate_eval_fixture(case_ids: set[str], report: Report) -> None:
    path = ROOT / "evals/fixtures/sample-runs.jsonl"
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        report.error("missing evals/fixtures/sample-runs.jsonl")
        return

    rows: list[dict[str, object]] = []
    seen: set[tuple[object, ...]] = set()
    for line_no, raw in enumerate(lines, 1):
        if not raw.strip():
            continue
        try:
            row = json.loads(raw)
        except json.JSONDecodeError as exc:
            report.error(f"{path.relative_to(ROOT)}:{line_no}: invalid JSON: {exc}")
            continue
        if not isinstance(row, dict):
            report.error(f"{path.relative_to(ROOT)}:{line_no}: row must be an object")
            continue
        for field in ("campaign_id", "case_id", "provider", "client", "client_version", "package_commit", "variant"):
            if not isinstance(row.get(field), str) or not str(row[field]).strip():
                report.error(f"{path.relative_to(ROOT)}:{line_no}: {field} must be a non-empty string")
        if row.get("case_id") not in case_ids:
            report.error(f"{path.relative_to(ROOT)}:{line_no}: unknown case_id {row.get('case_id')!r}")
        if row.get("synthetic") is not True:
            report.error(f"{path.relative_to(ROOT)}:{line_no}: repository fixture must be explicitly synthetic")
        identity = (
            row.get("campaign_id"), row.get("provider"), row.get("client"), row.get("client_version"),
            row.get("case_id"), row.get("case_revision"), row.get("variant"), row.get("repetition"),
        )
        if identity in seen:
            report.error(f"{path.relative_to(ROOT)}:{line_no}: duplicate eval identity")
        seen.add(identity)
        rows.append(row)

    if not rows:
        report.error("sample eval fixture has no rows")
        return
    if len({row.get("campaign_id") for row in rows}) != 1:
        report.error("sample eval fixture must use exactly one campaign_id")
    if len({row.get("package_commit") for row in rows}) != 1:
        report.error("sample eval fixture must use exactly one package_commit")
    variants = {row.get("variant") for row in rows}
    if not {"baseline", "candidate"}.issubset(variants):
        report.error("sample eval fixture must include baseline and candidate variants")


def validate_profiles(report: Report) -> None:
    codex_profiles = sorted((ROOT / "profiles/codex").glob("*.toml"))
    claude_profiles = sorted((ROOT / "profiles/claude").glob("*.md"))
    if len(codex_profiles) != 3 or len(claude_profiles) != 3:
        report.error("expected three Codex and three Claude optional agent profiles")

    for path in codex_profiles:
        try:
            data = tomllib.loads(path.read_text(encoding="utf-8"))
        except tomllib.TOMLDecodeError as exc:
            report.error(f"invalid Codex profile {path.relative_to(ROOT)}: {exc}")
            continue
        for field in ("name", "description", "developer_instructions"):
            if not isinstance(data.get(field), str) or not data[field].strip():
                report.error(f"{path.relative_to(ROOT)}: missing {field}")
        if data.get("sandbox_mode") != "read-only":
            report.error(f"{path.relative_to(ROOT)}: supplied specialist profiles must be read-only")
        if "model" in data or "model_reasoning_effort" in data:
            report.error(f"{path.relative_to(ROOT)}: reusable profiles must not pin a model")
        if "spawn" not in str(data.get("developer_instructions", "")).lower():
            report.warn(f"{path.relative_to(ROOT)}: profile should state its delegation boundary")

    required_tools = {"Read", "Glob", "Grep"}
    required_denials = {"Write", "Edit", "Agent"}
    for path in claude_profiles:
        meta, body = parse_frontmatter(path, report)
        if meta.get("name") != path.stem:
            report.error(f"{path.relative_to(ROOT)}: name must match filename")
        description = meta.get("description")
        if not isinstance(description, str) or not description.strip():
            report.error(f"{path.relative_to(ROOT)}: missing description")
        tools = {item.strip() for item in str(meta.get("tools", "")).split(",") if item.strip()}
        denied = {item.strip() for item in str(meta.get("disallowedTools", "")).split(",") if item.strip()}
        if not required_tools.issubset(tools):
            report.error(f"{path.relative_to(ROOT)}: read-only tool allowlist is incomplete")
        if not required_denials.issubset(denied):
            report.error(f"{path.relative_to(ROOT)}: write or nested-agent denial is incomplete")
        if "model" in meta:
            report.error(f"{path.relative_to(ROOT)}: reusable profiles must not pin a model")
        try:
            max_turns = int(str(meta.get("maxTurns", "0")))
        except ValueError:
            max_turns = 0
        if not (1 <= max_turns <= 20):
            report.error(f"{path.relative_to(ROOT)}: maxTurns must be 1..20")
        if not body:
            report.error(f"{path.relative_to(ROOT)}: empty agent prompt")

def validate_examples(report: Report) -> None:
    contract = load_json(ROOT / "examples/task-contract.static-validation.json", report)
    evidence = load_json(ROOT / "examples/completion-evidence.pass.json", report)
    if not isinstance(contract, dict) or not isinstance(evidence, dict):
        return

    if evidence.get("completion_status") != "COMPLETE":
        report.error("pass evidence must declare COMPLETE")
    if evidence.get("task_id") != contract.get("task_id"):
        report.error("pass evidence task_id must match the task contract")
    if evidence.get("working_tree_reviewed") is not True:
        report.error("pass evidence must review working tree")

    items = evidence.get("items")
    if not isinstance(items, list) or not items:
        report.error("pass evidence must contain items")
        return
    criteria: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            report.error("pass evidence items must be objects")
            continue
        criterion = item.get("criterion")
        if not isinstance(criterion, str) or not criterion.strip():
            report.error("pass evidence item has empty criterion")
            continue
        criteria.append(criterion)
        if item.get("status") not in {"PASS", "NOT_APPLICABLE"}:
            report.error(f"pass evidence criterion is not complete: {criterion}")
        if not isinstance(item.get("evidence"), str) or not item["evidence"].strip():
            report.error(f"pass evidence item has empty evidence: {criterion}")

    if len(criteria) != len(set(criteria)):
        report.error("pass evidence contains duplicate criteria")
    acceptance = contract.get("acceptance")
    if not isinstance(acceptance, list):
        report.error("task contract acceptance must be a list")
    elif set(criteria) != set(acceptance) or len(criteria) != len(acceptance):
        report.error("pass evidence criteria must exactly match task-contract acceptance")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", action="store_true", help="Treat warnings as failures.")
    parser.add_argument("--json", action="store_true", dest="json_output")
    args = parser.parse_args()
    report = Report()
    catalog = load_json(ROOT / "catalog/plugins.json", report)
    if isinstance(catalog, dict):
        plugins = catalog.get("plugins", [])
        if not isinstance(plugins, list) or not plugins:
            report.error("catalog has no plugins")
        else:
            for plugin in plugins:
                path = ROOT / plugin["path"]
                if not path.is_dir():
                    report.error(f"missing plugin directory: {plugin['path']}")
                else:
                    validate_plugin(path, report)
            validate_marketplaces(catalog, report)
            case_ids = validate_eval_cases(catalog, report)
            validate_eval_fixture(case_ids, report)
    validate_profiles(report)
    validate_examples(report)
    claude = (ROOT / "CLAUDE.md").read_text(encoding="utf-8") if (ROOT / "CLAUDE.md").exists() else ""
    if not claude.startswith("@AGENTS.md"):
        report.error("CLAUDE.md must import canonical AGENTS.md first")

    payload = {"errors": report.errors, "warnings": report.warnings, "error_count": len(report.errors), "warning_count": len(report.warnings)}
    if args.json_output:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        for item in report.errors:
            print(f"ERROR: {item}")
        for item in report.warnings:
            print(f"WARNING: {item}")
        print(f"repository validation: {'PASS' if not report.errors else 'FAIL'}")
        print(f"errors: {len(report.errors)}")
        print(f"warnings: {len(report.warnings)}")
    return 1 if report.errors or (args.strict and report.warnings) else 0


if __name__ == "__main__":
    sys.exit(main())
