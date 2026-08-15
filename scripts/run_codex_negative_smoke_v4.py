#!/usr/bin/env python3
"""Run negative-trigger smoke revision 4 with runtime MCP name isolation.

Codex can contribute MCP servers after ordinary config and plugin inventory have
already been resolved. This launcher performs a model-free ephemeral thread
probe, records the effective runtime MCP names, applies those names as explicit
vetoes, and then delegates to the established negative-trigger smoke harness.
"""
from __future__ import annotations

import json
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Callable

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import run_codex_live_smoke as base
import run_codex_negative_smoke as negative

CASE_REVISION = 4
RUNTIME_PROBE_TIMEOUT_SECONDS = 45
RUNTIME_PROBE_POLL_SECONDS = 0.25
RUNTIME_PROBE_STABLE_POLLS = 2


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

    with tempfile.TemporaryDirectory(prefix="engineering-foundation-mcp-probe-") as tmp:
        trace_path = Path(tmp) / "runtime-mcp-probe-trace.jsonl"
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
            thread_id = str(thread["id"])

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

    inventory = sorted(
        observed.values(),
        key=lambda row: (str(row["name"]), str(row["plugin_id"] or "")),
    )
    if not inventory:
        raise base.HarnessError(
            "runtime MCP probe returned no inventory; live model turns were not started."
        )
    return inventory


def write_runtime_probe_artifact(
    *,
    campaign: Path | None,
    codex_home: Path,
    direct_config_names: list[str],
    runtime_inventory: list[dict[str, Any]],
    disabled_names: list[str],
) -> Path | None:
    if campaign is None:
        return None
    path = campaign / "preflight" / "runtime-mcp-inventory.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        "case_revision": CASE_REVISION,
        "codex_home": str(codex_home),
        "model_calls": 0,
        "direct_config_mcp_names": direct_config_names,
        "runtime_mcp_inventory": runtime_inventory,
        "disabled_mcp_server_names": disabled_names,
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
) -> list[str]:
    direct_names = sorted(set(original_reader(codex_home)))
    inventory = discover_runtime_mcp_inventory(
        launchers=launchers,
        codex_home=codex_home,
        cwd=base.ROOT,
    )
    disabled_names = merge_mcp_server_names(direct_names, inventory)
    artifact = write_runtime_probe_artifact(
        campaign=campaign,
        codex_home=codex_home,
        direct_config_names=direct_names,
        runtime_inventory=inventory,
        disabled_names=disabled_names,
    )

    print("\nRUNTIME MCP ISOLATION PREFLIGHT")
    print("  model-calls       : 0")
    print("  direct-config     : " + (", ".join(direct_names) or "NONE"))
    print(
        "  runtime-discovered: "
        + ", ".join(str(row["name"]) for row in inventory)
    )
    print("  name-veto         : " + ", ".join(disabled_names))
    if artifact is not None:
        print(f"  artifact          : {artifact}")
    print()
    return disabled_names


def main() -> int:
    launchers = base.resolve_codex_launchers()
    original_reader = base.configured_mcp_server_names
    original_campaign_directory = base.campaign_directory
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
        )

    negative.CASE_REVISION = CASE_REVISION
    base.campaign_directory = capture_campaign
    base.configured_mcp_server_names = runtime_aware_reader
    try:
        return negative.main()
    finally:
        base.campaign_directory = original_campaign_directory
        base.configured_mcp_server_names = original_reader


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("ERROR: interrupted.", file=sys.stderr)
        raise SystemExit(130)
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
