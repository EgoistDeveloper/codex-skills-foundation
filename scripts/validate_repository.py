#!/usr/bin/env python3
"""Strict repository validator for packages, skills, profiles, schemas, docs, and eval fixtures."""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
import tomllib
from pathlib import Path
from typing import Any

try:
    import yaml
    from jsonschema import Draft202012Validator
except ImportError as exc:  # pragma: no cover - exercised by bootstrap dependency guard
    print(f"ERROR: missing development dependency: {exc}")
    print("Run: python -m pip install -r requirements-dev.txt")
    raise SystemExit(2) from exc

ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "catalog/plugins.json"
PORTABLE_SCHEMA_URI = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
CLAUDE_PLUGIN_SCHEMA = "https://json.schemastore.org/claude-code-plugin-manifest.json"
CLAUDE_MARKETPLACE_SCHEMA = "https://json.schemastore.org/claude-code-marketplace.json"
PLUGIN_NAME_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$")
SKILL_NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SEMVER_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$")
LINK_RE = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")
SECRET_PATTERNS = {
    "OpenAI API key": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    "GitHub token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
}
PLACEHOLDER_RE = re.compile(r"\b(?:" + "|".join(("TO" + "DO", "FIX" + "ME", "X" + "XX", "HA" + "CK")) + r")\b")
CODEX_INTERFACE_REQUIRED = {
    "displayName",
    "shortDescription",
    "longDescription",
    "developerName",
    "category",
    "capabilities",
    "websiteURL",
    "privacyPolicyURL",
    "termsOfServiceURL",
    "defaultPrompt",
    "brandColor",
    "screenshots",
}
ALLOWED_OPENAI_AUTH = {"ON_INSTALL", "ON_USE"}
ALLOWED_OPENAI_INSTALLATION = {"AVAILABLE", "INSTALLED_BY_DEFAULT", "NOT_AVAILABLE"}
EXCLUDED_PATH_PARTS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "dist",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".tox",
    ".nox",
}


class Report:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def error(self, message: str) -> None:
        self.errors.append(message)

    def warn(self, message: str) -> None:
        self.warnings.append(message)


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def is_excluded_path(path: Path) -> bool:
    try:
        parts = path.relative_to(ROOT).parts
    except ValueError:
        return False
    return any(part in EXCLUDED_PATH_PARTS for part in parts)


def load_json(path: Path, report: Report) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        report.error(f"missing JSON: {rel(path)}")
    except json.JSONDecodeError as exc:
        report.error(f"invalid JSON {rel(path)}: {exc}")
    except OSError as exc:
        report.error(f"cannot read {rel(path)}: {exc}")
    return None


def load_yaml(path: Path, report: Report) -> Any:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        report.error(f"missing YAML: {rel(path)}")
    except (OSError, yaml.YAMLError) as exc:
        report.error(f"invalid YAML {rel(path)}: {exc}")
    return None


def parse_frontmatter(path: Path, report: Report) -> tuple[dict[str, Any], str]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        report.error(f"cannot read {rel(path)}: {exc}")
        return {}, ""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        report.error(f"missing YAML frontmatter: {rel(path)}")
        return {}, text
    try:
        end = next(index for index, line in enumerate(lines[1:], 1) if line.strip() == "---")
    except StopIteration:
        report.error(f"unterminated YAML frontmatter: {rel(path)}")
        return {}, text
    try:
        data = yaml.safe_load("\n".join(lines[1:end])) or {}
    except yaml.YAMLError as exc:
        report.error(f"invalid YAML frontmatter {rel(path)}: {exc}")
        return {}, "\n".join(lines[end + 1 :]).strip()
    if not isinstance(data, dict):
        report.error(f"frontmatter must be an object: {rel(path)}")
        data = {}
    return data, "\n".join(lines[end + 1 :]).strip()


def validate_catalog(catalog: object, report: Report) -> list[dict[str, Any]]:
    if not isinstance(catalog, dict):
        report.error("catalog root must be an object")
        return []
    market = catalog.get("marketplace")
    plugins = catalog.get("plugins")
    if not isinstance(market, dict):
        report.error("catalog.marketplace must be an object")
    if not isinstance(plugins, list) or not plugins:
        report.error("catalog.plugins must be a non-empty array")
        return []
    names: set[str] = set()
    paths: set[str] = set()
    for index, plugin in enumerate(plugins):
        prefix = f"catalog.plugins[{index}]"
        if not isinstance(plugin, dict):
            report.error(f"{prefix} must be an object")
            continue
        for field in (
            "name",
            "version",
            "path",
            "description",
            "category",
            "claude_category",
            "display_name",
            "short_description",
            "brand_color",
        ):
            if not isinstance(plugin.get(field), str) or not plugin[field].strip():
                report.error(f"{prefix}.{field} is required")
        name = plugin.get("name")
        path = plugin.get("path")
        if isinstance(name, str):
            if not PLUGIN_NAME_RE.fullmatch(name):
                report.error(f"{prefix}.name is invalid: {name}")
            if name in names:
                report.error(f"duplicate plugin name: {name}")
            names.add(name)
        if isinstance(path, str):
            if path in paths:
                report.error(f"duplicate plugin path: {path}")
            paths.add(path)
            if Path(path).is_absolute() or ".." in Path(path).parts:
                report.error(f"unsafe plugin path: {path}")
        version = plugin.get("version")
        if isinstance(version, str) and not SEMVER_RE.fullmatch(version):
            report.error(f"{prefix}.version is not strict semver")
        for field in ("keywords", "default_prompts", "capabilities"):
            value = plugin.get(field)
            if not isinstance(value, list) or not value or any(not isinstance(item, str) or not item for item in value):
                report.error(f"{prefix}.{field} must be a non-empty string array")
        prompts = plugin.get("default_prompts")
        if isinstance(prompts, list):
            if len(prompts) > 3:
                report.error(f"{prefix}.default_prompts exceeds three entries")
            for prompt in prompts:
                if isinstance(prompt, str) and len(prompt) > 128:
                    report.error(f"{prefix}.default prompt exceeds 128 characters")
    disk_plugins = {
        path.name for path in (ROOT / "plugins").iterdir() if path.is_dir() and not path.name.startswith(".")
    }
    if disk_plugins != names:
        report.error(
            f"catalog/plugin-directory drift: catalog={sorted(names)}, disk={sorted(disk_plugins)}"
        )
    return [plugin for plugin in plugins if isinstance(plugin, dict)]


def validate_schema(instance: object, schema_path: Path, label: str, report: Report) -> None:
    schema = load_json(schema_path, report)
    if not isinstance(schema, dict):
        return
    try:
        Draft202012Validator.check_schema(schema)
        errors = sorted(Draft202012Validator(schema).iter_errors(instance), key=lambda exc: list(exc.path))
    except Exception as exc:  # jsonschema reports precise schema errors; keep validator resilient
        report.error(f"schema validation failed for {label}: {exc}")
        return
    for error in errors:
        location = ".".join(str(part) for part in error.path) or "<root>"
        report.error(f"{label} violates {rel(schema_path)} at {location}: {error.message}")


def validate_plugin(plugin: dict[str, Any], portable_schema: Path, report: Report) -> set[str]:
    root = ROOT / plugin["path"]
    if not root.is_dir():
        report.error(f"missing plugin directory: {plugin['path']}")
        return set()
    portable = load_json(root / "plugin.json", report)
    codex = load_json(root / ".codex-plugin/plugin.json", report)
    claude = load_json(root / ".claude-plugin/plugin.json", report)
    if not all(isinstance(value, dict) for value in (portable, codex, claude)):
        return set()

    validate_schema(portable, portable_schema, f"{plugin['name']} portable manifest", report)
    expected_name = plugin["name"]
    for label, manifest in (("portable", portable), ("Codex", codex), ("Claude", claude)):
        if manifest.get("name") != expected_name:
            report.error(f"{expected_name}: {label} manifest name mismatch")
        if manifest.get("version") != plugin["version"]:
            report.error(f"{expected_name}: {label} manifest version drift")
    if portable.get("$schema") != PORTABLE_SCHEMA_URI:
        report.error(f"{expected_name}: portable schema URI mismatch")
    extensions = portable.get("extensions")
    if not isinstance(extensions, dict) or extensions.get("com.openai.codex", {}).get("manifest") != "./.codex-plugin/plugin.json" or extensions.get("com.anthropic.claude-code", {}).get("manifest") != "./.claude-plugin/plugin.json":
        report.error(f"{expected_name}: portable provider extensions are incomplete")

    if codex.get("skills") != "./skills/":
        report.error(f"{expected_name}: Codex skills path must be ./skills/")
    interface = codex.get("interface")
    if not isinstance(interface, dict):
        report.error(f"{expected_name}: Codex interface missing")
    else:
        missing = CODEX_INTERFACE_REQUIRED - set(interface)
        if missing:
            report.error(f"{expected_name}: Codex interface missing {sorted(missing)}")
        if interface.get("displayName") != plugin["display_name"]:
            report.error(f"{expected_name}: Codex displayName drift")
        prompts = interface.get("defaultPrompt")
        if not isinstance(prompts, list) or not prompts or len(prompts) > 3:
            report.error(f"{expected_name}: Codex defaultPrompt must contain 1..3 strings")
        elif any(not isinstance(item, str) or not item or len(item) > 128 for item in prompts):
            report.error(f"{expected_name}: Codex defaultPrompt entry is invalid")
        screenshots = interface.get("screenshots")
        if screenshots != []:
            report.error(f"{expected_name}: screenshots must be an empty array until real PNG assets exist")
    for forbidden in ("hooks", "mcpServers", "apps"):
        if forbidden in codex:
            report.error(f"{expected_name}: Codex manifest contains privileged surface {forbidden}")

    if claude.get("$schema") != CLAUDE_PLUGIN_SCHEMA:
        report.error(f"{expected_name}: Claude schema URI mismatch")
    if claude.get("displayName") != plugin["display_name"]:
        report.error(f"{expected_name}: Claude displayName drift")
    for forbidden in ("hooks", "mcpServers"):
        if forbidden in claude or (root / ("hooks.json" if forbidden == "hooks" else ".mcp.json")).exists():
            report.error(f"{expected_name}: Claude package contains privileged surface {forbidden}")

    skills_root = root / "skills"
    skills: set[str] = set()
    description_budget = 0
    for skill_file in sorted(skills_root.glob("*/SKILL.md")):
        skill_name = skill_file.parent.name
        skills.add(skill_name)
        meta, body = parse_frontmatter(skill_file, report)
        if set(meta) != {"name", "description"}:
            report.error(
                f"{rel(skill_file)}: portable/OpenAI skill frontmatter must contain only name and description"
            )
        if meta.get("name") != skill_name or not SKILL_NAME_RE.fullmatch(skill_name):
            report.error(f"{rel(skill_file)}: invalid or mismatched skill name")
        description = meta.get("description")
        if not isinstance(description, str) or not (1 <= len(description) <= 1024):
            report.error(f"{rel(skill_file)}: description must be 1..1024 characters")
        else:
            description_budget += len(description)
            if "Use " not in description or "Do not " not in description:
                report.error(f"{rel(skill_file)}: description must state positive and negative triggers")
        if not body:
            report.error(f"{rel(skill_file)}: skill body is empty")
        if len(body.splitlines()) > 500:
            report.error(f"{rel(skill_file)}: skill body exceeds 500 lines")
        agent_meta = load_yaml(skill_file.parent / "agents/openai.yaml", report)
        if not isinstance(agent_meta, dict):
            continue
        agent_interface = agent_meta.get("interface")
        if not isinstance(agent_interface, dict):
            report.error(f"{rel(skill_file.parent / 'agents/openai.yaml')}: interface missing")
        else:
            for field in ("display_name", "short_description"):
                value = agent_interface.get(field)
                if not isinstance(value, str) or not value.strip():
                    report.error(f"{rel(skill_file.parent / 'agents/openai.yaml')}: {field} missing")
            short = agent_interface.get("short_description")
            if isinstance(short, str) and len(short) > 100:
                report.error(f"{rel(skill_file.parent / 'agents/openai.yaml')}: short_description too long")
        references = skill_file.parent / "references"
        if references.exists():
            for reference in references.rglob("*.md"):
                if len(reference.relative_to(references).parts) > 1:
                    report.error(f"{rel(reference)}: keep references one level deep")
    if not skills:
        report.error(f"{expected_name}: no skills found")
    if description_budget > 8000:
        report.error(f"{expected_name}: combined skill descriptions exceed 8,000 characters")
    return skills


def validate_marketplaces(plugins: list[dict[str, Any]], report: Report) -> None:
    expected = {plugin["name"]: plugin for plugin in plugins}
    openai = load_json(ROOT / ".agents/plugins/marketplace.json", report)
    claude = load_json(ROOT / ".claude-plugin/marketplace.json", report)
    if isinstance(openai, dict):
        entries = {entry.get("name"): entry for entry in openai.get("plugins", []) if isinstance(entry, dict)}
        if set(entries) != set(expected):
            report.error("OpenAI marketplace plugin set differs from catalog")
        for name, entry in entries.items():
            source = entry.get("source")
            path = source.get("path") if isinstance(source, dict) else None
            if name in expected and path != f"./{expected[name]['path']}":
                report.error(f"OpenAI marketplace path mismatch: {name}")
            policy = entry.get("policy")
            if not isinstance(policy, dict):
                report.error(f"OpenAI marketplace policy missing: {name}")
            else:
                if policy.get("installation") not in ALLOWED_OPENAI_INSTALLATION:
                    report.error(f"OpenAI marketplace installation policy invalid: {name}")
                if policy.get("authentication") not in ALLOWED_OPENAI_AUTH:
                    report.error(f"OpenAI marketplace authentication policy invalid: {name}")
            if not isinstance(entry.get("category"), str) or not entry["category"]:
                report.error(f"OpenAI marketplace category missing: {name}")
    if isinstance(claude, dict):
        if claude.get("$schema") != CLAUDE_MARKETPLACE_SCHEMA:
            report.error("Claude marketplace schema URI mismatch")
        entries = {entry.get("name"): entry for entry in claude.get("plugins", []) if isinstance(entry, dict)}
        if set(entries) != set(expected):
            report.error("Claude marketplace plugin set differs from catalog")
        for name, entry in entries.items():
            if name in expected and entry.get("source") != f"./{expected[name]['path']}":
                report.error(f"Claude marketplace path mismatch: {name}")
            if name in expected and entry.get("version") != expected[name]["version"]:
                report.error(f"Claude marketplace version drift: {name}")


def validate_profiles(report: Report) -> None:
    codex_profiles = sorted((ROOT / "profiles/codex").glob("*.toml"))
    claude_profiles = sorted((ROOT / "profiles/claude").glob("*.md"))
    if len(codex_profiles) != 3 or len(claude_profiles) != 3:
        report.error("expected exactly three Codex and three Claude optional project profiles")

    for path in codex_profiles:
        try:
            data = tomllib.loads(path.read_text(encoding="utf-8"))
        except (OSError, tomllib.TOMLDecodeError) as exc:
            report.error(f"invalid Codex profile {rel(path)}: {exc}")
            continue
        for field in ("name", "description", "developer_instructions"):
            if not isinstance(data.get(field), str) or not data[field].strip():
                report.error(f"{rel(path)}: missing {field}")
        if data.get("sandbox_mode") != "read-only":
            report.error(f"{rel(path)}: supplied specialist must be read-only")
        if "model" in data or "model_reasoning_effort" in data:
            report.error(f"{rel(path)}: reusable profile must not pin a model")
        instructions = str(data.get("developer_instructions", "")).lower()
        if "spawn" not in instructions and "delegate" not in instructions:
            report.error(f"{rel(path)}: delegation boundary is not explicit")

    required_tools = {"Read", "Glob", "Grep"}
    required_denials = {"Write", "Edit", "Agent"}
    for path in claude_profiles:
        meta, body = parse_frontmatter(path, report)
        if meta.get("name") != path.stem:
            report.error(f"{rel(path)}: name must match filename")
        tools_value = meta.get("tools")
        denied_value = meta.get("disallowedTools")
        tools = _normalize_string_list(tools_value)
        denied = _normalize_string_list(denied_value)
        if not required_tools.issubset(tools):
            report.error(f"{rel(path)}: read-only tool allowlist is incomplete")
        if not required_denials.issubset(denied):
            report.error(f"{rel(path)}: write/nested-agent denial is incomplete")
        if "model" in meta:
            report.error(f"{rel(path)}: reusable profile must not pin a model")
        try:
            max_turns = int(meta.get("maxTurns", 0))
        except (TypeError, ValueError):
            max_turns = 0
        if not (1 <= max_turns <= 20):
            report.error(f"{rel(path)}: maxTurns must be 1..20")
        if not body:
            report.error(f"{rel(path)}: agent body is empty")


def _normalize_string_list(value: object) -> set[str]:
    if isinstance(value, list):
        return {str(item).strip() for item in value if str(item).strip()}
    if isinstance(value, str):
        return {item.strip() for item in value.split(",") if item.strip()}
    return set()


def validate_examples_and_schemas(report: Report) -> None:
    schema_dir = ROOT / "schemas"
    schemas: dict[str, dict[str, Any]] = {}
    for path in sorted(schema_dir.glob("*.schema.json")):
        schema = load_json(path, report)
        if not isinstance(schema, dict):
            continue
        try:
            Draft202012Validator.check_schema(schema)
        except Exception as exc:
            report.error(f"invalid JSON Schema {rel(path)}: {exc}")
        schemas[path.name] = schema

    examples = {
        "task-contract.schema.json": ROOT / "examples/task-contract.static-validation.json",
        "completion-evidence.schema.json": ROOT / "examples/completion-evidence.pass.json",
        "handoff.schema.json": ROOT / "examples/handoff.json",
    }
    for schema_name, example_path in examples.items():
        instance = load_json(example_path, report)
        schema = schemas.get(schema_name)
        if schema is not None and instance is not None:
            for error in Draft202012Validator(schema).iter_errors(instance):
                report.error(f"{rel(example_path)} violates {schema_name}: {error.message}")

    portable_schema = ROOT / "schemas/provider/agent-plugins-1.0.0.schema.json"
    portable = load_json(portable_schema, report)
    if isinstance(portable, dict):
        try:
            Draft202012Validator.check_schema(portable)
        except Exception as exc:
            report.error(f"invalid pinned Agent Plugins schema: {exc}")


def validate_evals(plugins: list[dict[str, Any]], all_skills: set[str], report: Report) -> None:
    package_names = {plugin["name"] for plugin in plugins}
    case_schema = load_json(ROOT / "schemas/eval-case.schema.json", report)
    run_schema = load_json(ROOT / "schemas/eval-run.schema.json", report)
    cases = sorted((ROOT / "evals/cases").glob("*.json"))
    if len(cases) < 16:
        report.error("at least sixteen positive/negative behavior eval cases are required")
    case_ids: set[str] = set()
    for path in cases:
        case = load_json(path, report)
        if not isinstance(case, dict):
            continue
        if isinstance(case_schema, dict):
            for error in Draft202012Validator(case_schema).iter_errors(case):
                report.error(f"{rel(path)} violates eval-case schema: {error.message}")
        case_id = case.get("id")
        if case_id != path.stem or case_id in case_ids:
            report.error(f"{rel(path)}: id mismatch or duplicate")
        if isinstance(case_id, str):
            case_ids.add(case_id)
        if case.get("package") not in package_names:
            report.error(f"{rel(path)}: unknown package")
        expected = case.get("expected_activation", [])
        forbidden = case.get("forbidden_activation", [])
        for skill in list(expected) + list(forbidden):
            if skill not in all_skills:
                report.error(f"{rel(path)}: unknown skill {skill}")
        if set(expected) & set(forbidden):
            report.error(f"{rel(path)}: skill cannot be both expected and forbidden")

    fixture = ROOT / "evals/fixtures/sample-runs.jsonl"
    rows: list[dict[str, Any]] = []
    seen: set[tuple[object, ...]] = set()
    try:
        lines = fixture.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        report.error(f"cannot read {rel(fixture)}: {exc}")
        return
    for line_no, raw in enumerate(lines, 1):
        if not raw.strip():
            continue
        try:
            row = json.loads(raw)
        except json.JSONDecodeError as exc:
            report.error(f"{rel(fixture)}:{line_no}: invalid JSON: {exc}")
            continue
        if isinstance(run_schema, dict):
            for error in Draft202012Validator(run_schema).iter_errors(row):
                report.error(f"{rel(fixture)}:{line_no} violates eval-run schema: {error.message}")
        if row.get("case_id") not in case_ids:
            report.error(f"{rel(fixture)}:{line_no}: unknown case_id")
        if row.get("synthetic") is not True:
            report.error(f"{rel(fixture)}:{line_no}: repository fixture must be explicitly synthetic")
        identity = (
            row.get("campaign_id"),
            row.get("provider"),
            row.get("client"),
            row.get("client_version"),
            row.get("case_id"),
            row.get("case_revision"),
            row.get("variant"),
            row.get("repetition"),
        )
        if identity in seen:
            report.error(f"{rel(fixture)}:{line_no}: duplicate eval identity")
        seen.add(identity)
        rows.append(row)
    variants = {row.get("variant") for row in rows}
    if variants != {"baseline", "previous", "candidate"}:
        report.error("sample eval fixture must include baseline, previous, and candidate")
    if len({row.get("harness_commit") for row in rows}) != 1:
        report.error("sample eval fixture must use one harness_commit")
    subject_identities = {
        row.get("variant"): (row.get("subject_version"), row.get("subject_commit")) for row in rows
    }
    if len(set(subject_identities.values())) != len(subject_identities):
        report.error("sample eval variants must have distinct subject identities")


def validate_markdown_links(report: Report) -> None:
    for path in ROOT.rglob("*.md"):
        if is_excluded_path(path):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            report.error(f"cannot read {rel(path)}: {exc}")
            continue
        for target in LINK_RE.findall(text):
            target = target.strip().strip("<>")
            if not target or target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            clean = target.split("#", 1)[0]
            if not clean:
                continue
            resolved = (path.parent / clean).resolve()
            try:
                resolved.relative_to(ROOT.resolve())
            except ValueError:
                report.error(f"local link escapes repository in {rel(path)}: {target}")
                continue
            if not resolved.exists():
                report.error(f"broken local link in {rel(path)}: {target}")


def validate_security_and_placeholders(report: Report) -> None:
    allowed_placeholder_files = set()
    for path in ROOT.rglob("*"):
        if not path.is_file() or is_excluded_path(path):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        except OSError as exc:
            report.error(f"cannot read {rel(path)}: {exc}")
            continue
        for label, pattern in SECRET_PATTERNS.items():
            if pattern.search(text):
                report.error(f"possible {label} in {rel(path)}")
        if path not in allowed_placeholder_files and PLACEHOLDER_RE.search(text):
            report.error(f"placeholder marker in {rel(path)}")


def validate_root_contract(report: Report) -> None:
    claude = ROOT / "CLAUDE.md"
    if not claude.is_file() or not claude.read_text(encoding="utf-8").startswith("@AGENTS.md"):
        report.error("CLAUDE.md must import canonical AGENTS.md first")
    for required in (
        "README.md",
        "README.tr.md",
        "LICENSE",
        "SECURITY.md",
        "PRIVACY.md",
        "TERMS.md",
        "THIRD_PARTY_NOTICES.md",
        "requirements-dev.txt",
    ):
        if not (ROOT / required).is_file():
            report.error(f"missing root file: {required}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", action="store_true", help="Treat warnings as failures.")
    parser.add_argument("--json", action="store_true", dest="json_output")
    args = parser.parse_args()

    report = Report()
    catalog = load_json(CATALOG_PATH, report)
    plugins = validate_catalog(catalog, report)
    portable_schema = ROOT / "schemas/provider/agent-plugins-1.0.0.schema.json"
    all_skills: set[str] = set()
    for plugin in plugins:
        all_skills.update(validate_plugin(plugin, portable_schema, report))
    validate_marketplaces(plugins, report)
    validate_profiles(report)
    validate_examples_and_schemas(report)
    validate_evals(plugins, all_skills, report)
    validate_markdown_links(report)
    validate_security_and_placeholders(report)
    validate_root_contract(report)

    payload = {
        "ok": not report.errors and (not args.strict or not report.warnings),
        "errors": report.errors,
        "warnings": report.warnings,
        "error_count": len(report.errors),
        "warning_count": len(report.warnings),
    }
    if args.json_output:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        for item in report.errors:
            print(f"ERROR: {item}")
        for item in report.warnings:
            print(f"WARNING: {item}")
        print(f"repository validation: {'PASS' if payload['ok'] else 'FAIL'}")
        print(f"errors: {len(report.errors)}")
        print(f"warnings: {len(report.warnings)}")
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
