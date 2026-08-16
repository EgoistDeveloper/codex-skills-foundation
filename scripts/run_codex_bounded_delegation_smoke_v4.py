#!/usr/bin/env python3
"""Run bounded delegation smoke revision 4.

Revision 3 correctly observed MultiAgentV2 child starts, but it created the
parent as an ephemeral thread and then requested child history with
`thread/read(includeTurns=true)`. Codex intentionally rejects that combination.
Revision 4 starts each measured app-server with a unique process-scoped
in-memory thread store plus a campaign-local state DB, creates non-ephemeral
threads inside that disposable storage boundary, proves history readability
before either model turn, and then performs the established V1/V2 child
inspection without writing normal Codex history or agent-graph state.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Iterable

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import run_codex_bounded_delegation_smoke_v3 as revision3


delegation = revision3.delegation
CASE_REVISION = 4
_THREAD_STORE_TYPE = "in_memory"
_REVISION3_EVALUATE_RUN = revision3.evaluate_run


def command_with_startup_overrides(
    command: tuple[str, ...],
    overrides: Iterable[str],
) -> tuple[str, ...]:
    override_values = list(overrides)
    command_parts = list(command)
    try:
        listen_index = command_parts.index("--listen")
    except ValueError as error:
        raise delegation.base.HarnessError(
            "app-server command is missing the --listen boundary."
        ) from error

    inserted: list[str] = []
    for override in override_values:
        if not isinstance(override, str) or not override.strip():
            raise delegation.base.HarnessError(
                "app-server startup overrides must be nonempty strings."
            )
        inserted.extend(("-c", override))
    command_parts[listen_index:listen_index] = inserted
    return tuple(command_parts)


def in_memory_thread_store_override(store_id: str) -> str:
    if not store_id or not store_id.strip():
        raise delegation.base.HarnessError("in-memory thread store id must not be empty.")
    return (
        "experimental_thread_store="
        f"{{ type = {json.dumps(_THREAD_STORE_TYPE)}, id = {json.dumps(store_id)} }}"
    )


def sqlite_home_override(sqlite_home: Path) -> str:
    resolved = sqlite_home.resolve()
    if not resolved.is_absolute():
        raise delegation.base.HarnessError("campaign sqlite_home must be absolute.")
    return f"sqlite_home={json.dumps(str(resolved))}"


def app_server_command_with_in_memory_store(
    command: tuple[str, ...],
    *,
    store_id: str,
) -> tuple[tuple[str, ...], str]:
    override = in_memory_thread_store_override(store_id)
    if any("experimental_thread_store" in argument for argument in command):
        raise delegation.base.HarnessError(
            "app-server command already contains an experimental_thread_store override."
        )
    return command_with_startup_overrides(command, [override]), override


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
    store_id = f"bounded-delegation-{variant}-{uuid.uuid4()}"
    state_db_home = (run_dir / "state-db").resolve()
    state_db_home.mkdir(parents=True, exist_ok=False)

    isolated_command, store_override = app_server_command_with_in_memory_store(
        app_server_command,
        store_id=store_id,
    )
    state_db_override = sqlite_home_override(state_db_home)
    isolated_command = command_with_startup_overrides(
        isolated_command,
        [state_db_override],
    )

    with delegation.base.AppServer(
        command=isolated_command,
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
            "ephemeral": False,
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

        # Prove the process-scoped store supports turn-bearing reads before a
        # paid model turn begins. This catches startup override drift without
        # polluting the user's normal local thread store.
        parent_read = server.request(
            "thread/read",
            {"threadId": parent_thread_id, "includeTurns": True},
        )
        readable_parent = parent_read.get("thread")
        if not isinstance(readable_parent, dict):
            raise delegation.base.HarnessError(
                "in-memory thread-store preflight returned no parent thread."
            )
        if str(readable_parent.get("id") or "") != parent_thread_id:
            raise delegation.base.HarnessError(
                "in-memory thread-store preflight returned the wrong parent thread."
            )

        ephemeral_values = [
            value
            for value in (thread.get("ephemeral"), readable_parent.get("ephemeral"))
            if isinstance(value, bool)
        ]
        if not ephemeral_values or any(ephemeral_values):
            raise delegation.base.HarnessError(
                "bounded delegation parent was not confirmed non-ephemeral inside "
                "the disposable in-memory thread store."
            )

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
        observation.thread_store_mode = _THREAD_STORE_TYPE
        observation.thread_store_id = store_id
        observation.thread_store_startup_override = store_override
        observation.state_db_home = str(state_db_home)
        observation.state_db_startup_override = state_db_override
        observation.state_db_isolated = True
        observation.parent_thread_ephemeral = False
        observation.parent_read_preflight_pass = True
        observation.child_history_readable = not observation.child_read_errors

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


def evaluate_run(**kwargs: Any) -> delegation.DelegationEvaluation:
    result = _REVISION3_EVALUATE_RUN(**kwargs)
    observation = kwargs["observation"]

    result.artifact["thread_store_mode"] = getattr(
        observation,
        "thread_store_mode",
        None,
    )
    result.artifact["thread_store_id"] = getattr(
        observation,
        "thread_store_id",
        None,
    )
    result.artifact["thread_store_startup_override"] = getattr(
        observation,
        "thread_store_startup_override",
        None,
    )
    result.artifact["state_db_home"] = getattr(
        observation,
        "state_db_home",
        None,
    )
    result.artifact["state_db_startup_override"] = getattr(
        observation,
        "state_db_startup_override",
        None,
    )
    result.artifact["state_db_isolated"] = getattr(
        observation,
        "state_db_isolated",
        False,
    )
    result.artifact["parent_thread_ephemeral"] = getattr(
        observation,
        "parent_thread_ephemeral",
        None,
    )
    result.artifact["parent_read_preflight_pass"] = getattr(
        observation,
        "parent_read_preflight_pass",
        False,
    )
    result.artifact["child_history_readable"] = getattr(
        observation,
        "child_history_readable",
        False,
    )

    startup_overrides = result.artifact.get("startup_config_overrides")
    extra_overrides = (
        result.artifact["thread_store_startup_override"],
        result.artifact["state_db_startup_override"],
    )
    if isinstance(startup_overrides, list):
        for override in extra_overrides:
            if isinstance(override, str) and override not in startup_overrides:
                startup_overrides.append(override)

    run_dir = kwargs["run_dir"]
    (run_dir / "artifact.json").write_text(
        json.dumps(result.artifact, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return result


def apply_revision_contract() -> None:
    revision3.apply_revision_contract()
    delegation.CASE_REVISION = CASE_REVISION
    delegation.run_read_only_variant = run_read_only_variant
    delegation.evaluate_run = evaluate_run


def main() -> int:
    if len(sys.argv) == 3 and sys.argv[1] == "--inspect-existing":
        return revision3.main()

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
