from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one match, found {count}")
    return text.replace(old, new, 1)


script_path = Path("scripts/run_codex_negative_smoke.py")
text = script_path.read_text(encoding="utf-8")

text = replace_once(
    text,
    "CASE_REVISION = 1",
    "CASE_REVISION = 2",
    "bump negative case revision",
)

text = replace_once(
    text,
    '''def toml_bool(value: bool) -> str:
    return "true" if value else "false"


def plugin_table_override''',
    '''def toml_bool(value: bool) -> str:
    return "true" if value else "false"


def toml_dotted_key_segment(value: str) -> str:
    if value and all(
        character.isascii() and (character.isalnum() or character in "_-")
        for character in value
    ):
        return value
    return json.dumps(value, ensure_ascii=True)


def plugin_table_override''',
    "insert TOML dotted-key helper",
)

text = replace_once(
    text,
    '''    launchers: base.CodexLaunchers,
    installed_plugin_ids: list[str],
    plugins_enabled: bool,
    enabled_plugin_id: str | None,
) -> tuple[tuple[str, ...], list[str]]:
    plugin_ids = sorted(set(installed_plugin_ids))
''',
    '''    launchers: base.CodexLaunchers,
    installed_plugin_ids: list[str],
    mcp_server_names: list[str],
    plugins_enabled: bool,
    enabled_plugin_id: str | None,
) -> tuple[tuple[str, ...], list[str]]:
    plugin_ids = sorted(set(installed_plugin_ids))
    mcp_names = sorted(set(mcp_server_names))
''',
    "extend startup command inputs",
)

text = replace_once(
    text,
    '''    if plugin_states:
        overrides.append(plugin_table_override(plugin_states))

    command: list[str] = [*launchers.cli_prefix, "app-server"]
''',
    '''    if plugin_states:
        overrides.append(plugin_table_override(plugin_states))
    overrides.extend(
        f"mcp_servers.{toml_dotted_key_segment(name)}.enabled=false"
        for name in mcp_names
    )

    command: list[str] = [*launchers.cli_prefix, "app-server"]
''',
    "add startup MCP overrides",
)

text = replace_once(
    text,
    '''    disabled_skill_paths: list[str],
    disabled_plugin_ids: list[str],
    startup_config_overrides: list[str],
    exposed_core_skills: dict[str, str],
) -> NegativeEvaluation:
''',
    '''    disabled_skill_paths: list[str],
    disabled_plugin_ids: list[str],
    disabled_mcp_server_names: list[str],
    startup_config_overrides: list[str],
    exposed_core_skills: dict[str, str],
) -> NegativeEvaluation:
''',
    "extend evaluation MCP evidence",
)

text = replace_once(
    text,
    '''        "disabled_plugin_ids": sorted(set(disabled_plugin_ids)),
        "startup_config_overrides": list(startup_config_overrides),
''',
    '''        "disabled_plugin_ids": sorted(set(disabled_plugin_ids)),
        "disabled_mcp_server_names": sorted(set(disabled_mcp_server_names)),
        "startup_config_overrides": list(startup_config_overrides),
''',
    "record disabled MCP servers",
)

text = replace_once(
    text,
    '''        "disabled_plugin_ids": artifact.get("disabled_plugin_ids", []),
        "startup_config_overrides": artifact.get("startup_config_overrides", []),
''',
    '''        "disabled_plugin_ids": artifact.get("disabled_plugin_ids", []),
        "disabled_mcp_server_names": artifact.get("disabled_mcp_server_names", []),
        "startup_config_overrides": artifact.get("startup_config_overrides", []),
''',
    "include MCP evidence in diagnostics",
)

text = replace_once(
    text,
    '''        disabled_plugins = candidate.get("disabled_plugin_ids", [])
        if disabled_plugins:
            print("  disabled-plugins: " + ", ".join(str(item) for item in disabled_plugins))
        startup_overrides = candidate.get("startup_config_overrides", [])
''',
    '''        disabled_plugins = candidate.get("disabled_plugin_ids", [])
        if disabled_plugins:
            print("  disabled-plugins: " + ", ".join(str(item) for item in disabled_plugins))
        disabled_mcp_servers = candidate.get("disabled_mcp_server_names", [])
        if disabled_mcp_servers:
            print(
                "  disabled-mcp-servers: "
                + ", ".join(str(item) for item in disabled_mcp_servers)
            )
        startup_overrides = candidate.get("startup_config_overrides", [])
''',
    "print disabled MCP diagnostics",
)

text = replace_once(
    text,
    '''            guard.snapshot_config(codex_home)
            guard.prepare_baseline()
            baseline_plugin_ids = installed_plugin_ids(launchers)
''',
    '''            guard.snapshot_config(codex_home)
            mcp_names = base.configured_mcp_server_names(codex_home)
            guard.prepare_baseline()
            baseline_plugin_ids = installed_plugin_ids(launchers)
''',
    "discover MCP servers before isolated startup",
)

text = replace_once(
    text,
    '''                launchers=launchers,
                installed_plugin_ids=baseline_plugin_ids,
                plugins_enabled=False,
''',
    '''                launchers=launchers,
                installed_plugin_ids=baseline_plugin_ids,
                mcp_server_names=mcp_names,
                plugins_enabled=False,
''',
    "pass baseline MCP startup inventory",
)

text = replace_once(
    text,
    '''
            mcp_names = base.configured_mcp_server_names(codex_home)
            baseline_disabled_skills = base.enabled_skill_paths(baseline_skills)
''',
    '''
            baseline_disabled_skills = base.enabled_skill_paths(baseline_skills)
''',
    "remove late MCP discovery",
)

text = replace_once(
    text,
    '''                disabled_skill_paths=baseline_disabled_skills,
                disabled_plugin_ids=baseline_plugin_ids,
                startup_config_overrides=baseline_startup_overrides,
''',
    '''                disabled_skill_paths=baseline_disabled_skills,
                disabled_plugin_ids=baseline_plugin_ids,
                disabled_mcp_server_names=mcp_names,
                startup_config_overrides=baseline_startup_overrides,
''',
    "record baseline MCP startup inventory",
)

text = replace_once(
    text,
    '''                launchers=launchers,
                installed_plugin_ids=candidate_plugin_ids,
                plugins_enabled=True,
''',
    '''                launchers=launchers,
                installed_plugin_ids=candidate_plugin_ids,
                mcp_server_names=mcp_names,
                plugins_enabled=True,
''',
    "pass candidate MCP startup inventory",
)

text = replace_once(
    text,
    '''                disabled_skill_paths=candidate_disabled_skills,
                disabled_plugin_ids=candidate_disabled_plugins,
                startup_config_overrides=candidate_startup_overrides,
''',
    '''                disabled_skill_paths=candidate_disabled_skills,
                disabled_plugin_ids=candidate_disabled_plugins,
                disabled_mcp_server_names=mcp_names,
                startup_config_overrides=candidate_startup_overrides,
''',
    "record candidate MCP startup inventory",
)

script_path.write_text(text, encoding="utf-8", newline="\n")


test_path = Path("tests/test_codex_negative_smoke.py")
tests = test_path.read_text(encoding="utf-8")

tests = replace_once(
    tests,
    '''        for bare_name in module.FORBIDDEN_SKILL_BARE_NAMES:
            self.assertNotIn(bare_name, module.NEGATIVE_PROMPT)
''',
    '''        for bare_name in module.FORBIDDEN_SKILL_BARE_NAMES:
            self.assertNotIn(bare_name, module.NEGATIVE_PROMPT)
        self.assertEqual(module.CASE_REVISION, 2)
''',
    "assert negative case revision",
)

tests = replace_once(
    tests,
    '''            installed_plugin_ids=[base.PLUGIN_ID, foreign_plugin],
            plugins_enabled=True,
''',
    '''            installed_plugin_ids=[base.PLUGIN_ID, foreign_plugin],
            mcp_server_names=["fable-advisor-python3", "server.with.dot"],
            plugins_enabled=True,
''',
    "add candidate MCP startup test input",
)

tests = replace_once(
    tests,
    '''        self.assertIn("features.apps=false", overrides)
        plugin_override = next(value for value in overrides if value.startswith("plugins="))
''',
    '''        self.assertIn("features.apps=false", overrides)
        self.assertIn("mcp_servers.fable-advisor-python3.enabled=false", overrides)
        self.assertIn('mcp_servers."server.with.dot".enabled=false', overrides)
        plugin_override = next(value for value in overrides if value.startswith("plugins="))
''',
    "assert candidate MCP startup overrides",
)

tests = replace_once(
    tests,
    '''            installed_plugin_ids=[foreign_plugin],
            plugins_enabled=False,
''',
    '''            installed_plugin_ids=[foreign_plugin],
            mcp_server_names=["fable-advisor-python3"],
            plugins_enabled=False,
''',
    "add baseline MCP startup test input",
)

tests = replace_once(
    tests,
    '''        self.assertIn("features.remote_plugin=false", overrides)
        plugin_override = next(value for value in overrides if value.startswith("plugins="))
''',
    '''        self.assertIn("features.remote_plugin=false", overrides)
        self.assertIn("mcp_servers.fable-advisor-python3.enabled=false", overrides)
        plugin_override = next(value for value in overrides if value.startswith("plugins="))
''',
    "assert baseline MCP startup override",
)

tests = replace_once(
    tests,
    '''                disabled_skill_paths=[],
                disabled_plugin_ids=[],
                startup_config_overrides=["features.remote_plugin=false"],
''',
    '''                disabled_skill_paths=[],
                disabled_plugin_ids=[],
                disabled_mcp_server_names=["fable-advisor-python3"],
                startup_config_overrides=["features.remote_plugin=false"],
''',
    "update evaluation MCP evidence",
)

tests = replace_once(
    tests,
    '''                "disabled_plugin_ids": ["fable-advisor@foreign-marketplace"],
                "token_usage": {},
''',
    '''                "disabled_plugin_ids": ["fable-advisor@foreign-marketplace"],
                "disabled_mcp_server_names": ["fable-advisor-python3"],
                "token_usage": {},
''',
    "add failure diagnostic MCP evidence",
)

tests = replace_once(
    tests,
    '''            self.assertEqual(
                payload["candidate"]["disabled_plugin_ids"],
                ["fable-advisor@foreign-marketplace"],
            )
            self.assertIn(
''',
    '''            self.assertEqual(
                payload["candidate"]["disabled_plugin_ids"],
                ["fable-advisor@foreign-marketplace"],
            )
            self.assertEqual(
                payload["candidate"]["disabled_mcp_server_names"],
                ["fable-advisor-python3"],
            )
            self.assertIn(
''',
    "assert failure diagnostic MCP evidence",
)

test_path.write_text(tests, encoding="utf-8", newline="\n")


docs_path = Path("docs/live-smoke.md")
docs = docs_path.read_text(encoding="utf-8")
docs = replace_once(
    docs,
    "Foreign installed plugins are disabled before each app-server process starts and again at the thread layer; the remote plugin catalog, foreign user skills, apps, memories, code mode, and configured MCP servers remain disabled.",
    "Foreign installed plugins and directly configured MCP servers are disabled before each app-server process starts and again at the thread layer; the remote plugin catalog, foreign user skills, apps, memories, and code mode remain disabled.",
    "document process-level MCP isolation",
)
docs = replace_once(
    docs,
    "- app-server startup overrides disable the remote plugin catalog and every foreign installed plugin before plugin capabilities are loaded;",
    "- app-server startup overrides disable the remote plugin catalog, every foreign installed plugin, and every directly configured MCP server before capabilities are loaded;",
    "strengthen validity-control documentation",
)
docs_path.write_text(docs, encoding="utf-8", newline="\n")


changelog_path = Path("CHANGELOG.md")
changelog = changelog_path.read_text(encoding="utf-8")
changelog = replace_once(
    changelog,
    "- Moved negative-smoke plugin isolation to app-server startup, disabled the remote plugin catalog for the campaign, and retained thread-level isolation as defense in depth.",
    "- Moved negative-smoke plugin isolation to app-server startup, disabled the remote plugin catalog for the campaign, and retained thread-level isolation as defense in depth.\n- Moved configured MCP-server isolation to app-server startup after thread-scoped disablement proved too late for eager MCP initialization.",
    "record MCP startup isolation change",
)
changelog_path.write_text(changelog, encoding="utf-8", newline="\n")
