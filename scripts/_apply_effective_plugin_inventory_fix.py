from __future__ import annotations

from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one match, found {count}")
    return text.replace(old, new, 1)


script_path = Path("scripts/run_codex_negative_smoke.py")
text = script_path.read_text(encoding="utf-8")
text = replace_once(text, 'CASE_REVISION = 2', 'CASE_REVISION = 3', 'bump case revision')

inventory_helpers = '''\n\ndef effective_plugin_inventory_from_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:\n    marketplaces = payload.get("marketplaces", [])\n    if not isinstance(marketplaces, list):\n        raise base.HarnessError("plugin/installed returned an invalid marketplaces field.")\n\n    inventory: list[dict[str, Any]] = []\n    for marketplace in marketplaces:\n        if not isinstance(marketplace, dict):\n            continue\n        marketplace_name = marketplace.get("name")\n        marketplace_path = marketplace.get("path")\n        plugins = marketplace.get("plugins", [])\n        if not isinstance(plugins, list):\n            raise base.HarnessError("plugin/installed returned an invalid plugins field.")\n        for plugin in plugins:\n            if not isinstance(plugin, dict):\n                continue\n            if plugin.get("installed") is not True and plugin.get("enabled") is not True:\n                continue\n            plugin_id = plugin.get("id")\n            plugin_name = plugin.get("name")\n            if (\n                not isinstance(plugin_id, str)\n                or not plugin_id.strip()\n                or not isinstance(plugin_name, str)\n                or not plugin_name.strip()\n                or not isinstance(marketplace_name, str)\n                or not marketplace_name.strip()\n            ):\n                raise base.HarnessError("plugin/installed returned an incomplete plugin row.")\n            inventory.append(\n                {\n                    "id": plugin_id,\n                    "name": plugin_name,\n                    "marketplace_name": marketplace_name,\n                    "marketplace_path": (\n                        marketplace_path if isinstance(marketplace_path, str) else None\n                    ),\n                    "installed": plugin.get("installed") is True,\n                    "enabled": plugin.get("enabled") is True,\n                }\n            )\n    return sorted(inventory, key=lambda item: str(item["id"]))\n\n\ndef app_server_effective_plugin_inventory(\n    server: base.AppServer,\n    cwd: Path,\n) -> list[dict[str, Any]]:\n    payload = server.request(\n        "plugin/installed",\n        {\n            "cwds": [str(cwd)],\n            "installSuggestionPluginNames": [],\n        },\n    )\n    return effective_plugin_inventory_from_payload(payload)\n\n\ndef app_server_plugin_mcp_servers(\n    server: base.AppServer,\n    inventory: list[dict[str, Any]],\n    *,\n    known_plugin_ids: set[str],\n) -> dict[str, list[str]]:\n    discovered: dict[str, list[str]] = {}\n    for item in inventory:\n        plugin_id = str(item["id"])\n        if plugin_id == base.PLUGIN_ID or plugin_id in known_plugin_ids:\n            continue\n        params: dict[str, Any] = {"pluginName": str(item["name"])}\n        marketplace_path = item.get("marketplace_path")\n        if isinstance(marketplace_path, str) and marketplace_path:\n            params["marketplacePath"] = marketplace_path\n        else:\n            params["remoteMarketplaceName"] = str(item["marketplace_name"])\n        response = server.request("plugin/read", params)\n        plugin = response.get("plugin")\n        if not isinstance(plugin, dict):\n            raise base.HarnessError(f"plugin/read returned no plugin detail for {plugin_id!r}.")\n        mcp_servers = plugin.get("mcpServers", [])\n        if not isinstance(mcp_servers, list) or not all(\n            isinstance(name, str) and name for name in mcp_servers\n        ):\n            raise base.HarnessError(\n                f"plugin/read returned an invalid MCP server list for {plugin_id!r}."\n            )\n        discovered[plugin_id] = sorted(set(mcp_servers))\n    return discovered\n'''
text = replace_once(
    text,
    '\n\n\ndef toml_bool(value: bool) -> str:\n',
    inventory_helpers + '\n\ndef toml_bool(value: bool) -> str:\n',
    'insert effective plugin inventory helpers',
)

old_plugin_override = '''def plugin_table_override(plugin_states: dict[str, bool]) -> str:\n    entries = ", ".join(\n        f"{json.dumps(plugin_id, ensure_ascii=True)} = {{ enabled = {toml_bool(enabled)} }}"\n        for plugin_id, enabled in sorted(plugin_states.items())\n    )\n    return f"plugins={{ {entries} }}"\n'''
new_plugin_override = '''def plugin_table_override(\n    plugin_states: dict[str, bool],\n    plugin_mcp_servers: dict[str, list[str]] | None = None,\n) -> str:\n    mcp_by_plugin = plugin_mcp_servers or {}\n    entries: list[str] = []\n    for plugin_id, enabled in sorted(plugin_states.items()):\n        fields = [f"enabled = {toml_bool(enabled)}"]\n        mcp_names = sorted(set(mcp_by_plugin.get(plugin_id, [])))\n        if mcp_names:\n            mcp_entries = ", ".join(\n                f"{json.dumps(name, ensure_ascii=True)} = {{ enabled = false }}"\n                for name in mcp_names\n            )\n            fields.append(f"mcp_servers = {{ {mcp_entries} }}")\n        entries.append(\n            f"{json.dumps(plugin_id, ensure_ascii=True)} = {{ {', '.join(fields)} }}"\n        )\n    return f"plugins={{ {', '.join(entries)} }}"\n'''
text = replace_once(text, old_plugin_override, new_plugin_override, 'extend plugin override')

text = replace_once(
    text,
    '''    installed_plugin_ids: list[str],\n    mcp_server_names: list[str],\n    plugins_enabled: bool,\n''',
    '''    installed_plugin_ids: list[str],\n    mcp_server_names: list[str],\n    plugin_mcp_servers: dict[str, list[str]] | None = None,\n    plugins_enabled: bool,\n''',
    'extend startup command signature',
)
text = replace_once(
    text,
    '        overrides.append(plugin_table_override(plugin_states))',
    '        overrides.append(plugin_table_override(plugin_states, plugin_mcp_servers))',
    'apply plugin MCP startup overrides',
)

text = replace_once(
    text,
    '''    mcp_server_names: list[str],\n    installed_plugin_ids: list[str],\n) -> tuple[dict[str, Any], dict[str, str], list[str], list[str]]:\n''',
    '''    mcp_server_names: list[str],\n    installed_plugin_ids: list[str],\n    plugin_mcp_servers: dict[str, list[str]],\n) -> tuple[dict[str, Any], dict[str, str], list[str], list[str]]:\n''',
    'extend candidate session signature',
)
old_thread_plugins = '''    config["plugins"] = {\n        plugin_id: {"enabled": plugin_id == base.PLUGIN_ID}\n        for plugin_id in sorted(set(installed_plugin_ids) | {base.PLUGIN_ID})\n    }\n'''
new_thread_plugins = '''    config["plugins"] = {}\n    for plugin_id in sorted(set(installed_plugin_ids) | {base.PLUGIN_ID}):\n        plugin_config: dict[str, Any] = {\n            "enabled": plugin_id == base.PLUGIN_ID,\n        }\n        mcp_names = sorted(set(plugin_mcp_servers.get(plugin_id, [])))\n        if mcp_names:\n            plugin_config["mcp_servers"] = {\n                name: {"enabled": False}\n                for name in mcp_names\n            }\n        config["plugins"][plugin_id] = plugin_config\n'''
text = replace_once(text, old_thread_plugins, new_thread_plugins, 'add thread plugin MCP isolation')

text = replace_once(
    text,
    '''    disabled_plugin_ids: list[str],\n    disabled_mcp_server_names: list[str],\n    startup_config_overrides: list[str],\n''',
    '''    disabled_plugin_ids: list[str],\n    effective_plugin_ids: list[str],\n    hidden_plugin_ids: list[str],\n    disabled_plugin_mcp_servers: dict[str, list[str]],\n    disabled_mcp_server_names: list[str],\n    startup_config_overrides: list[str],\n''',
    'extend evaluation evidence inputs',
)
text = replace_once(
    text,
    '''        "disabled_plugin_ids": sorted(set(disabled_plugin_ids)),\n        "disabled_mcp_server_names": sorted(set(disabled_mcp_server_names)),\n''',
    '''        "disabled_plugin_ids": sorted(set(disabled_plugin_ids)),\n        "effective_plugin_ids": sorted(set(effective_plugin_ids)),\n        "hidden_plugin_ids": sorted(set(hidden_plugin_ids)),\n        "disabled_plugin_mcp_servers": {\n            plugin_id: sorted(set(names))\n            for plugin_id, names in sorted(disabled_plugin_mcp_servers.items())\n        },\n        "disabled_mcp_server_names": sorted(set(disabled_mcp_server_names)),\n''',
    'record effective plugin inventory',
)
text = replace_once(
    text,
    '''        "disabled_plugin_ids": artifact.get("disabled_plugin_ids", []),\n        "disabled_mcp_server_names": artifact.get("disabled_mcp_server_names", []),\n''',
    '''        "disabled_plugin_ids": artifact.get("disabled_plugin_ids", []),\n        "effective_plugin_ids": artifact.get("effective_plugin_ids", []),\n        "hidden_plugin_ids": artifact.get("hidden_plugin_ids", []),\n        "disabled_plugin_mcp_servers": artifact.get("disabled_plugin_mcp_servers", {}),\n        "disabled_mcp_server_names": artifact.get("disabled_mcp_server_names", []),\n''',
    'include effective inventory in compact diagnostics',
)
text = replace_once(
    text,
    '''        disabled_plugins = candidate.get("disabled_plugin_ids", [])\n        if disabled_plugins:\n            print("  disabled-plugins: " + ", ".join(str(item) for item in disabled_plugins))\n        disabled_mcp_servers = candidate.get("disabled_mcp_server_names", [])\n''',
    '''        disabled_plugins = candidate.get("disabled_plugin_ids", [])\n        if disabled_plugins:\n            print("  disabled-plugins: " + ", ".join(str(item) for item in disabled_plugins))\n        hidden_plugins = candidate.get("hidden_plugin_ids", [])\n        if hidden_plugins:\n            print("  hidden-plugins: " + ", ".join(str(item) for item in hidden_plugins))\n        plugin_mcp_servers = candidate.get("disabled_plugin_mcp_servers", {})\n        if plugin_mcp_servers:\n            print(\n                "  disabled-plugin-mcps: "\n                + json.dumps(plugin_mcp_servers, ensure_ascii=False, sort_keys=True)\n            )\n        disabled_mcp_servers = candidate.get("disabled_mcp_server_names", [])\n''',
    'print effective plugin diagnostics',
)

text = replace_once(
    text,
    '''                disabled_skill_paths=baseline_disabled_skills,\n                disabled_plugin_ids=baseline_plugin_ids,\n                disabled_mcp_server_names=mcp_names,\n''',
    '''                disabled_skill_paths=baseline_disabled_skills,\n                disabled_plugin_ids=baseline_plugin_ids,\n                effective_plugin_ids=[],\n                hidden_plugin_ids=[],\n                disabled_plugin_mcp_servers={},\n                disabled_mcp_server_names=mcp_names,\n''',
    'record baseline empty effective inventory',
)

start = text.index('            installed_root = guard.install_candidate()\n')
end = text.index('            candidate_turn, candidate_home = run_live_variant(\n', start)
new_candidate_preflight = '''            installed_root = guard.install_candidate()\n            candidate_cli_plugin_ids = installed_plugin_ids(launchers)\n            (\n                candidate_inventory_command,\n                _,\n            ) = build_isolated_app_server_command(\n                launchers=launchers,\n                installed_plugin_ids=candidate_cli_plugin_ids,\n                mcp_server_names=mcp_names,\n                plugin_mcp_servers={},\n                plugins_enabled=True,\n                enabled_plugin_id=base.PLUGIN_ID,\n            )\n            with base.AppServer(\n                command=candidate_inventory_command,\n                node_executable=launchers.node_executable,\n                cwd=candidate_workspace,\n                trace_path=preflight_dir / "candidate-plugin-inventory-trace.jsonl",\n                timeout_seconds=args.timeout_seconds,\n            ) as candidate_inventory_server:\n                candidate_inventory_home = candidate_inventory_server.initialize()\n                candidate_effective_inventory = app_server_effective_plugin_inventory(\n                    candidate_inventory_server,\n                    candidate_workspace,\n                )\n                candidate_hidden_plugin_mcps = app_server_plugin_mcp_servers(\n                    candidate_inventory_server,\n                    candidate_effective_inventory,\n                    known_plugin_ids=set(candidate_cli_plugin_ids) | {base.PLUGIN_ID},\n                )\n            if base.normalized_path(candidate_inventory_home) != base.normalized_path(codex_home):\n                raise base.HarnessError(\n                    "candidate plugin inventory used a different Codex home directory."\n                )\n            candidate_effective_plugin_ids = sorted(\n                {str(item["id"]) for item in candidate_effective_inventory}\n            )\n            candidate_plugin_ids = sorted(\n                set(candidate_cli_plugin_ids)\n                | set(candidate_effective_plugin_ids)\n                | {base.PLUGIN_ID}\n            )\n            candidate_hidden_plugin_ids = sorted(\n                set(candidate_effective_plugin_ids)\n                - set(candidate_cli_plugin_ids)\n                - {base.PLUGIN_ID}\n            )\n            (\n                candidate_app_server_command,\n                candidate_startup_overrides,\n            ) = build_isolated_app_server_command(\n                launchers=launchers,\n                installed_plugin_ids=candidate_plugin_ids,\n                mcp_server_names=mcp_names,\n                plugin_mcp_servers=candidate_hidden_plugin_mcps,\n                plugins_enabled=True,\n                enabled_plugin_id=base.PLUGIN_ID,\n            )\n            with base.AppServer(\n                command=candidate_app_server_command,\n                node_executable=launchers.node_executable,\n                cwd=candidate_workspace,\n                trace_path=preflight_dir / "candidate-skills-trace.jsonl",\n                timeout_seconds=args.timeout_seconds,\n            ) as candidate_preflight:\n                candidate_preflight_home = candidate_preflight.initialize()\n                candidate_skills = candidate_preflight.skills_list(candidate_workspace)\n            if base.normalized_path(candidate_preflight_home) != base.normalized_path(codex_home):\n                raise base.HarnessError("candidate preflight used a different Codex home directory.")\n            (\n                candidate_config,\n                exposed_core,\n                candidate_disabled_skills,\n                candidate_disabled_plugins,\n            ) = build_candidate_session_config(\n                skills=candidate_skills,\n                installed_plugin_root=installed_root,\n                mcp_server_names=mcp_names,\n                installed_plugin_ids=candidate_plugin_ids,\n                plugin_mcp_servers=candidate_hidden_plugin_mcps,\n            )\n'''
text = text[:start] + new_candidate_preflight + text[end:]

text = replace_once(
    text,
    '''                disabled_skill_paths=candidate_disabled_skills,\n                disabled_plugin_ids=candidate_disabled_plugins,\n                disabled_mcp_server_names=mcp_names,\n''',
    '''                disabled_skill_paths=candidate_disabled_skills,\n                disabled_plugin_ids=candidate_disabled_plugins,\n                effective_plugin_ids=candidate_effective_plugin_ids,\n                hidden_plugin_ids=candidate_hidden_plugin_ids,\n                disabled_plugin_mcp_servers=candidate_hidden_plugin_mcps,\n                disabled_mcp_server_names=mcp_names,\n''',
    'record candidate effective inventory',
)

script_path.write_text(text, encoding="utf-8", newline="\n")


test_path = Path("tests/test_codex_negative_smoke.py")
tests = test_path.read_text(encoding="utf-8")
tests = replace_once(
    tests,
    '        self.assertEqual(module.CASE_REVISION, 2)',
    '        self.assertEqual(module.CASE_REVISION, 3)',
    'update case revision test',
)

inventory_test = '''\n    def test_effective_plugin_inventory_includes_hidden_curated_plugins(self) -> None:\n        payload = {\n            "marketplaces": [\n                {\n                    "name": "openai-api-curated",\n                    "path": "C:/codex/curated/marketplace.json",\n                    "plugins": [\n                        {\n                            "id": "fable-advisor@openai-api-curated",\n                            "name": "fable-advisor",\n                            "installed": True,\n                            "enabled": True,\n                        },\n                        {\n                            "id": "suggestion@openai-api-curated",\n                            "name": "suggestion",\n                            "installed": False,\n                            "enabled": False,\n                        },\n                    ],\n                },\n                {\n                    "name": base.MARKETPLACE_NAME,\n                    "path": "C:/foundation/marketplace.json",\n                    "plugins": [\n                        {\n                            "id": base.PLUGIN_ID,\n                            "name": base.PLUGIN_NAME,\n                            "installed": True,\n                            "enabled": True,\n                        }\n                    ],\n                },\n            ]\n        }\n        inventory = module.effective_plugin_inventory_from_payload(payload)\n        self.assertEqual(\n            [item["id"] for item in inventory],\n            [base.PLUGIN_ID, "fable-advisor@openai-api-curated"],\n        )\n        self.assertEqual(\n            inventory[1]["marketplace_path"],\n            "C:/codex/curated/marketplace.json",\n        )\n\n'''
tests = replace_once(
    tests,
    '    def test_fixture_fails_then_passes_after_exact_literal_edit(self) -> None:\n',
    inventory_test + '    def test_fixture_fails_then_passes_after_exact_literal_edit(self) -> None:\n',
    'add effective inventory regression test',
)

tests = replace_once(
    tests,
    '''                    mcp_server_names=["memory"],\n                    installed_plugin_ids=[base.PLUGIN_ID, foreign_plugin],\n''',
    '''                    mcp_server_names=["memory"],\n                    installed_plugin_ids=[base.PLUGIN_ID, foreign_plugin],\n                    plugin_mcp_servers={foreign_plugin: ["fable-advisor-python3"]},\n''',
    'pass plugin MCP session test input',
)
tests = replace_once(
    tests,
    '''            self.assertFalse(config["plugins"][foreign_plugin]["enabled"])\n''',
    '''            self.assertFalse(config["plugins"][foreign_plugin]["enabled"])\n            self.assertFalse(\n                config["plugins"][foreign_plugin]["mcp_servers"]\n                ["fable-advisor-python3"]["enabled"]\n            )\n''',
    'assert thread plugin MCP disablement',
)
tests = replace_once(
    tests,
    '''            mcp_server_names=["fable-advisor-python3", "server.with.dot"],\n            plugins_enabled=True,\n''',
    '''            mcp_server_names=["fable-advisor-python3", "server.with.dot"],\n            plugin_mcp_servers={foreign_plugin: ["fable-advisor-python3"]},\n            plugins_enabled=True,\n''',
    'pass startup plugin MCP test input',
)
tests = replace_once(
    tests,
    '''        self.assertFalse(plugin_table[foreign_plugin]["enabled"])\n        for override in overrides:\n''',
    '''        self.assertFalse(plugin_table[foreign_plugin]["enabled"])\n        self.assertFalse(\n            plugin_table[foreign_plugin]["mcp_servers"]\n            ["fable-advisor-python3"]["enabled"]\n        )\n        for override in overrides:\n''',
    'assert startup plugin MCP disablement',
)
tests = replace_once(
    tests,
    '''            mcp_server_names=["fable-advisor-python3"],\n            plugins_enabled=False,\n''',
    '''            mcp_server_names=["fable-advisor-python3"],\n            plugin_mcp_servers={},\n            plugins_enabled=False,\n''',
    'pass baseline empty plugin MCP input',
)
tests = replace_once(
    tests,
    '''                disabled_skill_paths=[],\n                disabled_plugin_ids=[],\n                disabled_mcp_server_names=["fable-advisor-python3"],\n''',
    '''                disabled_skill_paths=[],\n                disabled_plugin_ids=[],\n                effective_plugin_ids=[base.PLUGIN_ID],\n                hidden_plugin_ids=[],\n                disabled_plugin_mcp_servers={},\n                disabled_mcp_server_names=["fable-advisor-python3"],\n''',
    'update evaluation inventory evidence',
)
tests = replace_once(
    tests,
    '''                "disabled_plugin_ids": ["fable-advisor@foreign-marketplace"],\n                "disabled_mcp_server_names": ["fable-advisor-python3"],\n''',
    '''                "disabled_plugin_ids": ["fable-advisor@openai-api-curated"],\n                "effective_plugin_ids": [\n                    base.PLUGIN_ID,\n                    "fable-advisor@openai-api-curated",\n                ],\n                "hidden_plugin_ids": ["fable-advisor@openai-api-curated"],\n                "disabled_plugin_mcp_servers": {\n                    "fable-advisor@openai-api-curated": ["fable-advisor-python3"],\n                },\n                "disabled_mcp_server_names": ["fable-advisor-python3"],\n''',
    'update failure diagnostic inventory fixture',
)
tests = replace_once(
    tests,
    '''                payload["candidate"]["disabled_plugin_ids"],\n                ["fable-advisor@foreign-marketplace"],\n            )\n            self.assertEqual(\n                payload["candidate"]["disabled_mcp_server_names"],\n''',
    '''                payload["candidate"]["disabled_plugin_ids"],\n                ["fable-advisor@openai-api-curated"],\n            )\n            self.assertEqual(\n                payload["candidate"]["hidden_plugin_ids"],\n                ["fable-advisor@openai-api-curated"],\n            )\n            self.assertEqual(\n                payload["candidate"]["disabled_plugin_mcp_servers"],\n                {"fable-advisor@openai-api-curated": ["fable-advisor-python3"]},\n            )\n            self.assertEqual(\n                payload["candidate"]["disabled_mcp_server_names"],\n''',
    'assert failure diagnostic effective inventory',
)
test_path.write_text(tests, encoding="utf-8", newline="\n")


docs_path = Path("docs/live-smoke.md")
docs = docs_path.read_text(encoding="utf-8")
docs = replace_once(
    docs,
    "Foreign installed plugins and directly configured MCP servers are disabled before each app-server process starts and again at the thread layer; the remote plugin catalog, foreign user skills, apps, memories, and code mode remain disabled.",
    "Foreign installed plugins, API-curated or otherwise effective installed plugins discovered through app-server, and directly configured MCP servers are disabled before the measured candidate app-server starts and again at the thread layer; plugin-provided MCP servers from hidden effective plugins are explicitly disabled as defense in depth. The remote plugin catalog, foreign user skills, apps, memories, and code mode remain disabled.",
    'document effective plugin inventory isolation',
)
docs = replace_once(
    docs,
    "- app-server startup overrides disable the remote plugin catalog, every foreign installed plugin, and every directly configured MCP server before capabilities are loaded;",
    "- an unmeasured app-server inventory phase calls `plugin/installed` and `plugin/read` so API-curated or otherwise hidden effective plugins and their MCP server names are known before the measured candidate starts;\n- app-server startup overrides disable the remote plugin catalog, every foreign effective plugin, every discovered plugin-provided MCP server, and every directly configured MCP server before capabilities are loaded;",
    'document inventory validity control',
)
docs_path.write_text(docs, encoding="utf-8", newline="\n")


changelog_path = Path("CHANGELOG.md")
changelog = changelog_path.read_text(encoding="utf-8")
changelog = replace_once(
    changelog,
    "- Moved configured MCP-server isolation to app-server startup after thread-scoped disablement proved too late for eager MCP initialization.",
    "- Moved configured MCP-server isolation to app-server startup after thread-scoped disablement proved too late for eager MCP initialization.\n- Added an app-server effective-plugin inventory pass so API-curated plugins omitted by the CLI installed list, plus their plugin-provided MCP servers, are disabled before measured negative-smoke execution.",
    'record effective plugin inventory change',
)
changelog_path.write_text(changelog, encoding="utf-8", newline="\n")
