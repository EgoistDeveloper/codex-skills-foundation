from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "run_codex_bounded_delegation_smoke_v2",
    ROOT / "scripts/run_codex_bounded_delegation_smoke_v2.py",
)
module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = module
assert SPEC.loader
SPEC.loader.exec_module(module)


class CodexBoundedDelegationSmokeV2Tests(unittest.TestCase):
    def test_case_revision_is_two(self) -> None:
        self.assertEqual(module.CASE_REVISION, 2)

    def test_prompt_requires_real_native_delegation(self) -> None:
        prompt = module.DELEGATION_PROMPT
        normalized = prompt.lower()
        self.assertIn("spawn_agent", prompt)
        self.assertIn("zorunlu parçasıdır", normalized)
        self.assertIn("en az bir, en fazla üç", normalized)
        self.assertIn("tek başına tamamlama", normalized)
        self.assertNotIn("kullanabilirsin", normalized)

    def test_session_config_pins_default_v1_collaboration_surface(self) -> None:
        def safe_builder(**_: Any) -> dict[str, Any]:
            return {"features": {"plugins": False}}

        config = module.session_config(
            safe_session_builder=safe_builder,
            disabled_skill_paths=[],
            disabled_mcp_names=[],
            plugin_ids=[module.delegation.base.PLUGIN_ID],
            enable_core=True,
        )
        self.assertTrue(config["features"]["multi_agent"])
        self.assertFalse(config["features"]["multi_agent_v2"])
        self.assertTrue(config["include_collaboration_mode_instructions"])
        self.assertTrue(config["plugins"][module.delegation.base.PLUGIN_ID]["enabled"])

    def test_revision_contract_patches_established_harness(self) -> None:
        original_revision = module.delegation.CASE_REVISION
        original_prompt = module.delegation.DELEGATION_PROMPT
        original_builder = module.delegation.session_config
        try:
            module.apply_revision_contract()
            self.assertEqual(module.delegation.CASE_REVISION, module.CASE_REVISION)
            self.assertEqual(module.delegation.DELEGATION_PROMPT, module.DELEGATION_PROMPT)
            self.assertIs(module.delegation.session_config, module.session_config)
        finally:
            module.delegation.CASE_REVISION = original_revision
            module.delegation.DELEGATION_PROMPT = original_prompt
            module.delegation.session_config = original_builder


if __name__ == "__main__":
    unittest.main()
