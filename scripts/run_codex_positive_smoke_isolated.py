#!/usr/bin/env python3
"""Run the explicit-positive Codex smoke with runtime MCP isolation.

The base positive smoke predates Codex runtime-only MCP registrations. This
maintainer wrapper discovers the effective runtime MCP inventory without a
model turn, validates a transport-complete name veto, disables foreign plugins
at app-server startup, and then delegates to the established positive harness.
"""
from __future__ import annotations

import dataclasses
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import run_codex_live_smoke as base
import run_codex_negative_smoke as negative
import run_codex_negative_smoke_v4 as isolation

ISOLATION_REVISION = 1
POSITIVE_CASE_REVISION = 2


def effective_plugin_ids(
    inventory: list[dict[str, Any]],
    cli_plugin_ids: list[str],
) -> list[str]:
    """Return every plugin ID that can affect app-server startup."""
    ids = {base.PLUGIN_ID, *cli_plugin_ids}
    for item in inventory:
        plugin_id = item.get("id")
        if isinstance(plugin_id, str) and plugin_id.strip():
            ids.add(plugin_id)
    return sorted(ids)


def build_positive_app_server_command(
    *,
    launchers: base.CodexLaunchers,
    plugin_ids: list[str],
    disabled_mcp_server_names: list[str],
) -> tuple[tuple[str, ...], list[str]]:
    """Enable only core and apply the validated runtime MCP name veto."""
    builder = isolation.transport_safe_builder(
        negative.build_isolated_app_server_command
    )
    return builder(
        launchers=launchers,
        installed_plugin_ids=plugin_ids,
        mcp_server_names=disabled_mcp_server_names,
        plugin_mcp_servers={},
        plugins_enabled=True,
        enabled_plugin_id=base.PLUGIN_ID,
    )


def write_isolation_artifact(
    *,
    campaign: Path,
    codex_home: Path,
    direct_mcp_names: list[str],
    runtime_inventory: list[dict[str, Any]],
    disabled_mcp_names: list[str],
    veto_inventory: list[dict[str, Any]],
    veto_overrides: list[str],
    startup_overrides: list[str],
    plugin_ids: list[str],
) -> Path:
    preflight_dir = campaign / "preflight"
    if not preflight_dir.is_dir():
        raise base.HarnessError(
            "positive campaign layout did not prepare the preflight directory "
            "before the isolation artifact write."
        )

    path = preflight_dir / "positive-runtime-isolation.json"
    payload = {
        "schema_version": 1,
        "isolation_revision": ISOLATION_REVISION,
        "positive_case_revision": POSITIVE_CASE_REVISION,
        "model_calls": 0,
        "codex_home": str(codex_home),
        "effective_plugin_ids": plugin_ids,
        "direct_config_mcp_names": direct_mcp_names,
        "runtime_mcp_inventory": runtime_inventory,
        "disabled_mcp_server_names": disabled_mcp_names,
        "thread_mcp_overrides_omitted": True,
        "veto_validation_inventory": veto_inventory,
        "veto_validation_overrides": veto_overrides,
        "measured_startup_overrides": startup_overrides,
        "veto_validation_pass": True,
    }
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return path


def main() -> int:
    if "--confirm-live" not in sys.argv:
        return base.main()

    original_launchers = base.resolve_codex_launchers()
    base.login_status(original_launchers)

    with tempfile.TemporaryDirectory(
        prefix="engineering-foundation-positive-isolation-"
    ) as tmp:
        trace_path = Path(tmp) / "inventory-trace.jsonl"
        with base.AppServer(
            command=original_launchers.app_server_command,
            node_executable=original_launchers.node_executable,
            cwd=base.ROOT,
            trace_path=trace_path,
            timeout_seconds=120,
        ) as server:
            codex_home = server.initialize()
            inventory = negative.app_server_effective_plugin_inventory(
                server,
                base.ROOT,
            )

    direct_mcp_names = base.configured_mcp_server_names(codex_home)
    runtime_inventory = isolation.discover_runtime_mcp_inventory(
        launchers=original_launchers,
        codex_home=codex_home,
        cwd=base.ROOT,
    )
    disabled_mcp_names = isolation.merge_mcp_server_names(
        direct_mcp_names,
        runtime_inventory,
    )
    cli_plugin_ids = negative.installed_plugin_ids(original_launchers)
    plugin_ids = effective_plugin_ids(inventory, cli_plugin_ids)

    safe_builder = isolation.transport_safe_builder(
        negative.build_isolated_app_server_command
    )
    original_session_builder = base.build_session_config
    safe_session_builder = isolation.startup_only_session_config_builder(
        original_session_builder
    )

    base.build_session_config = safe_session_builder
    try:
        veto_inventory, veto_overrides = isolation.verify_runtime_mcp_veto(
            launchers=original_launchers,
            codex_home=codex_home,
            cwd=base.ROOT,
            disabled_names=disabled_mcp_names,
            builder=safe_builder,
            campaign=None,
        )
    finally:
        base.build_session_config = original_session_builder

    app_server_command, startup_overrides = build_positive_app_server_command(
        launchers=original_launchers,
        plugin_ids=plugin_ids,
        disabled_mcp_server_names=disabled_mcp_names,
    )
    isolated_launchers = dataclasses.replace(
        original_launchers,
        app_server_command=app_server_command,
    )

    original_resolver = base.resolve_codex_launchers
    original_reader = base.configured_mcp_server_names
    original_campaign_directory = base.campaign_directory
    original_create_fixture = base.create_fixture
    safe_session_builder = isolation.startup_only_session_config_builder(
        original_session_builder
    )
    captured_campaign: Path | None = None

    def capture_campaign(output_root: Path) -> Path:
        nonlocal captured_campaign
        captured_campaign = original_campaign_directory(output_root)
        return captured_campaign

    def create_fixture_with_isolation(seed: Path) -> None:
        if captured_campaign is None:
            raise base.HarnessError(
                "positive isolation campaign path was not captured before fixture creation."
            )

        artifact = write_isolation_artifact(
            campaign=captured_campaign,
            codex_home=codex_home,
            direct_mcp_names=direct_mcp_names,
            runtime_inventory=runtime_inventory,
            disabled_mcp_names=disabled_mcp_names,
            veto_inventory=veto_inventory,
            veto_overrides=veto_overrides,
            startup_overrides=startup_overrides,
            plugin_ids=plugin_ids,
        )
        print("\nPOSITIVE RUNTIME ISOLATION PREFLIGHT")
        print("  model-calls       : 0")
        print("  transport-stubs   : VALID")
        print("  thread-mcp-layer  : OMITTED")
        print("  veto-validation   : PASS")
        print(f"  artifact          : {artifact}")
        print()
        original_create_fixture(seed)

    base.resolve_codex_launchers = lambda: isolated_launchers
    base.configured_mcp_server_names = lambda _home: list(disabled_mcp_names)
    base.campaign_directory = capture_campaign
    base.create_fixture = create_fixture_with_isolation
    base.build_session_config = safe_session_builder
    try:
        return base.main()
    finally:
        base.resolve_codex_launchers = original_resolver
        base.configured_mcp_server_names = original_reader
        base.campaign_directory = original_campaign_directory
        base.create_fixture = original_create_fixture
        base.build_session_config = original_session_builder


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("ERROR: interrupted.", file=sys.stderr)
        raise SystemExit(130)
    except (
        base.HarnessError,
        OSError,
        subprocess.SubprocessError,
        json.JSONDecodeError,
    ) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
