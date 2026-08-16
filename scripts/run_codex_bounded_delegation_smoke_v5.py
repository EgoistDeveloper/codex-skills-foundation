#!/usr/bin/env python3
"""Run bounded delegation smoke revision 5.

Revision 4 made child histories readable, revealing that a direct child's own
MultiAgentV2 `subAgentActivity(kind=started)` provenance item is also present in
that child's history. Revision 3/4 treated every child-history start as a new
nested spawn, so the same thread ID appeared in both direct and nested sets.
Revision 5 classifies child-history activity by sender, thread identity, and
`/root/...` path depth: self/direct provenance is recorded but ignored for
fan-out, while only depth-two-or-deeper activity is counted as nested.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import run_codex_bounded_delegation_smoke_v4 as revision4


delegation = revision4.delegation
revision3 = revision4.revision3
CASE_REVISION = 5
_REVISION4_EVALUATE_RUN = revision4.evaluate_run


def append_mapping_value(
    mapping: dict[str, list[str]],
    key: str,
    value: str,
) -> None:
    values = mapping.setdefault(key, [])
    if value not in values:
        values.append(value)


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
    activity_errors: list[str] = []

    self_activity_paths_by_child: dict[str, list[str]] = {}
    mirrored_direct_activity_by_child: dict[str, list[str]] = {}
    root_activity_paths_by_child: dict[str, list[str]] = {}
    mirrored_v1_parent_spawns_by_child: dict[str, list[str]] = {}

    for item in revision3.v1_spawn_items(events):
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

    for item in revision3.v2_started_items(events):
        protocols.add("v2-subAgentActivity")
        thread_id, agent_path, depth = revision3.classify_v2_activity(item)
        if thread_id is None or depth is None:
            activity_errors.append(
                "parent V2 start omitted a valid agentThreadId or /root agentPath"
            )
            continue
        if depth == 1:
            direct_receivers.append(thread_id)
            if agent_path:
                direct_paths[thread_id] = agent_path
        elif depth >= 2:
            nested_receivers.append(thread_id)
            if agent_path:
                nested_paths[thread_id] = agent_path
        elif depth == 0 and thread_id == parent_thread_id:
            # A root provenance item is not delegation.
            continue
        else:
            activity_errors.append(
                f"parent V2 activity had unsupported depth={depth}: {thread_id}"
            )

    counts: dict[str, int] = {}
    for receiver in direct_receivers:
        counts[receiver] = counts.get(receiver, 0) + 1
    duplicate_receivers = sorted(
        receiver for receiver, count in counts.items() if count > 1
    )
    unique_direct = sorted(counts)
    direct_set = set(unique_direct)

    child_read_errors: list[str] = list(activity_errors)
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

        items = revision3.child_items(child_result)
        text = revision3.assignment_text(items)
        assignment_by_child[child_id] = text
        if child_id in direct_paths and not text:
            empty_prompt_calls += 1

        for item in items:
            item_type = revision3.normalized(item.get("type"))

            if (
                item_type == "collabagenttoolcall"
                and revision3.normalized(item.get("tool")) == "spawnagent"
            ):
                sender = str(item.get("senderThreadId") or "")
                receivers = item.get("receiverThreadIds")
                receiver_ids = [
                    str(receiver)
                    for receiver in receivers
                    if isinstance(receiver, str) and receiver
                ] if isinstance(receivers, list) else []

                if sender == parent_thread_id:
                    for receiver_id in receiver_ids:
                        append_mapping_value(
                            mirrored_v1_parent_spawns_by_child,
                            child_id,
                            receiver_id,
                        )
                    continue

                if sender != child_id:
                    child_read_errors.append(
                        f"{child_id}: child history contained V1 spawn from "
                        f"unexpected sender {sender!r}"
                    )
                    continue

                if receiver_ids:
                    nested_receivers.extend(receiver_ids)
                else:
                    nested_receivers.append("<unknown-v1-child>")
                continue

            if (
                item_type == "subagentactivity"
                and revision3.normalized(item.get("kind")) == "started"
            ):
                activity_id, activity_path, depth = revision3.classify_v2_activity(item)
                if activity_id is None or depth is None:
                    child_read_errors.append(
                        f"{child_id}: V2 start omitted a valid thread ID or agent path"
                    )
                    continue

                if depth >= 2:
                    nested_receivers.append(activity_id)
                    if activity_path:
                        nested_paths[activity_id] = activity_path
                    continue

                if depth == 1:
                    expected_path = direct_paths.get(activity_id)
                    if expected_path and activity_path != expected_path:
                        child_read_errors.append(
                            f"{child_id}: direct activity path mismatch for "
                            f"{activity_id}: observed={activity_path!r} "
                            f"expected={expected_path!r}"
                        )
                        continue

                    if activity_id == child_id:
                        append_mapping_value(
                            self_activity_paths_by_child,
                            child_id,
                            activity_path or "<missing-path>",
                        )
                        continue

                    if activity_id in direct_set:
                        append_mapping_value(
                            mirrored_direct_activity_by_child,
                            child_id,
                            activity_id,
                        )
                        continue

                    child_read_errors.append(
                        f"{child_id}: child history exposed unobserved root-level "
                        f"direct activity {activity_id} at {activity_path!r}"
                    )
                    continue

                if depth == 0 and activity_id == parent_thread_id:
                    append_mapping_value(
                        root_activity_paths_by_child,
                        child_id,
                        activity_path or "/root",
                    )
                    continue

                child_read_errors.append(
                    f"{child_id}: unsupported V2 activity depth={depth} "
                    f"for {activity_id} at {activity_path!r}"
                )

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
    observation.self_activity_paths_by_child = self_activity_paths_by_child
    observation.mirrored_direct_activity_by_child = mirrored_direct_activity_by_child
    observation.root_activity_paths_by_child = root_activity_paths_by_child
    observation.mirrored_v1_parent_spawns_by_child = (
        mirrored_v1_parent_spawns_by_child
    )
    return observation


def evaluate_run(**kwargs: Any) -> delegation.DelegationEvaluation:
    result = _REVISION4_EVALUATE_RUN(**kwargs)
    observation = kwargs["observation"]

    result.artifact["self_activity_paths_by_child"] = dict(
        getattr(observation, "self_activity_paths_by_child", {})
    )
    result.artifact["mirrored_direct_activity_by_child"] = dict(
        getattr(observation, "mirrored_direct_activity_by_child", {})
    )
    result.artifact["root_activity_paths_by_child"] = dict(
        getattr(observation, "root_activity_paths_by_child", {})
    )
    result.artifact["mirrored_v1_parent_spawns_by_child"] = dict(
        getattr(observation, "mirrored_v1_parent_spawns_by_child", {})
    )

    run_dir = kwargs["run_dir"]
    (run_dir / "artifact.json").write_text(
        json.dumps(result.artifact, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return result


def apply_revision_contract() -> None:
    revision4.apply_revision_contract()
    delegation.CASE_REVISION = CASE_REVISION
    delegation.observe_delegation = observe_delegation
    delegation.evaluate_run = evaluate_run


def main() -> int:
    if len(sys.argv) == 3 and sys.argv[1] == "--inspect-existing":
        return revision4.main()

    apply_revision_contract()
    return delegation.main()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("ERROR: interrupted.", file=sys.stderr)
        raise SystemExit(130)
    except (
        delegation.base.HarnessError,
        OSError,
        subprocess.SubprocessError,
        json.JSONDecodeError,
    ) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
