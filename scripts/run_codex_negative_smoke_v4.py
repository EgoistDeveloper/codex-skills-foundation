#!/usr/bin/env python3
"""Run the runtime-isolated Codex negative-trigger smoke.

Codex can contribute MCP servers after ordinary config and plugin inventory have
already been resolved. This launcher performs a model-free ephemeral thread
probe, records the effective runtime MCP names, converts those names into valid
transport-complete disabled startup entries, verifies the name veto without a
model turn, and then delegates to the established negative-trigger harness.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any, Callable

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import run_codex_live_smoke as base
import run_codex_negative_smoke as negative

CASE_REVISION = 6
RUNTIME_PROBE_TIMEOUT_SECONDS = 45
RUNTIME_PROBE_POLL_SECONDS = 0.25
RUNTIME_PROBE_STABLE_POLLS = 2
DISABLED_MCP_STUB_COMMAND = "__engineering_foundation_disabled_mcp__"


def mcp_status_rows(
    server: base.AppServer,
    *,
    thread_id: str,
) -> list[dict[str, Any]]:
    """Return the complete, normalized thread runtime MCP inventory."""
    rows: list[dict[str, Any]] = []
    cursor: str | None = None

    while True:
        response = server.request(
            "mcpServerStatus/list",
            {
                "cursor": cursor,
                "limit": 100,
                "detail": "toolsAndAuthOnly",
                "threadId": thread_id,
            },
        )
        data = response.get("data")
        if not isinstance(data, list):
            raise base.HarnessError(
                "mcpServerStatus/list returned an invalid data field."
            )

        for item in data:
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            if not isinstance(name, str) or not name.strip():
                continue
            plugin_id = item.get("pluginId")
            tools = item.get("tools")
            rows.append(
                {
                    "name": name,
                    "plugin_id": (
                        plugin_id
                        if isinstance(plugin_id, str) and plugin_id.strip()
                        else None
                    ),
                    "auth_status": item.get("authStatus"),
                    "tool_names": (
                        sorted(str(tool_name) for tool_name in tools)
                        if isinstance(tools, dict)
                        else []
                    ),
                }
            )

        next_cursor = response.get("nextCursor")
        if not isinstance(next_cursor, str) or not next_cursor:
            break
        cursor = next_cursor

    unique: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        key = (str(row["name"]), str(row["plugin_id"] or ""))
        unique[key] = row

    return sorted(
        unique.values(),
        key=lambda row: (str(row["name"]), str(row["plugin_id"] or "")),
    )


def merge_mcp_server_names(
    direct_config_names: list[str],
    runtime_inventory: list[dict[str, Any]],
) -> list[str]:
    """Build the fail-closed name veto applied to both live variants."""
    names = {name for name in direct_config_names if name}
    for row in runtime_inventory:
        name = row.get("name")
        if isinstance(name, str) and name:
            names.add(name)
    return sorted(names)


def disabled_mcp_table_override(server_names: list[str]) -> str:
    """Return valid disabled MCP entries whose names survive runtime overlays.

    Codex requires every configured MCP row to declare a transport even when
    ``enabled`` is false. A non-runnable placeholder command is therefore kept
    as structural metadata; the disabled flag prevents it from being launched.
    """
    names = sorted({name for name in server_names if name})
    entries = ", ".join(
        (
            f"{json.dumps(name, ensure_ascii=True)} = "
            "{ "
            f"command = {json.dumps(DISABLED_MCP_STUB_COMMAND)}, "
            "enabled = false "
            "}"
        )
        for name in names
    )
    return f"mcp_servers={{ {entries} }}"


def transport_safe_builder(
    original_builder: Callable[..., tuple[tuple[str, ...], list[str]]],
) -> Callable[..., tuple[tuple[str, ...], list[str]]]:
    """Wrap the existing command builder with transport-complete MCP vetoes."""

    def build(
        *,
        launchers: base.CodexLaunchers,
        installed_plugin_ids: list[str],
        mcp_server_names: list[str],
        plugin_mcp_servers: dict[str, list[str]] | None = None,
        plugins_enabled: bool,
        enabled_plugin_id: str | None,
    ) -> tuple[tuple[str, ...], list[str]]:
        command, overrides = original_builder(
            launchers=launchers,
            installed_plugin_ids=installed_plugin_ids,
            mcp_server_names=[],
            plugin_mcp_servers=plugin_mcp_servers,
            plugins_enabled=plugins_enabled,
            enabled_plugin_id=enabled_plugin_id,
        )
        names = sorted({name for name in mcp_server_names if name})
        if not names:
            return command, overrides
        if len(command) < 2 or tuple(command[-2:]) != ("--listen", "stdio://"):
            raise base.HarnessError(
                "unexpected app-server command shape while adding MCP vetoes."
            )

        veto_override = disabled_mcp_table_override(names)
        amended_command = (
            *command[:-2],
            "-c",
            veto_override,
            *command[-2:],
        )
        return tuple(amended_command), [*overrides, veto_override]

    return build


def startup_only_session_config_builder(
    original_builder: Callable[..., dict[str, Any]],
) -> Callable[..., dict[str, Any]]:
    """Keep MCP rows exclusively in the validated app-server startup layer.

    Thread config is a separate configuration layer. Supplying only
    ``enabled=false`` there replaces the transport-complete startup row and is
    rejected as ``invalid transport``. The startup layer already owns the full
    name veto, so thread config must omit top-level MCP rows entirely.
    """

    def build(
        *,
        disabled_skill_paths: list[str],
        mcp_server_names: list[str],
    ) -> dict[str, Any]:
        config = original_builder(
            disabled_skill_paths=disabled_skill_paths,
            mcp_server_names=[],
        )
        if "mcp_servers" in config:
            raise base.HarnessError(
                "startup-only session config unexpectedly emitted MCP rows."
            )
        return config

    return build


def poll_runtime_inventory(
    server: base.AppServer,
    *,
    thread_id: str,
    timeout_seconds: int,
) -> list[dict[str, Any]]:
    """Poll until the thread MCP inventory is stable or the deadline expires."""
    observed: dict[tuple[str, str], dict[str, Any]] = {}
    previous_signature: tuple[tuple[str, str, tuple[str, ...]], ...] | None = None
    stable_polls = 0
    deadline = time.monotonic() + timeout_seconds

    while time.monotonic() < deadline:
        current = mcp_status_rows(server, thread_id=thread_id)
        for row in current:
            key = (str(row["name"]), str(row["plugin_id"] or ""))
            observed[key] = row

        signature = tuple(
            (
                str(row["name"]),
                str(row["plugin_id"] or ""),
                tuple(str(name) for name in row["tool_names"]),
            )
            for row in current
        )
        if signature == previous_signature:
            stable_polls += 1
        else:
            previous_signature = signature
            stable_polls = 0

        if current and stable_polls >= RUNTIME_PROBE_STABLE_POLLS:
            break
        time.sleep(RUNTIME_PROBE_POLL_SECONDS)

    return sorted(
        observed.values(),
        key=lambda row: (str(row["name"]), str(row["plugin_id"] or "")),
    )


def discover_runtime_mcp_inventory(
    *,
    launchers: base.CodexLaunchers,
    codex_home: Path,
    cwd: Path,
    timeout_seconds: int = RUNTIME_PROBE_TIMEOUT_SECONDS,
) -> list[dict[str, Any]]:
    """Discover compatibility/extension MCP names without starting a model turn."""
    if timeout_seconds < 5:
        raise base.HarnessError("runtime MCP probe timeout must be at least five seconds.")

    with base.qualification_workspace.allocate_probe_workspace(
        repository_root=base.ROOT,
        family="mcpprobe",
    ) as probe_workspace:
        trace_path = probe_workspace.child("t")
        request_timeout = max(30, min(timeout_seconds, 120))
        with base.AppServer(
            command=launchers.app_server_command,
            node_executable=launchers.node_executable,
            cwd=cwd,
            trace_path=trace_path,
            timeout_seconds=request_timeout,
        ) as server:
            reported_home = server.initialize()
            if base.normalized_path(reported_home) != base.normalized_path(codex_home):
                raise base.HarnessError(
                    "runtime MCP probe used a different Codex home directory."
                )

            thread_result = server.start_thread(
                cwd=cwd,
                model=None,
                model_provider=None,
                service_tier=None,
                session_config={},
            )
            thread = thread_result.get("thread")
            if not isinstance(thread, dict) or not isinstance(thread.get("id"), str):
                raise base.HarnessError(
                    "runtime MCP probe thread/start returned no thread id."
                )
            inventory = poll_runtime_inventory(
                server,
                thread_id=str(thread["id"]),
                timeout_seconds=timeout_seconds,
            )

    if not inventory:
        raise base.HarnessError(
            "runtime MCP probe returned no inventory; live model turns were not started."
        )
    return inventory


def verify_runtime_mcp_veto(
    *,
    launchers: base.CodexLaunchers,
    codex_home: Path,
    cwd: Path,
    disabled_names: list[str],
    builder: Callable[..., tuple[tuple[str, ...], list[str]]],
    campaign: Path | None,
    timeout_seconds: int = RUNTIME_PROBE_TIMEOUT_SECONDS,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Verify the complete name veto before either authenticated model turn."""
    plugin_ids = negative.installed_plugin_ids(launchers)
    command, overrides = builder(
        launchers=launchers,
        installed_plugin_ids=plugin_ids,
        mcp_server_names=disabled_names,
        plugin_mcp_servers={},
        plugins_enabled=False,
        enabled_plugin_id=None,
    )

    temporary: base.qualification_workspace.WorkspaceLease | None
    if campaign is None:
        temporary = base.qualification_workspace.allocate_probe_workspace(
            repository_root=base.ROOT,
            family="mcpveto",
        )
        trace_path = temporary.child("t")
    else:
        temporary = None
        trace_path = campaign / "preflight" / "runtime-mcp-veto-trace.jsonl"
        trace_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with base.AppServer(
            command=command,
            node_executable=launchers.node_executable,
            cwd=cwd,
            trace_path=trace_path,
            timeout_seconds=max(30, min(timeout_seconds, 120)),
        ) as server:
            reported_home = server.initialize()
            if base.normalized_path(reported_home) != base.normalized_path(codex_home):
                raise base.HarnessError(
                    "runtime MCP veto verification used a different Codex home directory."
                )
            session_config = base.build_session_config(
                disabled_skill_paths=[],
                mcp_server_names=disabled_names,
            )
            session_config["features"]["plugins"] = False
            session_config["features"]["remote_plugin"] = False
            session_config["features"]["recommended_plugins"] = False
            session_config["features"]["plugin_sharing"] = False
            session_config["features"]["apps"] = False
            session_config["features"]["code_mode"] = False
            session_config["memories"] = {
                "generate_memories": False,
                "use_memories": False,
                "dedicated_tools": False,
            }
            if "mcp_servers" in session_config:
                raise base.HarnessError(
                    "runtime MCP veto verification received thread-layer MCP rows."
                )
            thread_result = server.start_thread(
                cwd=cwd,
                model=None,
                model_provider=None,
                service_tier=None,
                session_config=session_config,
            )
            thread = thread_result.get("thread")
            if not isinstance(thread, dict) or not isinstance(thread.get("id"), str):
                raise base.HarnessError(
                    "runtime MCP veto verification returned no thread id."
                )
            inventory = poll_runtime_inventory(
                server,
                thread_id=str(thread["id"]),
                timeout_seconds=timeout_seconds,
            )
    finally:
        if temporary is not None:
            temporary.cleanup()

    disabled = set(disabled_names)
    leaking = sorted(
        str(row["name"])
        for row in inventory
        if str(row["name"]) in disabled and row["tool_names"]
    )
    if leaking:
        raise base.HarnessError(
            "runtime MCP name veto left tools exposed: " + ", ".join(leaking)
        )
    return inventory, overrides


def write_runtime_probe_artifact(
    *,
    campaign: Path | None,
    codex_home: Path,
    direct_config_names: list[str],
    runtime_inventory: list[dict[str, Any]],
    disabled_names: list[str],
    veto_inventory: list[dict[str, Any]],
    veto_overrides: list[str],
) -> Path | None:
    if campaign is None:
        return None
    path = campaign / "preflight" / "runtime-mcp-inventory.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 3,
        "case_revision": CASE_REVISION,
        "codex_home": str(codex_home),
        "model_calls": 0,
        "direct_config_mcp_names": direct_config_names,
        "runtime_mcp_inventory": runtime_inventory,
        "disabled_mcp_server_names": disabled_names,
        "thread_mcp_overrides_omitted": True,
        "veto_validation_inventory": veto_inventory,
        "veto_startup_overrides": veto_overrides,
        "veto_validation_pass": True,
    }
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return path


def runtime_aware_configured_mcp_names(
    *,
    codex_home: Path,
    original_reader: Callable[[Path], list[str]],
    launchers: base.CodexLaunchers,
    campaign: Path | None,
    builder: Callable[..., tuple[tuple[str, ...], list[str]]],
) -> list[str]:
    direct_names = sorted(set(original_reader(codex_home)))
    inventory = discover_runtime_mcp_inventory(
        launchers=launchers,
        codex_home=codex_home,
        cwd=base.ROOT,
    )
    disabled_names = merge_mcp_server_names(direct_names, inventory)
    veto_inventory, veto_overrides = verify_runtime_mcp_veto(
        launchers=launchers,
        codex_home=codex_home,
        cwd=base.ROOT,
        disabled_names=disabled_names,
        builder=builder,
        campaign=campaign,
    )
    artifact = write_runtime_probe_artifact(
        campaign=campaign,
        codex_home=codex_home,
        direct_config_names=direct_names,
        runtime_inventory=inventory,
        disabled_names=disabled_names,
        veto_inventory=veto_inventory,
        veto_overrides=veto_overrides,
    )

    print("\nRUNTIME MCP ISOLATION PREFLIGHT")
    print("  model-calls       : 0")
    print("  direct-config     : " + (", ".join(direct_names) or "NONE"))
    print(
        "  runtime-discovered: "
        + ", ".join(str(row["name"]) for row in inventory)
    )
    print("  name-veto         : " + ", ".join(disabled_names))
    print("  transport-stubs   : VALID")
    print("  thread-mcp-layer  : OMITTED")
    print("  veto-validation   : PASS")
    if artifact is not None:
        print(f"  artifact          : {artifact}")
    print()
    return disabled_names


def main() -> int:
    launchers = base.resolve_codex_launchers()
    original_reader = base.configured_mcp_server_names
    original_campaign_directory = base.campaign_directory
    original_builder = negative.build_isolated_app_server_command
    original_session_builder = base.build_session_config
    original_case_revision = negative.CASE_REVISION
    safe_builder = transport_safe_builder(original_builder)
    safe_session_builder = startup_only_session_config_builder(
        original_session_builder
    )
    captured_campaign: dict[str, Path] = {}

    def capture_campaign(output_root: Path) -> Path:
        campaign = original_campaign_directory(output_root)
        captured_campaign["path"] = campaign
        return campaign

    def runtime_aware_reader(codex_home: Path) -> list[str]:
        return runtime_aware_configured_mcp_names(
            codex_home=codex_home,
            original_reader=original_reader,
            launchers=launchers,
            campaign=captured_campaign.get("path"),
            builder=safe_builder,
        )

    negative.CASE_REVISION = CASE_REVISION
    base.campaign_directory = capture_campaign
    base.configured_mcp_server_names = runtime_aware_reader
    base.build_session_config = safe_session_builder
    negative.build_isolated_app_server_command = safe_builder
    try:
        return negative.main()
    finally:
        negative.CASE_REVISION = original_case_revision
        negative.build_isolated_app_server_command = original_builder
        base.build_session_config = original_session_builder
        base.campaign_directory = original_campaign_directory
        base.configured_mcp_server_names = original_reader


if __name__ == "__main__":
    try:
        raise SystemExit(base.qualification_workspace.run_with_cleanup(main))
    except KeyboardInterrupt:
        print("ERROR: interrupted.", file=sys.stderr)
        raise SystemExit(130)
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
