#!/usr/bin/env python3
"""Run bounded delegation smoke revision 3.

Revisions 1 and 2 observed only the legacy V1 `collabAgentToolCall` event.
Codex CLI 0.147.0 selects MultiAgentV2 for gpt-5.6-sol, where a successful
spawn is surfaced as `subAgentActivity`. Revision 3 pins the supported V2
surface, observes both protocols, reads every direct child thread, rejects
nested fan-out, and can inspect an existing campaign without model calls.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any, Iterable

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import run_codex_bounded_delegation_smoke as delegation

CASE_REVISION = 3
DELEGATION_PROMPT = """Bu repository yalnızca read-only denetim fixture'ıdır.

Üç bağımsız çalışma akışını denetle:
1. auth/session-policy.md
2. billing/refunds.md
3. inventory/reservations.md

Bu pozitif aktivasyon testinde native V2 `spawn_agent` aracını kullanmak zorunludur. En az bir, en fazla üç doğrudan child agent oluştur; bağımsız dosya denetimlerinden en az birini child agente devretmeden parent olarak bütün işi tek başına tamamlama. Her child'a tek dosya veya tek çalışma akışı, açık non-goal, read-only sınırı, beklenen Risk-ID kanıtı ve stop condition içeren bounded bir görev ver. Child agentlar başka child açmamalı.

Hiçbir dosyayı değiştirme ve commit oluşturma. Parent olarak child sonuçlarını doğrula ve tek bir entegre risk raporunda birleştir. Her bulgu için dosya yolunu, fixture içindeki tam Risk-ID değerini, riski ve önerilen en küçük güvenli aksiyonu yaz. Sadece kaynaklarda bulunan bulguları raporla; kaynakta olmayan ayrıntı uydurma.
"""

_ORIGINAL_SESSION_CONFIG = delegation.session_config
_ORIGINAL_EVALUATE_RUN = delegation.evaluate_run
_ORIGINAL_RUN_VARIANT = delegation.run_read_only_variant
_ORIGINAL_TOOL_METRICS = delegation.tool_metrics


def normalized(value: object) -> str:
    return "".join(character for character in str(value).lower() if character.isalnum())


def event_items(
    events: Iterable[dict[str, Any]],
    *,
    item_type: str,
) -> list[dict[str, Any]]:
    expected = normalized(item_type)
    items: list[dict[str, Any]] = []
    for message in events:
        if message.get("method") != "item/completed":
            continue
        params = message.get("params")
        item = params.get("item") if isinstance(params, dict) else None
        if isinstance(item, dict) and normalized(item.get("type")) == expected:
            items.append(item)
    return items


def v1_spawn_items(events: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        item
        for item in event_items(events, item_type="collabAgentToolCall")
        if normalized(item.get("tool")) == "spawnagent"
        and normalized(item.get("status")) in {"completed", "inprogress"}
    ]


def v2_started_items(events: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        item
        for item in event_items(events, item_type="subAgentActivity")
        if normalized(item.get("kind")) == "started"
    ]


def agent_path_depth(agent_path: str) -> int | None:
    parts = [part for part in agent_path.split("/") if part]
    if not parts or parts[0] != "root":
        return None
    return len(parts) - 1


def strings_below(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        result: list[str] = []
        for item in value:
            result.extend(strings_below(item))
        return result
    if isinstance(value, dict):
        result = []
        for key in ("text", "message", "content", "fragments"):
            if key in value:
                result.extend(strings_below(value[key]))
        return result
    return []


def assignment_text(items: Iterable[dict[str, Any]]) -> str:
    fragments: list[str] = []
    for item in items:
        if normalized(item.get("type")) not in {"usermessage", "hookprompt"}:
            continue
        fragments.extend(strings_below(item))
    return "\n".join(fragment.strip() for fragment in fragments if fragment.strip())


def child_items(result: dict[str, Any]) -> list[dict[str, Any]]:
    return delegation.items_from_thread_read(result)


def classify_v2_activity(
    item: dict[str, Any],
) -> tuple[str | None, str | None, int | None]:
    thread_id = item.get("agentThreadId")
    path = item.get("agentPath")
    thread = str(thread_id) if isinstance(thread_id, str) and thread_id else None
    agent_path = str(path) if isinstance(path, str) and path else None
    return thread, agent_path, agent_path_depth(agent_path) if agent_path else None


def observe_delegation(
    *,
    server: delegation.base.AppServer,
    parent_thread_id: str,
    events: list[dict[str, Any]],
) -> delegation.DelegationObservation:
    direct_receivers: list[str] = []
    nested_receivers: list[str] = []
    empty_prompt_calls = 0
    protocols: set[str] = set()
    direct_paths: dict[str, str] = {}
    nested_paths: dict[str, str] = {}
    assignment_by_child: dict[str, str] = {}

    for item in v1_spawn_items(events):
        protocols.add("v1-collabAgentToolCall")
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

    for item in v2_started_items(events):
        protocols.add("v2-subAgentActivity")
        thread_id, agent_path, depth = classify_v2_activity(item)
        if thread_id is None:
            continue
        if depth == 1:
            direct_receivers.append(thread_id)
            if agent_path:
                direct_paths[thread_id] = agent_path
        else:
            nested_receivers.append(thread_id)
            if agent_path:
                nested_paths[thread_id] = agent_path

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
        except delegation.base.HarnessError as error:
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

        items = child_items(child_result)
        text = assignment_text(items)
        assignment_by_child[child_id] = text
        if "v2-subAgentActivity" in protocols and not text:
            empty_prompt_calls += 1

        for item in items:
            if (
                normalized(item.get("type")) == "collabagenttoolcall"
                and normalized(item.get("tool")) == "spawnagent"
            ):
                receivers = item.get("receiverThreadIds")
                if isinstance(receivers, list):
                    nested_receivers.extend(
                        str(receiver)
                        for receiver in receivers
                        if isinstance(receiver, str) and receiver
                    )
                else:
                    nested_receivers.append("<unknown-v1-child>")

            if (
                normalized(item.get("type")) == "subagentactivity"
                and normalized(item.get("kind")) == "started"
            ):
                nested_id, nested_path, _ = classify_v2_activity(item)
                if nested_id:
                    nested_receivers.append(nested_id)
                    if nested_path:
                        nested_paths[nested_id] = nested_path

    observation = delegation.DelegationObservation(
        direct_receiver_ids=unique_direct,
        duplicate_receiver_ids=duplicate_receivers,
        nested_receiver_ids=sorted(set(nested_receivers)),
        empty_prompt_calls=empty_prompt_calls,
        child_read_errors=child_read_errors,
        child_parent_mismatches=parent_mismatches,
    )
    observation.protocols = sorted(protocols)
    observation.direct_agent_paths = direct_paths
    observation.nested_agent_paths = nested_paths
    observation.assignment_text_by_child = assignment_by_child
    return observation


def session_config(
    *,
    safe_session_builder: Any,
    disabled_skill_paths: list[str],
    disabled_mcp_names: list[str],
    plugin_ids: list[str],
    enable_core: bool,
) -> dict[str, Any]:
    config = _ORIGINAL_SESSION_CONFIG(
        safe_session_builder=safe_session_builder,
        disabled_skill_paths=disabled_skill_paths,
        disabled_mcp_names=disabled_mcp_names,
        plugin_ids=plugin_ids,
        enable_core=enable_core,
    )
    features = config.setdefault("features", {})
    if not isinstance(features, dict):
        raise delegation.base.HarnessError("session features must be an object.")
    features["multi_agent"] = True
    features["multi_agent_v2"] = {
        "enabled": True,
        "max_concurrent_threads_per_session": 3,
        "root_agent_usage_hint_text": (
            "The user and selected bounded-orchestration skill explicitly require "
            "native spawn_agent delegation for this turn. Spawn one to three direct "
            "read-only children and integrate their evidence in the parent."
        ),
        "subagent_usage_hint_text": (
            "You are a depth-one read-only child. Do not spawn another agent. "
            "Return only source-backed findings for your assigned scope."
        ),
        "subagent_developer_instructions": (
            "Remain read-only, do not delegate, and stop after returning the exact "
            "Risk-ID, source path, risk, and smallest safe action for your assignment."
        ),
        "multi_agent_mode_hint_text": (
            "This turn is an explicit positive delegation request. Use spawn_agent "
            "for at least one independent workstream; keep all children directly "
            "under the root agent and never create nested agents."
        ),
        "wait_agent_enabled": True,
        "non_code_mode_only": True,
    }
    config["agents"] = {
        "enabled": True,
        "max_concurrent_threads_per_session": 3,
        "max_depth": 1,
    }
    config["include_collaboration_mode_instructions"] = True
    return config


def run_read_only_variant(
    *,
    variant: str,
    launchers: delegation.base.CodexLaunchers,
    app_server_command: tuple[str, ...],
    workspace: Path,
    run_dir: Path,
    timeout_seconds: int,
    model: str | None,
    model_provider: str | None,
    service_tier: str | None,
    session_config: dict[str, Any],
    explicit_skill: tuple[str, str] | None,
) -> tuple[delegation.base.LiveTurn, delegation.DelegationObservation, Path]:
    started = time.monotonic()
    with delegation.base.AppServer(
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
            raise delegation.base.HarnessError("thread/start returned no thread id.")
        parent_thread_id = str(thread["id"])
        turn_id, events, _ = server.start_turn(
            thread_id=parent_thread_id,
            prompt=delegation.DELEGATION_PROMPT,
            effort="high",
            skill=explicit_skill,
        )
        observation = delegation.observe_delegation(
            server=server,
            parent_thread_id=parent_thread_id,
            events=events,
        )
        observation.runtime_multi_agent_mode = thread_result.get("multiAgentMode")
        duration_ms = int((time.monotonic() - started) * 1000)
        turn = delegation.base.parse_live_turn(
            variant=variant,
            thread_result=thread_result,
            turn_id=turn_id,
            events=events,
            duration_ms=duration_ms,
            stderr=server.stderr_text(),
            skill=explicit_skill,
        )
        return turn, observation, codex_home


def tool_metrics(turn: delegation.base.LiveTurn) -> tuple[int, int]:
    tool_calls, _ = _ORIGINAL_TOOL_METRICS(turn)
    v1_ids: set[str] = set()
    for item in v1_spawn_items(turn.events):
        receivers = item.get("receiverThreadIds")
        if isinstance(receivers, list):
            v1_ids.update(
                str(receiver)
                for receiver in receivers
                if isinstance(receiver, str) and receiver
            )
    v2_ids = {
        str(item.get("agentThreadId"))
        for item in v2_started_items(turn.events)
        if isinstance(item.get("agentThreadId"), str) and item.get("agentThreadId")
    }
    tool_calls += len(v2_ids)
    return tool_calls, len(v1_ids | v2_ids)


def evaluate_run(**kwargs: Any) -> delegation.DelegationEvaluation:
    result = _ORIGINAL_EVALUATE_RUN(**kwargs)
    observation = kwargs["observation"]
    spawned_ids = set(observation.direct_receiver_ids) | set(observation.nested_receiver_ids)
    result.row["agents_spawned"] = len(spawned_ids)
    result.artifact["agents_spawned"] = len(spawned_ids)
    result.artifact["delegation_protocols"] = list(
        getattr(observation, "protocols", [])
    )
    result.artifact["direct_agent_paths"] = dict(
        getattr(observation, "direct_agent_paths", {})
    )
    result.artifact["nested_agent_paths"] = dict(
        getattr(observation, "nested_agent_paths", {})
    )
    result.artifact["assignment_text_by_child"] = dict(
        getattr(observation, "assignment_text_by_child", {})
    )
    result.artifact["runtime_multi_agent_mode"] = getattr(
        observation, "runtime_multi_agent_mode", None
    )
    run_dir = kwargs["run_dir"]
    (run_dir / "artifact.json").write_text(
        json.dumps(result.artifact, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return result


def apply_revision_contract() -> None:
    delegation.CASE_REVISION = CASE_REVISION
    delegation.DELEGATION_PROMPT = DELEGATION_PROMPT
    delegation.session_config = session_config
    delegation.observe_delegation = observe_delegation
    delegation.run_read_only_variant = run_read_only_variant
    delegation.tool_metrics = tool_metrics
    delegation.evaluate_run = evaluate_run


def trace_events(trace_path: Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for line_number, line in enumerate(
        trace_path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as error:
            raise delegation.base.HarnessError(
                f"invalid trace JSON at line {line_number}: {error}"
            ) from error
        payload = record.get("payload") if isinstance(record, dict) else None
        if isinstance(payload, dict):
            events.append(payload)
    return events


def inspect_existing_campaign(campaign: Path) -> int:
    campaign = campaign.resolve()
    trace_path = campaign / "candidate" / "trace.jsonl"
    artifact_path = campaign / "candidate" / "artifact.json"
    if not trace_path.is_file():
        raise delegation.base.HarnessError(f"candidate trace not found: {trace_path}")

    parent_thread_id = ""
    if artifact_path.is_file():
        payload = json.loads(artifact_path.read_text(encoding="utf-8"))
        parent_thread_id = str(payload.get("thread_id") or "")

    events = trace_events(trace_path)
    direct_ids: set[str] = set()
    nested_ids: set[str] = set()
    direct_paths: dict[str, str] = {}
    nested_paths: dict[str, str] = {}
    protocols: set[str] = set()

    for item in v1_spawn_items(events):
        protocols.add("v1-collabAgentToolCall")
        sender = str(item.get("senderThreadId") or "")
        receivers = item.get("receiverThreadIds")
        if not isinstance(receivers, list):
            continue
        target = direct_ids if sender == parent_thread_id else nested_ids
        target.update(
            str(receiver)
            for receiver in receivers
            if isinstance(receiver, str) and receiver
        )

    for item in v2_started_items(events):
        protocols.add("v2-subAgentActivity")
        thread_id, agent_path, depth = classify_v2_activity(item)
        if not thread_id:
            continue
        if depth == 1:
            direct_ids.add(thread_id)
            if agent_path:
                direct_paths[thread_id] = agent_path
        else:
            nested_ids.add(thread_id)
            if agent_path:
                nested_paths[thread_id] = agent_path

    result = {
        "schema_version": 1,
        "case_revision_assessed": CASE_REVISION,
        "model_calls": 0,
        "campaign": campaign.name,
        "parent_thread_id": parent_thread_id or None,
        "protocols_observed": sorted(protocols),
        "direct_receiver_ids": sorted(direct_ids),
        "direct_agent_paths": direct_paths,
        "nested_receiver_ids": sorted(nested_ids),
        "nested_agent_paths": nested_paths,
        "historical_result_reclassified": False,
        "note": (
            "This post-hoc trace inspection can reveal V2 starts missed by the old "
            "parser. It does not replace live child-thread inspection or reclassify "
            "the historical scorer result."
        ),
    }
    output_path = campaign / "posthoc-delegation-observation.json"
    output_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    print("POST-HOC BOUNDED DELEGATION OBSERVATION")
    print("  model-calls : 0")
    print("  protocols   : " + (", ".join(result["protocols_observed"]) or "NONE"))
    print(f"  direct      : {len(result['direct_receiver_ids'])}")
    print(f"  nested      : {len(result['nested_receiver_ids'])}")
    print(f"  artifact    : {output_path}")
    print("  reclassified: NO")
    return 0


def main() -> int:
    if len(sys.argv) == 3 and sys.argv[1] == "--inspect-existing":
        try:
            return inspect_existing_campaign(Path(sys.argv[2]))
        except (delegation.base.HarnessError, OSError, json.JSONDecodeError) as error:
            print(f"ERROR: {error}", file=sys.stderr)
            return 1

    apply_revision_contract()
    return delegation.main()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("ERROR: interrupted.", file=sys.stderr)
        raise SystemExit(130)
