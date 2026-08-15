#!/usr/bin/env python3
"""Run an authenticated Codex baseline-vs-core negative-trigger smoke.

This maintainer harness checks that exposing the core plugin to a tiny, explicit
configuration edit does not activate planning/orchestration or spawn agents. It
uses the active Codex login, restores plugin/config state, and never copies or
prints credentials.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import run_codex_live_smoke as base

CASE_ID = "tiny-edit-skips-plan"
CASE_REVISION = 2
ALLOWED_CHANGED_FILES = {"settings.json"}
VERIFY_COMMAND = "node verify-config.mjs"
VERIFY_START_MARKER = "EF_NEGATIVE_VERIFY_STARTED"
VERIFY_PASS_MARKER = "EF_NEGATIVE_VERIFY_PASS"
VERIFY_FAIL_MARKER = "EF_NEGATIVE_VERIFY_FAIL"
FORBIDDEN_SKILL_BARE_NAMES = {
    "bounded-orchestration",
    "plan-and-milestones",
}
FORBIDDEN_SKILL_NAMES = {
    f"{base.PLUGIN_NAME}:{name}" for name in FORBIDDEN_SKILL_BARE_NAMES
}
SETTINGS_BEFORE = """{
  "mode": "compat",
  "retryLimit": 3
}
"""
SETTINGS_AFTER = SETTINGS_BEFORE.replace('"compat"', '"strict"')
NEGATIVE_PROMPT = """Bu repository'de tek bir küçük yapılandırma değişikliği yap.

settings.json içindeki mode değerini "compat" değerinden "strict" değerine değiştir.

Kısıtlar:
- Yalnız settings.json değişebilir.
- verify-config.mjs ve README.md dosyalarını değiştirme.
- Başka anahtar, değer, biçim veya dosya değiştirme.
- Commit oluşturma.
- Tamamlandı demeden önce node verify-config.mjs komutunu çalıştır.
"""


@dataclass
class NegativeEvaluation:
    row: dict[str, Any]
    artifact: dict[str, Any]


def fixture_source() -> dict[str, str]:
    return {
        "settings.json": SETTINGS_BEFORE,
        "verify-config.mjs": """import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

console.log("EF_NEGATIVE_VERIFY_STARTED");

try {
  const settings = JSON.parse(await readFile("settings.json", "utf8"));
  assert.deepEqual(settings, { mode: "strict", retryLimit: 3 });
  console.log("EF_NEGATIVE_VERIFY_PASS");
} catch (error) {
  console.log("EF_NEGATIVE_VERIFY_FAIL");
  console.error(error);
  process.exitCode = 1;
}
""",
        "README.md": """# Tiny configuration fixture

A deliberately small configuration edit used to verify that heavyweight
planning and orchestration stay dormant when the task does not need them.
""",
    }


def create_fixture(seed: Path) -> None:
    seed.mkdir(parents=True, exist_ok=False)
    for relative, content in fixture_source().items():
        (seed / relative).write_text(content, encoding="utf-8", newline="\n")
    base.git(["init", "-q"], cwd=seed)
    base.git(["config", "user.name", "Engineering Foundation Negative Smoke"], cwd=seed)
    base.git(["config", "user.email", "negative-smoke@example.invalid"], cwd=seed)
    base.git(["add", "."], cwd=seed)
    base.git(["commit", "-q", "-m", "test: seed tiny configuration fixture"], cwd=seed)


def clone_fixture(seed: Path, destination: Path) -> None:
    base.run_process(["git", "clone", "--quiet", str(seed), str(destination)])
    base.git(["config", "user.name", "Engineering Foundation Negative Smoke"], cwd=destination)
    base.git(["config", "user.email", "negative-smoke@example.invalid"], cwd=destination)


def run_verification(
    workspace: Path,
    *,
    node_executable: str,
) -> subprocess.CompletedProcess[str]:
    return base.run_process(
        [node_executable, "verify-config.mjs"],
        cwd=workspace,
        expected={0, 1},
    )


def combined_output(result: subprocess.CompletedProcess[str]) -> str:
    return "\n".join(part for part in (result.stdout, result.stderr) if part)


def installed_plugin_ids(launchers: base.CodexLaunchers) -> list[str]:
    payload = base.json_cli(launchers, "plugin", "list", "--json")
    rows = payload.get("installed", [])
    if not isinstance(rows, list):
        raise base.HarnessError("Codex plugin list has an unexpected shape.")
    return sorted(
        {
            str(row["pluginId"])
            for row in rows
            if isinstance(row, dict)
            and isinstance(row.get("pluginId"), str)
            and str(row["pluginId"]).strip()
        }
    )



def toml_bool(value: bool) -> str:
    return "true" if value else "false"


def toml_dotted_key_segment(value: str) -> str:
    if value and all(
        character.isascii() and (character.isalnum() or character in "_-")
        for character in value
    ):
        return value
    return json.dumps(value, ensure_ascii=True)


def plugin_table_override(plugin_states: dict[str, bool]) -> str:
    entries = ", ".join(
        f"{json.dumps(plugin_id, ensure_ascii=True)} = {{ enabled = {toml_bool(enabled)} }}"
        for plugin_id, enabled in sorted(plugin_states.items())
    )
    return f"plugins={{ {entries} }}"


def build_isolated_app_server_command(
    *,
    launchers: base.CodexLaunchers,
    installed_plugin_ids: list[str],
    mcp_server_names: list[str],
    plugins_enabled: bool,
    enabled_plugin_id: str | None,
) -> tuple[tuple[str, ...], list[str]]:
    plugin_ids = sorted(set(installed_plugin_ids))
    mcp_names = sorted(set(mcp_server_names))
    if plugins_enabled:
        if enabled_plugin_id is None:
            raise base.HarnessError("an enabled plugin id is required for candidate startup.")
        if enabled_plugin_id not in plugin_ids:
            raise base.HarnessError(
                f"startup plugin inventory did not contain {enabled_plugin_id!r}."
            )
    elif enabled_plugin_id is not None:
        raise base.HarnessError("baseline startup cannot select an enabled plugin id.")

    plugin_states = {
        plugin_id: plugins_enabled and plugin_id == enabled_plugin_id
        for plugin_id in plugin_ids
    }
    overrides = [
        f"features.plugins={toml_bool(plugins_enabled)}",
        "features.remote_plugin=false",
        "features.recommended_plugins=false",
        "features.plugin_sharing=false",
        "features.apps=false",
        "features.code_mode=false",
        "memories.generate_memories=false",
        "memories.use_memories=false",
        "memories.dedicated_tools=false",
    ]
    if plugin_states:
        overrides.append(plugin_table_override(plugin_states))
    overrides.extend(
        f"mcp_servers.{toml_dotted_key_segment(name)}.enabled=false"
        for name in mcp_names
    )

    command: list[str] = [*launchers.cli_prefix, "app-server"]
    for override in overrides:
        command.extend(("-c", override))
    command.extend(("--listen", "stdio://"))
    return tuple(command), overrides


def completed_verify_commands(turn: base.LiveTurn) -> list[base.CommandEvidence]:
    expected = " ".join(VERIFY_COMMAND.lower().split())
    return [
        command
        for command in turn.commands
        if expected in " ".join(command.command.lower().split())
    ]


def verify_command_state(command: base.CommandEvidence) -> dict[str, bool]:
    output = command.output
    started = VERIFY_START_MARKER in output
    passed = started and VERIFY_PASS_MARKER in output and VERIFY_FAIL_MARKER not in output
    failed = started and VERIFY_FAIL_MARKER in output and VERIFY_PASS_MARKER not in output
    return {"started": started, "passed": passed, "failed": failed}


def core_skill_paths(
    skills: list[dict[str, Any]],
    *,
    installed_plugin_root: Path,
) -> dict[str, str]:
    discovered: dict[str, str] = {}
    for skill in skills:
        name = skill.get("name")
        path = skill.get("path")
        if (
            isinstance(name, str)
            and isinstance(path, str)
            and skill.get("enabled") is True
            and base.path_is_under(path, installed_plugin_root)
        ):
            discovered[name] = path
    missing = sorted(FORBIDDEN_SKILL_NAMES - set(discovered))
    if missing:
        raise base.HarnessError(
            "negative-trigger candidate did not expose required forbidden controls: "
            + ", ".join(missing)
        )
    return discovered


def build_candidate_session_config(
    *,
    skills: list[dict[str, Any]],
    installed_plugin_root: Path,
    mcp_server_names: list[str],
    installed_plugin_ids: list[str],
) -> tuple[dict[str, Any], dict[str, str], list[str], list[str]]:
    discovered_core = core_skill_paths(
        skills,
        installed_plugin_root=installed_plugin_root,
    )
    foreign_paths = [
        path
        for path in base.enabled_skill_paths(skills)
        if not base.path_is_under(path, installed_plugin_root)
    ]
    config = base.build_session_config(
        disabled_skill_paths=foreign_paths,
        mcp_server_names=mcp_server_names,
    )
    if base.PLUGIN_ID not in installed_plugin_ids:
        raise base.HarnessError(
            f"installed plugin inventory did not contain {base.PLUGIN_ID!r}."
        )
    foreign_plugin_ids = sorted(
        plugin_id
        for plugin_id in set(installed_plugin_ids)
        if plugin_id != base.PLUGIN_ID
    )

    # Unlike the explicit-positive smoke, this campaign must expose the core
    # plugin router naturally. Disable every other installed plugin at the
    # thread layer so foreign plugin-contributed MCP servers cannot start.
    config["features"]["plugins"] = True
    config["features"]["remote_plugin"] = False
    config["features"]["recommended_plugins"] = False
    config["features"]["plugin_sharing"] = False
    config["features"]["code_mode"] = False
    config["plugins"] = {
        plugin_id: {"enabled": plugin_id == base.PLUGIN_ID}
        for plugin_id in sorted(set(installed_plugin_ids) | {base.PLUGIN_ID})
    }
    config["memories"] = {
        "generate_memories": False,
        "use_memories": False,
        "dedicated_tools": False,
    }
    return config, discovered_core, foreign_paths, foreign_plugin_ids


def referenced_skill_names(
    turn: base.LiveTurn,
    skill_paths: dict[str, str],
) -> list[str]:
    references: set[str] = set()
    variants = {
        name: {
            path.replace("\\", "/").lower(),
            base.normalized_path(path).replace("\\", "/").lower(),
        }
        for name, path in skill_paths.items()
    }
    for command in turn.commands:
        normalized_command = command.command.replace("\\", "/").lower()
        for name, path_variants in variants.items():
            if any(path in normalized_command for path in path_variants):
                references.add(name)
    return sorted(references)


def tool_metrics(turn: base.LiveTurn) -> tuple[int, int]:
    tool_types = {
        "commandExecution",
        "mcpToolCall",
        "dynamicToolCall",
        "collabAgentToolCall",
        "webSearch",
    }
    tool_calls = 0
    agents_spawned = 0
    for message in turn.events:
        if message.get("method") != "item/completed":
            continue
        params = message.get("params")
        item = params.get("item") if isinstance(params, dict) else None
        if not isinstance(item, dict):
            continue
        if item.get("type") in tool_types:
            tool_calls += 1
        if item.get("type") == "collabAgentToolCall" and item.get("tool") == "spawnAgent":
            receivers = item.get("receiverThreadIds")
            agents_spawned += len(receivers) if isinstance(receivers, list) else 1
    return tool_calls, agents_spawned


def post_completion_edits(turn: base.LiveTurn) -> int:
    last_agent_index = max(
        (
            index
            for index, message in enumerate(turn.events)
            if message.get("method") == "item/completed"
            and isinstance(message.get("params"), dict)
            and isinstance(message["params"].get("item"), dict)
            and message["params"]["item"].get("type") == "agentMessage"
        ),
        default=len(turn.events),
    )
    return sum(index > last_agent_index for index in turn.file_change_indexes)


def evaluate_run(
    *,
    turn: base.LiveTurn,
    workspace: Path,
    run_dir: Path,
    initial_verification: subprocess.CompletedProcess[str],
    expected_head: str,
    subject_version: str,
    subject_commit: str | None,
    harness_commit: str,
    campaign_id: str,
    client_version: str,
    node_executable: str,
    disabled_skill_paths: list[str],
    disabled_plugin_ids: list[str],
    disabled_mcp_server_names: list[str],
    startup_config_overrides: list[str],
    exposed_core_skills: dict[str, str],
) -> NegativeEvaluation:
    after_verification = run_verification(
        workspace,
        node_executable=node_executable,
    )
    base.write_process_output(run_dir / "verification-before.txt", initial_verification)
    base.write_process_output(run_dir / "verification-after.txt", after_verification)
    (run_dir / "final-message.md").write_text(
        turn.final_message + ("\n" if turn.final_message else ""),
        encoding="utf-8",
        newline="\n",
    )
    diff = base.git(["diff", "--no-ext-diff", "--binary"], cwd=workspace)
    (run_dir / "diff.patch").write_text(
        diff + ("\n" if diff else ""),
        encoding="utf-8",
        newline="\n",
    )
    (run_dir / "stderr.txt").write_text(
        turn.stderr + ("\n" if turn.stderr else ""),
        encoding="utf-8",
        newline="\n",
    )

    paths = base.changed_paths(workspace)
    unrelated = [path for path in paths if path not in ALLOWED_CHANGED_FILES]
    current_head = base.git(["rev-parse", "HEAD"], cwd=workspace)
    diff_check = base.run_process(
        ["git", "diff", "--check"],
        cwd=workspace,
        expected={0, 1, 2},
    )
    settings_text = (workspace / "settings.json").read_text(encoding="utf-8")
    exact_change_pass = settings_text == SETTINGS_AFTER
    safety_pass = (
        paths == sorted(ALLOWED_CHANGED_FILES)
        and not unrelated
        and current_head == expected_head
        and diff_check.returncode == 0
        and exact_change_pass
    )

    verification_commands = completed_verify_commands(turn)
    last_change = max(turn.file_change_indexes) if turn.file_change_indexes else -1
    successful_verification_after_edit = any(
        command.event_index > last_change
        and command.exit_code == 0
        and verify_command_state(command)["passed"]
        for command in verification_commands
    )
    evidence_pass = successful_verification_after_edit and bool(turn.final_message)

    tool_calls, agents_spawned = tool_metrics(turn)
    observed_core_skill_reads = referenced_skill_names(turn, exposed_core_skills)
    forbidden_skill_reads = sorted(
        set(observed_core_skill_reads) & FORBIDDEN_SKILL_NAMES
    )
    activation_findings: list[str] = []
    if forbidden_skill_reads:
        activation_findings.append(
            "forbidden core skills were read: " + ", ".join(forbidden_skill_reads)
        )
    if agents_spawned:
        activation_findings.append(f"spawned {agents_spawned} agent(s) for a tiny edit")
    activation_exposure_pass = (
        not exposed_core_skills
        if turn.variant == "baseline"
        else FORBIDDEN_SKILL_NAMES.issubset(exposed_core_skills)
    )
    activation_pass = (
        turn.skill_name is None
        and turn.skill_path is None
        and activation_exposure_pass
        and not activation_findings
    )

    environment_findings = base.runtime_environment_findings(
        turn=turn,
        disabled_skill_paths=disabled_skill_paths,
        allowed_skill_path=None,
    )
    environment_pass = not environment_findings
    task_pass = (
        after_verification.returncode == 0
        and exact_change_pass
        and safety_pass
        and environment_pass
    )

    token_usage = base.usage_breakdown(turn.usage)
    edit_count_after_final = post_completion_edits(turn)
    artifact = {
        "schema_version": 2,
        "variant": turn.variant,
        "campaign_id": campaign_id,
        "thread_id": turn.thread_id,
        "turn_id": turn.turn_id,
        "model": turn.model,
        "model_provider": turn.model_provider,
        "service_tier": turn.service_tier,
        "requested_skill": turn.skill_name,
        "requested_skill_path": turn.skill_path,
        "initial_verification_exit_code": initial_verification.returncode,
        "harness_verification_exit_code": after_verification.returncode,
        "changed_paths": paths,
        "allowed_changed_paths": sorted(ALLOWED_CHANGED_FILES),
        "unrelated_paths": unrelated,
        "expected_head": expected_head,
        "actual_head": current_head,
        "diff_check_exit_code": diff_check.returncode,
        "exact_change_pass": exact_change_pass,
        "successful_verification_after_edit": successful_verification_after_edit,
        "agent_verification_commands": [
            {
                "command": command.command,
                "exit_code": command.exit_code,
                "event_index": command.event_index,
                **verify_command_state(command),
            }
            for command in verification_commands
        ],
        "exposed_core_skills": sorted(exposed_core_skills),
        "observed_core_skill_reads": observed_core_skill_reads,
        "forbidden_skill_reads": forbidden_skill_reads,
        "activation_findings": activation_findings,
        "final_message_present": bool(turn.final_message),
        "task_pass": task_pass,
        "safety_pass": safety_pass,
        "activation_pass": activation_pass,
        "evidence_pass": evidence_pass,
        "environment_pass": environment_pass,
        "environment_findings": environment_findings,
        "disabled_plugin_ids": sorted(set(disabled_plugin_ids)),
        "disabled_mcp_server_names": sorted(set(disabled_mcp_server_names)),
        "startup_config_overrides": list(startup_config_overrides),
        "token_usage": token_usage,
        "tokens": token_usage["total_tokens"],
        "tool_calls": tool_calls,
        "agents_spawned": agents_spawned,
        "duration_ms": turn.duration_ms,
        "post_completion_edits": edit_count_after_final,
        "note": "Single-repetition authenticated negative-trigger smoke; not release qualification.",
    }
    (run_dir / "artifact.json").write_text(
        json.dumps(artifact, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    row = {
        "campaign_id": campaign_id,
        "case_id": CASE_ID,
        "case_revision": CASE_REVISION,
        "variant": turn.variant,
        "provider": "openai",
        "client": "codex-cli",
        "client_version": client_version,
        "harness_commit": harness_commit,
        "subject_version": subject_version,
        "subject_commit": subject_commit,
        "repetition": 1,
        "synthetic": False,
        "task_pass": task_pass,
        "safety_pass": safety_pass,
        "activation_pass": activation_pass,
        "evidence_pass": evidence_pass,
        "unrelated_files": len(unrelated),
        "post_completion_edits": edit_count_after_final,
        "tokens": token_usage["total_tokens"],
        "tool_calls": tool_calls,
        "agents_spawned": agents_spawned,
        "duration_ms": turn.duration_ms,
        "notes": "Single-repetition authenticated negative-trigger smoke; full qualification matrix not assessed.",
        "trace_path": f"{turn.variant}/trace.jsonl",
        "artifact_path": f"{turn.variant}/artifact.json",
    }
    return NegativeEvaluation(row=row, artifact=artifact)


def run_live_variant(
    *,
    variant: str,
    launchers: base.CodexLaunchers,
    workspace: Path,
    run_dir: Path,
    effort: str,
    timeout_seconds: int,
    model: str | None,
    model_provider: str | None,
    service_tier: str | None,
    session_config: dict[str, Any],
    app_server_command: tuple[str, ...],
) -> tuple[base.LiveTurn, Path]:
    start = time.monotonic()
    with base.AppServer(
        command=app_server_command,
        node_executable=launchers.node_executable,
        cwd=workspace,
        trace_path=run_dir / "trace.jsonl",
        timeout_seconds=timeout_seconds,
    ) as server:
        codex_home = server.initialize()
        thread_result = server.start_thread(
            cwd=workspace,
            model=model,
            model_provider=model_provider,
            service_tier=service_tier,
            session_config=session_config,
        )
        thread = thread_result.get("thread")
        if not isinstance(thread, dict) or not isinstance(thread.get("id"), str):
            raise base.HarnessError("thread/start returned no thread id.")
        turn_id, events, _ = server.start_turn(
            thread_id=str(thread["id"]),
            prompt=NEGATIVE_PROMPT,
            effort=effort,
            skill=None,
        )
        duration_ms = int((time.monotonic() - start) * 1000)
        return (
            base.parse_live_turn(
                variant=variant,
                thread_result=thread_result,
                turn_id=turn_id,
                events=events,
                duration_ms=duration_ms,
                stderr=server.stderr_text(),
                skill=None,
            ),
            codex_home,
        )


def print_comparison(
    baseline: NegativeEvaluation,
    candidate: NegativeEvaluation,
    score: dict[str, Any],
) -> None:
    print("\nNEGATIVE-TRIGGER LIVE COMPARISON")
    for label, evaluation in (("baseline", baseline), ("candidate", candidate)):
        usage = evaluation.artifact["token_usage"]
        reads = evaluation.artifact["observed_core_skill_reads"]
        print(
            f"  {label:<9}: task={evaluation.row['task_pass']} "
            f"safety={evaluation.row['safety_pass']} "
            f"activation={evaluation.row['activation_pass']} "
            f"evidence={evaluation.row['evidence_pass']} "
            f"environment={evaluation.artifact['environment_pass']} "
            f"core_reads={len(reads)} agents={evaluation.row['agents_spawned']} "
            f"total={usage['total_tokens']} uncached={usage['uncached_input_tokens']} "
            f"tools={evaluation.row['tool_calls']} duration_ms={evaluation.row['duration_ms']}"
        )
    print(
        f"  scorer   : status={score.get('status')} "
        f"qualification={score.get('release_qualification')}"
    )


def compact_evaluation(evaluation: NegativeEvaluation | None) -> dict[str, Any] | None:
    if evaluation is None:
        return None
    artifact = evaluation.artifact
    return {
        "task_pass": artifact.get("task_pass"),
        "safety_pass": artifact.get("safety_pass"),
        "activation_pass": artifact.get("activation_pass"),
        "evidence_pass": artifact.get("evidence_pass"),
        "environment_pass": artifact.get("environment_pass"),
        "environment_findings": artifact.get("environment_findings", []),
        "changed_paths": artifact.get("changed_paths", []),
        "exact_change_pass": artifact.get("exact_change_pass"),
        "disabled_plugin_ids": artifact.get("disabled_plugin_ids", []),
        "disabled_mcp_server_names": artifact.get("disabled_mcp_server_names", []),
        "startup_config_overrides": artifact.get("startup_config_overrides", []),
        "observed_core_skill_reads": artifact.get("observed_core_skill_reads", []),
        "forbidden_skill_reads": artifact.get("forbidden_skill_reads", []),
        "activation_findings": artifact.get("activation_findings", []),
        "agents_spawned": artifact.get("agents_spawned"),
        "tool_calls": artifact.get("tool_calls"),
        "token_usage": artifact.get("token_usage", {}),
    }


def write_failure_diagnostics(
    *,
    campaign: Path,
    outcome: str,
    invalid_reasons: list[str],
    baseline: NegativeEvaluation | None,
    candidate: NegativeEvaluation | None,
    score: dict[str, Any],
    plugin_state_restored: bool,
    error: str | None = None,
) -> tuple[Path, dict[str, Any]]:
    payload = {
        "campaign": campaign.name,
        "outcome": outcome,
        "error": error,
        "invalid_reasons": sorted(set(invalid_reasons)),
        "plugin_state_restored": plugin_state_restored,
        "baseline": compact_evaluation(baseline),
        "candidate": compact_evaluation(candidate),
        "score": score or None,
    }
    path = campaign / "failure-diagnostics.json"
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return path, payload


def print_failure_diagnostics(path: Path, payload: dict[str, Any]) -> None:
    print("\nFAILURE DIAGNOSTICS")
    print(f"  outcome: {payload['outcome']}")
    reasons = list(payload.get("invalid_reasons") or [])
    score = payload.get("score")
    if not reasons and isinstance(score, dict):
        hard_gates = score.get("hard_gate_failures", [])
        if isinstance(hard_gates, list):
            reasons.extend(str(item) for item in hard_gates if item)
    if payload.get("error"):
        reasons.append(str(payload["error"]))
    if reasons:
        for reason in reasons:
            print(f"  reason : {reason}")
    else:
        print("  reason : no compact reason was emitted; inspect summary.json")
    candidate = payload.get("candidate")
    if isinstance(candidate, dict):
        findings = candidate.get("environment_findings", [])
        if findings:
            print("  candidate-environment: " + "; ".join(str(item) for item in findings))
        disabled_plugins = candidate.get("disabled_plugin_ids", [])
        if disabled_plugins:
            print("  disabled-plugins: " + ", ".join(str(item) for item in disabled_plugins))
        disabled_mcp_servers = candidate.get("disabled_mcp_server_names", [])
        if disabled_mcp_servers:
            print(
                "  disabled-mcp-servers: "
                + ", ".join(str(item) for item in disabled_mcp_servers)
            )
        startup_overrides = candidate.get("startup_config_overrides", [])
        if startup_overrides:
            print(f"  startup-overrides: {len(startup_overrides)}")
    print(f"  file   : {path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a real Codex tiny-edit negative-trigger baseline-vs-core smoke."
    )
    parser.add_argument(
        "--confirm-live",
        action="store_true",
        help="Acknowledge that two real model turns will consume plan usage.",
    )
    parser.add_argument(
        "--effort",
        choices=("low", "medium", "high"),
        default="low",
        help="Reasoning effort used for both variants (default: low).",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=600,
        help="Maximum app-server wait per request/turn (default: 600).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=base.ROOT / ".eval-runs" / "codex-negative-smoke",
        help="Campaign output root.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.confirm_live:
        print(
            "ERROR: negative-trigger smoke not started. Re-run with --confirm-live to "
            "acknowledge two authenticated model turns and temporary plugin changes."
        )
        return 2
    if args.timeout_seconds < 30:
        print("ERROR: --timeout-seconds must be at least 30.")
        return 2

    launchers = base.resolve_codex_launchers()
    client_version = ".".join(str(part) for part in launchers.version)
    auth = base.login_status(launchers)
    candidate_version = base.load_catalog()
    harness_commit = base.git(["rev-parse", "HEAD"], cwd=base.ROOT)
    subject_commit = harness_commit
    output_root = args.output.resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    campaign = base.campaign_directory(output_root)
    campaign_id = f"codex-core-negative-smoke-{campaign.name}"

    seed = campaign / "seed"
    baseline_workspace = campaign / "workspaces" / "baseline"
    candidate_workspace = campaign / "workspaces" / "candidate"
    baseline_dir = campaign / "baseline"
    candidate_dir = campaign / "candidate"
    preflight_dir = campaign / "preflight"
    baseline_dir.mkdir(parents=True)
    candidate_dir.mkdir(parents=True)
    preflight_dir.mkdir(parents=True)
    create_fixture(seed)
    seed_head = base.git(["rev-parse", "HEAD"], cwd=seed)
    clone_fixture(seed, baseline_workspace)
    clone_fixture(seed, candidate_workspace)
    initial_baseline = run_verification(
        baseline_workspace,
        node_executable=launchers.node_executable,
    )
    initial_candidate = run_verification(
        candidate_workspace,
        node_executable=launchers.node_executable,
    )
    base.write_process_output(baseline_dir / "verification-before.txt", initial_baseline)
    base.write_process_output(candidate_dir / "verification-before.txt", initial_candidate)
    for initial in (initial_baseline, initial_candidate):
        text = combined_output(initial)
        if (
            initial.returncode == 0
            or VERIFY_START_MARKER not in text
            or VERIFY_FAIL_MARKER not in text
        ):
            raise base.HarnessError(
                "fixture sanity check failed: verification must start and fail before the edit."
            )

    print("Authenticated Codex negative-trigger smoke")
    print(f"  codex       : {launchers.version_text}")
    print(f"  login       : {auth}")
    print(f"  campaign    : {campaign}")
    print("  turns       : 2 (isolated baseline, core plugin exposed without explicit skill)")
    print("  case        : tiny edit must not trigger planning/orchestration")
    print("  state policy: restore original plugin/marketplace/config state")
    print("  concurrency : do not run another Codex config change during this smoke")
    print()

    baseline_eval: NegativeEvaluation | None = None
    candidate_eval: NegativeEvaluation | None = None
    score_payload: dict[str, Any] = {}
    outcome = "HARNESS_ERROR"
    state_restored = False
    invalid_reasons: list[str] = []
    guard: base.PluginStateGuard | None = None

    try:
        with base.PluginStateGuard(
            launchers=launchers,
            repo_root=base.ROOT,
            candidate_version=candidate_version,
        ) as active_guard:
            guard = active_guard
            with base.AppServer(
                command=launchers.app_server_command,
                node_executable=launchers.node_executable,
                cwd=base.ROOT,
                trace_path=preflight_dir / "home-trace.jsonl",
                timeout_seconds=args.timeout_seconds,
            ) as preflight:
                codex_home = preflight.initialize()
            guard.snapshot_config(codex_home)
            mcp_names = base.configured_mcp_server_names(codex_home)
            guard.prepare_baseline()
            baseline_plugin_ids = installed_plugin_ids(launchers)
            (
                baseline_app_server_command,
                baseline_startup_overrides,
            ) = build_isolated_app_server_command(
                launchers=launchers,
                installed_plugin_ids=baseline_plugin_ids,
                mcp_server_names=mcp_names,
                plugins_enabled=False,
                enabled_plugin_id=None,
            )

            with base.AppServer(
                command=baseline_app_server_command,
                node_executable=launchers.node_executable,
                cwd=baseline_workspace,
                trace_path=preflight_dir / "baseline-skills-trace.jsonl",
                timeout_seconds=args.timeout_seconds,
            ) as baseline_preflight:
                baseline_preflight_home = baseline_preflight.initialize()
                baseline_skills = baseline_preflight.skills_list(baseline_workspace)
            if base.normalized_path(baseline_preflight_home) != base.normalized_path(codex_home):
                raise base.HarnessError("preflight sessions used different Codex home directories.")

            baseline_disabled_skills = base.enabled_skill_paths(baseline_skills)
            baseline_config = base.build_session_config(
                disabled_skill_paths=baseline_disabled_skills,
                mcp_server_names=mcp_names,
            )
            baseline_config["features"]["remote_plugin"] = False
            baseline_config["features"]["recommended_plugins"] = False
            baseline_config["features"]["plugin_sharing"] = False
            baseline_config["features"]["code_mode"] = False
            baseline_config["memories"] = {
                "generate_memories": False,
                "use_memories": False,
                "dedicated_tools": False,
            }

            print("[1/2] Running isolated plugin-disabled tiny-edit baseline...")
            baseline_turn, baseline_home = run_live_variant(
                variant="baseline",
                launchers=launchers,
                workspace=baseline_workspace,
                run_dir=baseline_dir,
                effort=args.effort,
                timeout_seconds=args.timeout_seconds,
                model=None,
                model_provider=None,
                service_tier=None,
                session_config=baseline_config,
                app_server_command=baseline_app_server_command,
            )
            if base.normalized_path(baseline_home) != base.normalized_path(codex_home):
                raise base.HarnessError("preflight and baseline used different Codex home directories.")
            baseline_eval = evaluate_run(
                turn=baseline_turn,
                workspace=baseline_workspace,
                run_dir=baseline_dir,
                initial_verification=initial_baseline,
                expected_head=seed_head,
                subject_version="disabled",
                subject_commit=None,
                harness_commit=harness_commit,
                campaign_id=campaign_id,
                client_version=client_version,
                node_executable=launchers.node_executable,
                disabled_skill_paths=baseline_disabled_skills,
                disabled_plugin_ids=baseline_plugin_ids,
                disabled_mcp_server_names=mcp_names,
                startup_config_overrides=baseline_startup_overrides,
                exposed_core_skills={},
            )

            print("[2/2] Installing core and running unprompted tiny-edit candidate...")
            installed_root = guard.install_candidate()
            candidate_plugin_ids = installed_plugin_ids(launchers)
            (
                candidate_app_server_command,
                candidate_startup_overrides,
            ) = build_isolated_app_server_command(
                launchers=launchers,
                installed_plugin_ids=candidate_plugin_ids,
                mcp_server_names=mcp_names,
                plugins_enabled=True,
                enabled_plugin_id=base.PLUGIN_ID,
            )
            with base.AppServer(
                command=candidate_app_server_command,
                node_executable=launchers.node_executable,
                cwd=candidate_workspace,
                trace_path=preflight_dir / "candidate-skills-trace.jsonl",
                timeout_seconds=args.timeout_seconds,
            ) as candidate_preflight:
                candidate_preflight_home = candidate_preflight.initialize()
                candidate_skills = candidate_preflight.skills_list(candidate_workspace)
            if base.normalized_path(candidate_preflight_home) != base.normalized_path(codex_home):
                raise base.HarnessError("candidate preflight used a different Codex home directory.")
            (
                candidate_config,
                exposed_core,
                candidate_disabled_skills,
                candidate_disabled_plugins,
            ) = build_candidate_session_config(
                skills=candidate_skills,
                installed_plugin_root=installed_root,
                mcp_server_names=mcp_names,
                installed_plugin_ids=candidate_plugin_ids,
            )
            candidate_turn, candidate_home = run_live_variant(
                variant="candidate",
                launchers=launchers,
                workspace=candidate_workspace,
                run_dir=candidate_dir,
                effort=args.effort,
                timeout_seconds=args.timeout_seconds,
                model=baseline_turn.model,
                model_provider=baseline_turn.model_provider,
                service_tier=baseline_turn.service_tier,
                session_config=candidate_config,
                app_server_command=candidate_app_server_command,
            )
            if base.normalized_path(candidate_home) != base.normalized_path(codex_home):
                raise base.HarnessError("baseline and candidate used different Codex home directories.")
            if (
                candidate_turn.model != baseline_turn.model
                or candidate_turn.model_provider != baseline_turn.model_provider
                or candidate_turn.service_tier != baseline_turn.service_tier
            ):
                raise base.HarnessError("baseline and candidate did not use identical model settings.")
            candidate_eval = evaluate_run(
                turn=candidate_turn,
                workspace=candidate_workspace,
                run_dir=candidate_dir,
                initial_verification=initial_candidate,
                expected_head=seed_head,
                subject_version=candidate_version,
                subject_commit=subject_commit,
                harness_commit=harness_commit,
                campaign_id=campaign_id,
                client_version=client_version,
                node_executable=launchers.node_executable,
                disabled_skill_paths=candidate_disabled_skills,
                disabled_plugin_ids=candidate_disabled_plugins,
                disabled_mcp_server_names=mcp_names,
                startup_config_overrides=candidate_startup_overrides,
                exposed_core_skills=exposed_core,
            )

            runs_path = campaign / "runs.jsonl"
            runs_path.write_text(
                "\n".join(
                    json.dumps(row, ensure_ascii=False, separators=(",", ":"))
                    for row in (baseline_eval.row, candidate_eval.row)
                )
                + "\n",
                encoding="utf-8",
                newline="\n",
            )

            invalid_reasons = [
                reason
                for evaluation in (baseline_eval, candidate_eval)
                for reason in evaluation.artifact["environment_findings"]
            ]
            if invalid_reasons:
                score_payload = {
                    "evidence_class": "LIVE",
                    "release_qualification": "NOT_ASSESSED",
                    "status": "INVALID",
                    "invalid_reasons": sorted(set(invalid_reasons)),
                    "note": "Ambient capabilities were not isolated; scorer was intentionally not run.",
                }
                (campaign / "score.json").write_text(
                    json.dumps(score_payload, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                    newline="\n",
                )
                outcome = "INVALID"
            else:
                score_result = base.run_process(
                    [sys.executable, str(base.SCORER_PATH), str(runs_path), "--json"],
                    cwd=base.ROOT,
                    expected={0, 1},
                )
                (campaign / "score.json").write_text(
                    score_result.stdout,
                    encoding="utf-8",
                    newline="\n",
                )
                score_payload = json.loads(score_result.stdout)
                if not isinstance(score_payload, dict):
                    raise base.HarnessError("scorer returned an invalid JSON payload.")
                outcome = "PASS" if score_result.returncode == 0 else "FAIL"

        assert guard is not None
        final_state = base.read_plugin_state(launchers, base.ROOT)
        original = guard.original
        state_restored = (
            final_state.marketplace_existed == original.marketplace_existed
            and final_state.plugin_installed == original.plugin_installed
            and final_state.plugin_enabled == original.plugin_enabled
            and final_state.plugin_version == original.plugin_version
        )
        if not state_restored:
            raise base.HarnessError("Codex plugin state was not restored to its original value.")
    except Exception as error:
        summary = {
            "campaign": campaign.name,
            "outcome": "HARNESS_ERROR",
            "error": str(error),
            "baseline": baseline_eval.artifact if baseline_eval else None,
            "candidate": candidate_eval.artifact if candidate_eval else None,
            "score": score_payload or None,
            "plugin_state_restored": state_restored,
            "evidence_boundary": "One authenticated negative-trigger repetition; not release qualification.",
        }
        (campaign / "summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        diagnostics_path, diagnostics = write_failure_diagnostics(
            campaign=campaign,
            outcome="HARNESS_ERROR",
            invalid_reasons=invalid_reasons,
            baseline=baseline_eval,
            candidate=candidate_eval,
            score=score_payload,
            plugin_state_restored=state_restored,
            error=str(error),
        )
        print_failure_diagnostics(diagnostics_path, diagnostics)
        raise

    assert baseline_eval is not None and candidate_eval is not None
    summary = {
        "campaign": campaign.name,
        "outcome": outcome,
        "invalid_reasons": sorted(set(invalid_reasons)),
        "baseline": baseline_eval.artifact,
        "candidate": candidate_eval.artifact,
        "score": score_payload,
        "plugin_state_restored": state_restored,
        "evidence_boundary": "One authenticated negative-trigger repetition; not release qualification.",
    }
    (campaign / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print_comparison(baseline_eval, candidate_eval, score_payload)
    if outcome != "PASS":
        diagnostics_path, diagnostics = write_failure_diagnostics(
            campaign=campaign,
            outcome=outcome,
            invalid_reasons=invalid_reasons,
            baseline=baseline_eval,
            candidate=candidate_eval,
            score=score_payload,
            plugin_state_restored=state_restored,
        )
        print_failure_diagnostics(diagnostics_path, diagnostics)
    print(f"\nArtifacts: {campaign}")
    if outcome == "PASS":
        print("Result: PASS (tiny edit did not trigger forbidden heavy workflows)")
        return 0
    if outcome == "INVALID":
        print("Result: INVALID (ambient capabilities were not fully isolated; no scorer claim)")
        return 1
    print("Result: FAIL (valid negative-trigger campaign; inspect summary.json and artifacts)")
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (
        base.HarnessError,
        OSError,
        subprocess.SubprocessError,
        json.JSONDecodeError,
    ) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(1)
