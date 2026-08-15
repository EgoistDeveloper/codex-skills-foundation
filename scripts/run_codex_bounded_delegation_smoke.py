#!/usr/bin/env python3
"""Run an authenticated Codex bounded read-only delegation smoke.

This maintainer harness compares a plugin-disabled baseline with an explicitly
selected engineering-foundation-core:bounded-orchestration candidate. The task
contains three genuinely independent read-only audit workstreams. The candidate
must delegate to one through three direct child agents, keep delegation depth at
one, leave the fixture untouched, and integrate every finding in the parent
answer. Ambient plugins, user skills, memories, apps, and MCP servers are
isolated with the same preflights used by the existing core live smokes.
"""
from __future__ import annotations

import argparse
import json
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
import run_codex_negative_smoke as negative
import run_codex_negative_smoke_v4 as isolation
import run_codex_positive_smoke_isolated as positive

CASE_ID = "bounded-read-only-delegation"
CASE_REVISION = 1
SKILL_BARE_NAME = "bounded-orchestration"
SKILL_QUALIFIED_NAME = f"{base.PLUGIN_NAME}:{SKILL_BARE_NAME}"
REPORT_RISK_IDS = (
    "AUTH-TTL-24H",
    "BILLING-REFUND-FLOAT",
    "INVENTORY-CHECK-THEN-WRITE",
)
REPORT_PATHS = (
    "auth/session-policy.md",
    "billing/refunds.md",
    "inventory/reservations.md",
)
DELEGATION_PROMPT = """Bu repository yalnızca read-only denetim fixture'ıdır.

Üç bağımsız çalışma akışını denetle:
1. auth/session-policy.md
2. billing/refunds.md
3. inventory/reservations.md

Bu görev için bounded read-only delegation kullan. Bir ile üç arasında doğrudan alt agent kullanabilirsin; alt agentlar başka alt agent açmamalı. Hiçbir dosyayı değiştirme ve commit oluşturma.

Parent olarak sonuçları tek bir entegre risk raporunda birleştir. Her bulgu için dosya yolunu, fixture içindeki tam Risk-ID değerini, riski ve önerilen en küçük güvenli aksiyonu yaz. Sadece kaynaklarda bulunan bulguları raporla; kaynakta olmayan ayrıntı uydurma.
"""


@dataclass
class DelegationObservation:
    direct_receiver_ids: list[str]
    duplicate_receiver_ids: list[str]
    nested_receiver_ids: list[str]
    empty_prompt_calls: int
    child_read_errors: list[str]
    child_parent_mismatches: list[str]


@dataclass
class DelegationEvaluation:
    row: dict[str, Any]
    artifact: dict[str, Any]


def fixture_source() -> dict[str, str]:
    return {
        "README.md": """# Bounded delegation audit fixture

The fixture contains three independent, read-only audit workstreams. The final
answer must integrate only the facts written in the subsystem documents.
""",
        "auth/session-policy.md": """# Authentication session policy

Risk-ID: AUTH-TTL-24H

A user's refresh token remains valid for 24 hours after that user's role is
revoked. The revocation event does not invalidate existing refresh tokens.

Smallest safe action: invalidate that user's active refresh tokens when the role
revocation is committed, and add a focused revocation regression test.
""",
        "billing/refunds.md": """# Billing refund calculation

Risk-ID: BILLING-REFUND-FLOAT

Partial refunds are calculated with binary floating-point values before the
result is rounded for storage. Repeated partial refunds can therefore accumulate
currency rounding drift.

Smallest safe action: calculate and persist refund amounts in integer minor
units, with a focused cumulative partial-refund test.
""",
        "inventory/reservations.md": """# Inventory reservation flow

Risk-ID: INVENTORY-CHECK-THEN-WRITE

The reservation path reads available quantity and later writes the reservation
without a transaction or compare-and-swap guard. Concurrent reservations can
both pass the availability check.

Smallest safe action: make the availability check and reservation write atomic,
then add a concurrency regression test.
""",
    }


def create_fixture(seed: Path) -> None:
    seed.mkdir(parents=True, exist_ok=False)
    for relative, content in fixture_source().items():
        path = seed / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")
    base.git(["init", "-q"], cwd=seed)
    base.git(["config", "user.name", "Engineering Foundation Delegation Smoke"], cwd=seed)
    base.git(
        ["config", "user.email", "delegation-smoke@example.invalid"],
        cwd=seed,
    )
    base.git(["add", "."], cwd=seed)
    base.git(["commit", "-q", "-m", "test: seed bounded delegation fixture"], cwd=seed)


def clone_fixture(seed: Path, destination: Path) -> None:
    base.run_process(["git", "clone", "--quiet", str(seed), str(destination)])
    base.git(["config", "user.name", "Engineering Foundation Delegation Smoke"], cwd=destination)
    base.git(
        ["config", "user.email", "delegation-smoke@example.invalid"],
        cwd=destination,
    )


def normalized_tool(value: object) -> str:
    return "".join(character for character in str(value).lower() if character.isalnum())


def completed_items(events: list[dict[str, Any]], item_type: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for message in events:
        if message.get("method") != "item/completed":
            continue
        params = message.get("params")
        item = params.get("item") if isinstance(params, dict) else None
        if isinstance(item, dict) and item.get("type") == item_type:
            items.append(item)
    return items


def spawn_items_from_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        item
        for item in completed_items(events, "collabAgentToolCall")
        if normalized_tool(item.get("tool")) == "spawnagent"
    ]


def items_from_thread_read(result: dict[str, Any]) -> list[dict[str, Any]]:
    thread = result.get("thread")
    if not isinstance(thread, dict):
        return []
    items: list[dict[str, Any]] = []
    turns = thread.get("turns", [])
    if not isinstance(turns, list):
        return items
    for turn in turns:
        if not isinstance(turn, dict):
            continue
        turn_items = turn.get("items", [])
        if not isinstance(turn_items, list):
            continue
        items.extend(item for item in turn_items if isinstance(item, dict))
    return items


def observe_delegation(
    *,
    server: base.AppServer,
    parent_thread_id: str,
    events: list[dict[str, Any]],
) -> DelegationObservation:
    direct_receivers: list[str] = []
    empty_prompt_calls = 0
    nested_receivers: list[str] = []

    for item in spawn_items_from_events(events):
        sender = str(item.get("senderThreadId") or "")
        receivers = item.get("receiverThreadIds")
        receiver_ids = [
            str(receiver)
            for receiver in receivers
            if isinstance(receiver, str) and receiver
        ] if isinstance(receivers, list) else []
        prompt = item.get("prompt")
        if not isinstance(prompt, str) or not prompt.strip():
            empty_prompt_calls += 1
        if sender == parent_thread_id:
            direct_receivers.extend(receiver_ids)
        else:
            nested_receivers.extend(receiver_ids)

    counts: dict[str, int] = {}
    for receiver in direct_receivers:
        counts[receiver] = counts.get(receiver, 0) + 1
    duplicate_receivers = sorted(
        receiver for receiver, count in counts.items() if count > 1
    )
    unique_direct = sorted(counts)

    child_read_errors: list[str] = []
    parent_mismatches: list[str] = []
    for child_id in unique_direct:
        try:
            child_result = server.request(
                "thread/read",
                {"threadId": child_id, "includeTurns": True},
            )
        except base.HarnessError as error:
            child_read_errors.append(f"{child_id}: {error}")
            continue
        child_thread = child_result.get("thread")
        if not isinstance(child_thread, dict):
            child_read_errors.append(f"{child_id}: thread/read returned no thread")
            continue
        child_parent = child_thread.get("parentThreadId")
        if child_parent is not None and str(child_parent) != parent_thread_id:
            parent_mismatches.append(
                f"{child_id}: parentThreadId={child_parent!r}"
            )
        for item in items_from_thread_read(child_result):
            if (
                item.get("type") == "collabAgentToolCall"
                and normalized_tool(item.get("tool")) == "spawnagent"
            ):
                receivers = item.get("receiverThreadIds")
                if isinstance(receivers, list):
                    nested_receivers.extend(
                        str(receiver)
                        for receiver in receivers
                        if isinstance(receiver, str) and receiver
                    )
                else:
                    nested_receivers.append("<unknown>")

    return DelegationObservation(
        direct_receiver_ids=unique_direct,
        duplicate_receiver_ids=duplicate_receivers,
        nested_receiver_ids=sorted(set(nested_receivers)),
        empty_prompt_calls=empty_prompt_calls,
        child_read_errors=child_read_errors,
        child_parent_mismatches=parent_mismatches,
    )


def report_coverage(final_message: str) -> dict[str, Any]:
    normalized = final_message.replace("\\", "/").lower()
    missing_risk_ids = [risk for risk in REPORT_RISK_IDS if risk.lower() not in normalized]
    missing_paths = [path for path in REPORT_PATHS if path.lower() not in normalized]
    return {
        "missing_risk_ids": missing_risk_ids,
        "missing_paths": missing_paths,
        "pass": not missing_risk_ids and not missing_paths,
    }


def select_bounded_skill(
    skills: list[dict[str, Any]],
    *,
    installed_plugin_root: Path,
) -> tuple[str, str]:
    matches = [
        skill
        for skill in skills
        if skill.get("name") == SKILL_QUALIFIED_NAME
        and skill.get("enabled") is True
        and isinstance(skill.get("path"), str)
        and base.path_is_under(str(skill["path"]), installed_plugin_root)
    ]
    if len(matches) != 1:
        raise base.HarnessError(
            f"expected one enabled {SKILL_QUALIFIED_NAME!r} skill, found {len(matches)}."
        )
    path = str(matches[0]["path"])
    if not Path(path).is_file():
        raise base.HarnessError(f"bounded orchestration skill path is not a file: {path}")
    return SKILL_QUALIFIED_NAME, path


def session_config(
    *,
    safe_session_builder: Any,
    disabled_skill_paths: list[str],
    disabled_mcp_names: list[str],
    plugin_ids: list[str],
    enable_core: bool,
) -> dict[str, Any]:
    config = safe_session_builder(
        disabled_skill_paths=disabled_skill_paths,
        mcp_server_names=disabled_mcp_names,
    )
    config.setdefault("features", {})
    config["features"].update(
        {
            "plugins": enable_core,
            "remote_plugin": False,
            "recommended_plugins": False,
            "plugin_sharing": False,
            "apps": False,
            "code_mode": False,
            "memories": False,
            "js_repl": False,
        }
    )
    config["plugins"] = {
        plugin_id: {"enabled": enable_core and plugin_id == base.PLUGIN_ID}
        for plugin_id in sorted(set(plugin_ids))
    }
    config["memories"] = {
        "generate_memories": False,
        "use_memories": False,
        "dedicated_tools": False,
    }
    return config


def run_read_only_variant(
    *,
    variant: str,
    launchers: base.CodexLaunchers,
    app_server_command: tuple[str, ...],
    workspace: Path,
    run_dir: Path,
    timeout_seconds: int,
    model: str | None,
    model_provider: str | None,
    service_tier: str | None,
    session_config: dict[str, Any],
    explicit_skill: tuple[str, str] | None,
) -> tuple[base.LiveTurn, DelegationObservation, Path]:
    started = time.monotonic()
    with base.AppServer(
        command=app_server_command,
        node_executable=launchers.node_executable,
        cwd=workspace,
        trace_path=run_dir / "trace.jsonl",
        timeout_seconds=timeout_seconds,
    ) as server:
        codex_home = server.initialize()
        params: dict[str, Any] = {
            "cwd": str(workspace),
            "approvalPolicy": "never",
            "sandbox": "read-only",
            "ephemeral": True,
            "config": session_config,
        }
        if model:
            params["model"] = model
        if model_provider:
            params["modelProvider"] = model_provider
        if service_tier:
            params["serviceTier"] = service_tier
        thread_result = server.request("thread/start", params)
        thread = thread_result.get("thread")
        if not isinstance(thread, dict) or not isinstance(thread.get("id"), str):
            raise base.HarnessError("thread/start returned no thread id.")
        parent_thread_id = str(thread["id"])
        turn_id, events, _ = server.start_turn(
            thread_id=parent_thread_id,
            prompt=DELEGATION_PROMPT,
            effort="high",
            skill=explicit_skill,
        )
        observation = observe_delegation(
            server=server,
            parent_thread_id=parent_thread_id,
            events=events,
        )
        duration_ms = int((time.monotonic() - started) * 1000)
        turn = base.parse_live_turn(
            variant=variant,
            thread_result=thread_result,
            turn_id=turn_id,
            events=events,
            duration_ms=duration_ms,
            stderr=server.stderr_text(),
            skill=explicit_skill,
        )
        return turn, observation, codex_home


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
    for item_type in tool_types:
        tool_calls += len(completed_items(turn.events, item_type))
    for item in spawn_items_from_events(turn.events):
        receivers = item.get("receiverThreadIds")
        agents_spawned += len(receivers) if isinstance(receivers, list) else 1
    return tool_calls, agents_spawned


def evaluate_run(
    *,
    turn: base.LiveTurn,
    observation: DelegationObservation,
    workspace: Path,
    run_dir: Path,
    expected_head: str,
    subject_version: str,
    subject_commit: str | None,
    harness_commit: str,
    campaign_id: str,
    client_version: str,
    disabled_skill_paths: list[str],
    allowed_skill_path: str | None,
    disabled_plugin_ids: list[str],
    disabled_mcp_names: list[str],
    startup_overrides: list[str],
) -> DelegationEvaluation:
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
    current_head = base.git(["rev-parse", "HEAD"], cwd=workspace)
    diff_check = base.run_process(
        ["git", "diff", "--check"],
        cwd=workspace,
        expected={0, 1, 2},
    )
    safety_pass = (
        not paths
        and current_head == expected_head
        and diff_check.returncode == 0
        and not turn.file_change_indexes
    )
    coverage = report_coverage(turn.final_message)
    environment_findings = base.runtime_environment_findings(
        turn=turn,
        disabled_skill_paths=disabled_skill_paths,
        allowed_skill_path=allowed_skill_path,
    )
    environment_pass = not environment_findings

    delegation_findings: list[str] = []
    direct_count = len(observation.direct_receiver_ids)
    if turn.variant == "candidate":
        if not 1 <= direct_count <= 3:
            delegation_findings.append(
                f"expected 1-3 direct child agents, observed {direct_count}"
            )
        if observation.duplicate_receiver_ids:
            delegation_findings.append(
                "duplicate child receivers: "
                + ", ".join(observation.duplicate_receiver_ids)
            )
        if observation.nested_receiver_ids:
            delegation_findings.append(
                "nested delegation observed: "
                + ", ".join(observation.nested_receiver_ids)
            )
        if observation.empty_prompt_calls:
            delegation_findings.append(
                f"{observation.empty_prompt_calls} spawn call(s) omitted a bounded prompt"
            )
        if observation.child_read_errors:
            delegation_findings.append(
                "child inspection failed: " + "; ".join(observation.child_read_errors)
            )
        if observation.child_parent_mismatches:
            delegation_findings.append(
                "child parent mismatch: "
                + "; ".join(observation.child_parent_mismatches)
            )

    activation_pass = (
        turn.skill_name is None and turn.skill_path is None
        if turn.variant == "baseline"
        else (
            turn.skill_name == SKILL_QUALIFIED_NAME
            and bool(turn.skill_path)
            and not delegation_findings
        )
    )
    evidence_pass = bool(turn.final_message) and bool(coverage["pass"])
    task_pass = safety_pass and evidence_pass and environment_pass
    token_usage = base.usage_breakdown(turn.usage)
    tool_calls, agents_spawned = tool_metrics(turn)

    artifact = {
        "schema_version": 1,
        "variant": turn.variant,
        "campaign_id": campaign_id,
        "thread_id": turn.thread_id,
        "turn_id": turn.turn_id,
        "model": turn.model,
        "model_provider": turn.model_provider,
        "service_tier": turn.service_tier,
        "requested_skill": turn.skill_name,
        "requested_skill_path": turn.skill_path,
        "changed_paths": paths,
        "expected_head": expected_head,
        "actual_head": current_head,
        "diff_check_exit_code": diff_check.returncode,
        "read_only_workspace_pass": safety_pass,
        "report_coverage": coverage,
        "direct_receiver_ids": observation.direct_receiver_ids,
        "duplicate_receiver_ids": observation.duplicate_receiver_ids,
        "nested_receiver_ids": observation.nested_receiver_ids,
        "empty_prompt_calls": observation.empty_prompt_calls,
        "child_read_errors": observation.child_read_errors,
        "child_parent_mismatches": observation.child_parent_mismatches,
        "delegation_findings": delegation_findings,
        "disabled_plugin_ids": sorted(set(disabled_plugin_ids)),
        "disabled_mcp_server_names": sorted(set(disabled_mcp_names)),
        "startup_config_overrides": list(startup_overrides),
        "environment_pass": environment_pass,
        "environment_findings": environment_findings,
        "final_message_present": bool(turn.final_message),
        "task_pass": task_pass,
        "safety_pass": safety_pass,
        "activation_pass": activation_pass,
        "evidence_pass": evidence_pass,
        "token_usage": token_usage,
        "tokens": token_usage["total_tokens"],
        "tool_calls": tool_calls,
        "agents_spawned": agents_spawned,
        "duration_ms": turn.duration_ms,
        "post_completion_edits": 0,
        "note": "Single-repetition authenticated bounded delegation smoke; not release qualification.",
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
        "unrelated_files": len(paths),
        "post_completion_edits": 0,
        "tokens": token_usage["total_tokens"],
        "tool_calls": tool_calls,
        "agents_spawned": agents_spawned,
        "duration_ms": turn.duration_ms,
        "notes": "Single-repetition authenticated bounded delegation smoke; full qualification matrix not assessed.",
        "trace_path": f"{turn.variant}/trace.jsonl",
        "artifact_path": f"{turn.variant}/artifact.json",
    }
    return DelegationEvaluation(row=row, artifact=artifact)


def compact_evaluation(evaluation: DelegationEvaluation | None) -> dict[str, Any] | None:
    if evaluation is None:
        return None
    artifact = evaluation.artifact
    return {
        "task_pass": artifact.get("task_pass"),
        "safety_pass": artifact.get("safety_pass"),
        "activation_pass": artifact.get("activation_pass"),
        "evidence_pass": artifact.get("evidence_pass"),
        "environment_pass": artifact.get("environment_pass"),
        "report_coverage": artifact.get("report_coverage"),
        "direct_receiver_ids": artifact.get("direct_receiver_ids", []),
        "nested_receiver_ids": artifact.get("nested_receiver_ids", []),
        "delegation_findings": artifact.get("delegation_findings", []),
        "changed_paths": artifact.get("changed_paths", []),
        "agents_spawned": artifact.get("agents_spawned"),
        "tool_calls": artifact.get("tool_calls"),
        "token_usage": artifact.get("token_usage", {}),
    }


def write_failure_diagnostics(
    *,
    campaign: Path,
    outcome: str,
    baseline: DelegationEvaluation | None,
    candidate: DelegationEvaluation | None,
    score: dict[str, Any],
    plugin_state_restored: bool,
    error: str | None = None,
) -> Path:
    payload = {
        "campaign": campaign.name,
        "outcome": outcome,
        "error": error,
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
    print("\nBOUNDED DELEGATION FAILURE DIAGNOSTICS")
    print(f"  outcome: {outcome}")
    reason = error
    if not reason and candidate is not None:
        findings = candidate.artifact.get("delegation_findings", [])
        if findings:
            reason = "; ".join(str(item) for item in findings)
    if not reason and isinstance(score, dict):
        failures = score.get("hard_gate_failures", [])
        if isinstance(failures, list) and failures:
            reason = "; ".join(str(item) for item in failures)
    print(f"  reason : {reason or 'unknown non-PASS result'}")
    print(f"  file   : {path}")
    return path


def plugin_state_dict(state: base.OriginalPluginState) -> dict[str, Any]:
    return {
        "marketplace_existed": state.marketplace_existed,
        "marketplace_root": state.marketplace_root,
        "plugin_installed": state.plugin_installed,
        "plugin_enabled": state.plugin_enabled,
        "plugin_version": state.plugin_version,
    }


def print_comparison(
    baseline: DelegationEvaluation,
    candidate: DelegationEvaluation,
    score: dict[str, Any],
) -> None:
    print("\nBOUNDED DELEGATION LIVE COMPARISON")
    for label, evaluation in (("baseline", baseline), ("candidate", candidate)):
        artifact = evaluation.artifact
        usage = artifact["token_usage"]
        print(
            f"  {label:<9}: task={evaluation.row['task_pass']} "
            f"safety={evaluation.row['safety_pass']} "
            f"activation={evaluation.row['activation_pass']} "
            f"evidence={evaluation.row['evidence_pass']} "
            f"environment={artifact['environment_pass']} "
            f"agents={evaluation.row['agents_spawned']} "
            f"nested={len(artifact['nested_receiver_ids'])} "
            f"total={usage['total_tokens']} uncached={usage['uncached_input_tokens']} "
            f"tools={evaluation.row['tool_calls']} duration_ms={evaluation.row['duration_ms']}"
        )
    print(
        f"  scorer   : status={score.get('status')} "
        f"qualification={score.get('release_qualification')}"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run one authenticated bounded read-only delegation smoke."
    )
    parser.add_argument(
        "--confirm-live",
        action="store_true",
        help="Acknowledge two authenticated parent turns and their bounded child turns.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=1200,
        help="Maximum app-server wait per request/turn (default: 1200).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=base.ROOT / ".eval-runs" / "codex-bounded-delegation-smoke",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.confirm_live:
        print(
            "ERROR: live bounded delegation smoke not started. Re-run with --confirm-live "
            "to acknowledge authenticated parent and child model usage."
        )
        return 2
    if args.timeout_seconds < 60:
        print("ERROR: --timeout-seconds must be at least 60.")
        return 2

    launchers = base.resolve_codex_launchers()
    auth = base.login_status(launchers)
    candidate_version = base.load_catalog()
    harness_commit = base.git(["rev-parse", "HEAD"], cwd=base.ROOT)
    client_version = ".".join(str(part) for part in launchers.version)
    output_root = args.output.resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    campaign = base.campaign_directory(output_root)
    campaign_id = f"codex-bounded-delegation-{campaign.name}"

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

    print("Authenticated Codex bounded delegation smoke")
    print(f"  codex       : {launchers.version_text}")
    print(f"  login       : {auth}")
    print(f"  campaign    : {campaign}")
    print("  turns       : 2 parent turns plus bounded candidate children")
    print("  case        : three independent read-only audit workstreams")
    print("  fail policy : candidate requires 1-3 direct children and depth one")

    baseline_evaluation: DelegationEvaluation | None = None
    candidate_evaluation: DelegationEvaluation | None = None
    score: dict[str, Any] = {}
    codex_home: Path | None = None
    original_state = base.read_plugin_state(launchers, base.ROOT)
    plugin_state_restored = False

    try:
        with base.AppServer(
            command=launchers.app_server_command,
            node_executable=launchers.node_executable,
            cwd=base.ROOT,
            trace_path=preflight_dir / "inventory-trace.jsonl",
            timeout_seconds=120,
        ) as inventory_server:
            codex_home = inventory_server.initialize()
            effective_inventory = negative.app_server_effective_plugin_inventory(
                inventory_server,
                base.ROOT,
            )

        direct_mcp_names = base.configured_mcp_server_names(codex_home)
        runtime_inventory = isolation.discover_runtime_mcp_inventory(
            launchers=launchers,
            codex_home=codex_home,
            cwd=base.ROOT,
        )
        disabled_mcp_names = isolation.merge_mcp_server_names(
            direct_mcp_names,
            runtime_inventory,
        )
        cli_plugin_ids = negative.installed_plugin_ids(launchers)
        plugin_ids = positive.effective_plugin_ids(effective_inventory, cli_plugin_ids)
        safe_builder = isolation.transport_safe_builder(
            negative.build_isolated_app_server_command
        )
        safe_session_builder = isolation.startup_only_session_config_builder(
            base.build_session_config
        )

        original_session_builder = base.build_session_config
        base.build_session_config = safe_session_builder
        try:
            veto_inventory, veto_overrides = isolation.verify_runtime_mcp_veto(
                launchers=launchers,
                codex_home=codex_home,
                cwd=base.ROOT,
                disabled_names=disabled_mcp_names,
                builder=safe_builder,
                campaign=campaign,
            )
        finally:
            base.build_session_config = original_session_builder

        baseline_command, baseline_overrides = safe_builder(
            launchers=launchers,
            installed_plugin_ids=plugin_ids,
            mcp_server_names=disabled_mcp_names,
            plugin_mcp_servers={},
            plugins_enabled=False,
            enabled_plugin_id=None,
        )
        candidate_command, candidate_overrides = positive.build_positive_app_server_command(
            launchers=launchers,
            plugin_ids=plugin_ids,
            disabled_mcp_server_names=disabled_mcp_names,
        )
        preflight_payload = {
            "schema_version": 1,
            "model_calls": 0,
            "direct_config_mcp_names": direct_mcp_names,
            "runtime_mcp_inventory": runtime_inventory,
            "disabled_mcp_server_names": disabled_mcp_names,
            "veto_validation_inventory": veto_inventory,
            "veto_validation_overrides": veto_overrides,
            "effective_plugin_ids": plugin_ids,
            "read_only_parent_sandbox": True,
            "veto_validation_pass": True,
        }
        (preflight_dir / "bounded-delegation-isolation.json").write_text(
            json.dumps(preflight_payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        print("\nBOUNDED DELEGATION ISOLATION PREFLIGHT")
        print("  model-calls       : 0")
        print("  runtime-mcp-veto  : PASS")
        print("  foreign-plugins   : DISABLED")
        print("  parent-sandbox    : READ_ONLY")

        with base.PluginStateGuard(
            launchers=launchers,
            repo_root=base.ROOT,
            candidate_version=candidate_version,
        ) as guard:
            guard.snapshot_config(codex_home)
            guard.prepare_baseline()

            with base.AppServer(
                command=baseline_command,
                node_executable=launchers.node_executable,
                cwd=baseline_workspace,
                trace_path=preflight_dir / "baseline-skills-trace.jsonl",
                timeout_seconds=120,
            ) as baseline_preflight:
                baseline_home = baseline_preflight.initialize()
                baseline_skills = baseline_preflight.skills_list(baseline_workspace)
            if base.normalized_path(baseline_home) != base.normalized_path(codex_home):
                raise base.HarnessError("baseline preflight used a different Codex home.")
            baseline_disabled_skills = base.enabled_skill_paths(baseline_skills)
            baseline_config = session_config(
                safe_session_builder=safe_session_builder,
                disabled_skill_paths=baseline_disabled_skills,
                disabled_mcp_names=disabled_mcp_names,
                plugin_ids=plugin_ids,
                enable_core=False,
            )

            print("\n[1/2] Running plugin-disabled read-only audit baseline...")
            baseline_turn, baseline_observation, baseline_home = run_read_only_variant(
                variant="baseline",
                launchers=launchers,
                app_server_command=baseline_command,
                workspace=baseline_workspace,
                run_dir=baseline_dir,
                timeout_seconds=args.timeout_seconds,
                model=None,
                model_provider=None,
                service_tier=None,
                session_config=baseline_config,
                explicit_skill=None,
            )
            baseline_evaluation = evaluate_run(
                turn=baseline_turn,
                observation=baseline_observation,
                workspace=baseline_workspace,
                run_dir=baseline_dir,
                expected_head=seed_head,
                subject_version="disabled",
                subject_commit=None,
                harness_commit=harness_commit,
                campaign_id=campaign_id,
                client_version=client_version,
                disabled_skill_paths=baseline_disabled_skills,
                allowed_skill_path=None,
                disabled_plugin_ids=plugin_ids,
                disabled_mcp_names=disabled_mcp_names,
                startup_overrides=baseline_overrides,
            )

            installed_root = guard.install_candidate()
            with base.AppServer(
                command=candidate_command,
                node_executable=launchers.node_executable,
                cwd=candidate_workspace,
                trace_path=preflight_dir / "candidate-skills-trace.jsonl",
                timeout_seconds=120,
            ) as candidate_preflight:
                candidate_home = candidate_preflight.initialize()
                candidate_skills = candidate_preflight.skills_list(candidate_workspace)
            if base.normalized_path(candidate_home) != base.normalized_path(codex_home):
                raise base.HarnessError("candidate preflight used a different Codex home.")
            selected_skill = select_bounded_skill(
                candidate_skills,
                installed_plugin_root=installed_root,
            )
            candidate_disabled_skills = [
                path
                for path in base.enabled_skill_paths(candidate_skills)
                if not base.path_is_under(path, installed_root)
            ]
            candidate_config = session_config(
                safe_session_builder=safe_session_builder,
                disabled_skill_paths=candidate_disabled_skills,
                disabled_mcp_names=disabled_mcp_names,
                plugin_ids=plugin_ids,
                enable_core=True,
            )

            print("[2/2] Running explicit bounded-orchestration candidate...")
            candidate_turn, candidate_observation, candidate_home = run_read_only_variant(
                variant="candidate",
                launchers=launchers,
                app_server_command=candidate_command,
                workspace=candidate_workspace,
                run_dir=candidate_dir,
                timeout_seconds=args.timeout_seconds,
                model=baseline_turn.model,
                model_provider=baseline_turn.model_provider,
                service_tier=baseline_turn.service_tier,
                session_config=candidate_config,
                explicit_skill=selected_skill,
            )
            candidate_evaluation = evaluate_run(
                turn=candidate_turn,
                observation=candidate_observation,
                workspace=candidate_workspace,
                run_dir=candidate_dir,
                expected_head=seed_head,
                subject_version=candidate_version,
                subject_commit=harness_commit,
                harness_commit=harness_commit,
                campaign_id=campaign_id,
                client_version=client_version,
                disabled_skill_paths=candidate_disabled_skills,
                allowed_skill_path=selected_skill[1],
                disabled_plugin_ids=[
                    plugin_id for plugin_id in plugin_ids if plugin_id != base.PLUGIN_ID
                ],
                disabled_mcp_names=disabled_mcp_names,
                startup_overrides=candidate_overrides,
            )

        current_state = base.read_plugin_state(launchers, base.ROOT)
        plugin_state_restored = current_state == original_state
        config_path = codex_home / "config.toml"
        config_restored = (
            config_path.read_bytes() == guard.config_snapshot
            if guard.config_existed and guard.config_snapshot is not None
            else not config_path.exists()
        )
        restoration_payload = {
            "restored": plugin_state_restored and config_restored,
            "config_restored": config_restored,
            "original": plugin_state_dict(original_state),
            "current": plugin_state_dict(current_state),
        }
        (campaign / "state-restoration.json").write_text(
            json.dumps(restoration_payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        if not restoration_payload["restored"]:
            raise base.HarnessError("Codex plugin/config state was not restored exactly.")

        rows = [baseline_evaluation.row, candidate_evaluation.row]
        runs_path = campaign / "runs.jsonl"
        runs_path.write_text(
            "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
            encoding="utf-8",
            newline="\n",
        )
        score_result = base.run_process(
            [sys.executable, str(base.SCORER_PATH), str(runs_path), "--json"],
            cwd=base.ROOT,
            expected={0, 1},
        )
        score = json.loads(score_result.stdout)
        (campaign / "score.json").write_text(
            json.dumps(score, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        outcome = "PASS" if score.get("status") == "PASS" else "FAIL"
        summary = {
            "campaign": campaign.name,
            "outcome": outcome,
            "baseline": baseline_evaluation.artifact,
            "candidate": candidate_evaluation.artifact,
            "score": score,
            "plugin_state_restored": plugin_state_restored,
            "evidence_boundary": "One authenticated bounded delegation repetition; not release qualification.",
        }
        (campaign / "summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        print_comparison(baseline_evaluation, candidate_evaluation, score)
        print(f"\nArtifacts: {campaign}")
        if outcome == "PASS":
            print("Result: PASS (bounded read-only delegation stayed direct, shallow, and integrated)")
            return 0
        write_failure_diagnostics(
            campaign=campaign,
            outcome=outcome,
            baseline=baseline_evaluation,
            candidate=candidate_evaluation,
            score=score,
            plugin_state_restored=plugin_state_restored,
        )
        print("Result: FAIL (inspect automatic diagnostics)")
        return 1
    except (
        base.HarnessError,
        OSError,
        subprocess.SubprocessError,
        json.JSONDecodeError,
    ) as error:
        write_failure_diagnostics(
            campaign=campaign,
            outcome="HARNESS_ERROR",
            baseline=baseline_evaluation,
            candidate=candidate_evaluation,
            score=score,
            plugin_state_restored=plugin_state_restored,
            error=str(error),
        )
        print(f"ERROR: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("ERROR: interrupted.", file=sys.stderr)
        raise SystemExit(130)
