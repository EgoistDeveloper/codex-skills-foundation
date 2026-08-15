from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "run_codex_core_repeatability_entrypoint",
    ROOT / "scripts/run_codex_core_repeatability.py",
)
module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = module
assert SPEC.loader
SPEC.loader.exec_module(module)
base = module.base


class CodexCoreRepeatabilityEntrypointTests(unittest.TestCase):
    def test_entrypoint_reexports_campaign_api(self) -> None:
        plan = module.build_plan(2)
        self.assertEqual(len(plan), 4)
        self.assertEqual(module.DEFAULT_REPETITIONS, 3)

    def test_plugin_state_comparison_normalizes_marketplace_paths(self) -> None:
        left = base.OriginalPluginState(
            marketplace_existed=True,
            marketplace_root=str(ROOT),
            plugin_installed=True,
            plugin_enabled=True,
            plugin_version="0.2.2",
        )
        right = base.OriginalPluginState(
            marketplace_existed=True,
            marketplace_root=str(ROOT / "."),
            plugin_installed=True,
            plugin_enabled=True,
            plugin_version="0.2.2",
        )
        self.assertTrue(module.plugin_states_equal(left, right))
        self.assertFalse(
            module.plugin_states_equal(
                left,
                base.OriginalPluginState(
                    marketplace_existed=True,
                    marketplace_root=str(ROOT),
                    plugin_installed=False,
                    plugin_enabled=False,
                    plugin_version=None,
                ),
            )
        )

    def test_campaign_state_guard_restores_exact_state_and_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            codex_home = Path(tmp) / ".codex"
            codex_home.mkdir()
            config = codex_home / "config.toml"
            config.write_bytes(b"original = true\n")

            original = base.OriginalPluginState(
                marketplace_existed=False,
                marketplace_root=None,
                plugin_installed=False,
                plugin_enabled=False,
                plugin_version=None,
            )
            modified = base.OriginalPluginState(
                marketplace_existed=True,
                marketplace_root=str(ROOT),
                plugin_installed=True,
                plugin_enabled=True,
                plugin_version="0.2.2",
            )
            state_box = {"value": original}

            class FakePluginStateGuard:
                def __init__(self, **_: Any) -> None:
                    self.original = original
                    self.codex_home: Path | None = None
                    self.config_existed = False
                    self.config_snapshot: bytes | None = None
                    self.marketplace_added = False

                def snapshot_config(self, home: Path) -> None:
                    self.codex_home = home
                    target = home / "config.toml"
                    self.config_existed = target.exists()
                    self.config_snapshot = target.read_bytes()

                def __exit__(self, exc_type: object, exc: object, tb: object) -> bool:
                    state_box["value"] = original
                    assert self.codex_home is not None
                    assert self.config_snapshot is not None
                    (self.codex_home / "config.toml").write_bytes(self.config_snapshot)
                    return False

            class FakeAppServer:
                def __init__(self, **_: Any) -> None:
                    pass

                def __enter__(self) -> "FakeAppServer":
                    return self

                def __exit__(self, exc_type: object, exc: object, tb: object) -> bool:
                    return False

                def initialize(self) -> Path:
                    return codex_home

            launchers = base.CodexLaunchers(
                cli_prefix=("node", "codex.js"),
                app_server_command=(
                    "node",
                    "codex.js",
                    "app-server",
                    "--listen",
                    "stdio://",
                ),
                node_executable="node",
                version_text="codex-cli 0.147.0",
                version=(0, 147, 0),
            )

            original_guard = base.PluginStateGuard
            original_server = base.AppServer
            original_reader = base.read_plugin_state
            base.PluginStateGuard = FakePluginStateGuard
            base.AppServer = FakeAppServer
            base.read_plugin_state = lambda _launchers, _root: state_box["value"]
            try:
                guard = module.CampaignStateGuard(
                    launchers=launchers,
                    subject_version="0.2.2",
                )
                with guard:
                    state_box["value"] = modified
                    config.write_bytes(b"modified = true\n")
            finally:
                base.PluginStateGuard = original_guard
                base.AppServer = original_server
                base.read_plugin_state = original_reader

            self.assertTrue(guard.restored)
            self.assertTrue(guard.config_restored)
            self.assertEqual(config.read_bytes(), b"original = true\n")
            self.assertEqual(guard.evidence()["current"], guard.evidence()["original"])

    def test_parent_state_evidence_updates_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            campaign = Path(tmp) / "campaign"
            campaign.mkdir()
            module._impl.atomic_write_json(
                campaign / "manifest.json",
                {
                    "schema_version": 1,
                    "campaign": campaign.name,
                    "outcome": "INTERRUPTED",
                },
            )

            class FakeGuard:
                restored = True

                @staticmethod
                def evidence() -> dict[str, Any]:
                    return {
                        "schema_version": 1,
                        "restored": True,
                        "config_restored": True,
                        "restore_error": None,
                    }

            evidence_path = module.write_parent_state_evidence(
                campaign,
                FakeGuard(),
            )
            payload = json.loads(evidence_path.read_text(encoding="utf-8"))
            manifest = json.loads(
                (campaign / "manifest.json").read_text(encoding="utf-8")
            )
            self.assertTrue(payload["restored"])
            self.assertTrue(manifest["parent_state_restored"])
            self.assertEqual(
                manifest["parent_state_evidence"],
                "parent-state-restoration.json",
            )


if __name__ == "__main__":
    unittest.main()
