from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "engineering-foundation"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


router = load_module("test_route_task", PLUGIN / "scripts" / "route_task.py")
gate = load_module("test_evidence_gate", PLUGIN / "scripts" / "evidence_gate.py")
validator = load_module("test_repository_validator", ROOT / "scripts" / "validate_repository.py")
installer = load_module(
    "test_install_codex_agents",
    PLUGIN / "scripts" / "install_codex_agents.py",
)


class RouterTests(unittest.TestCase):
    def test_small_coupled_task_stays_single_agent(self):
        result = router.route_task(
            {
                "risk": "low",
                "uncertainty": "low",
                "estimated_files": 3,
                "independent_workstreams": 1,
                "shared_write_surface": True,
                "specialist_domains": ["laravel"],
            }
        )
        self.assertEqual("single-agent", result["mode"])
        self.assertEqual([], result["specialists"])
        self.assertEqual("primary", result["completion_owner"])

    def test_read_heavy_independent_work_uses_bounded_multi_agent(self):
        result = router.route_task(
            {
                "risk": "medium",
                "uncertainty": "high",
                "estimated_files": 30,
                "independent_workstreams": 3,
                "shared_write_surface": False,
                "read_heavy": True,
            }
        )
        self.assertEqual("bounded-multi-agent", result["mode"])
        self.assertLessEqual(result["max_concurrent_specialists"], 3)
        self.assertEqual(1, result["delegation_depth"])

    def test_shared_high_risk_work_keeps_primary_writer(self):
        result = router.route_task(
            {
                "risk": "high",
                "uncertainty": "high",
                "estimated_files": 12,
                "independent_workstreams": 3,
                "shared_write_surface": True,
                "irreversible": True,
            }
        )
        self.assertEqual("single-agent-with-specialists", result["mode"])
        self.assertTrue(result["primary_writer"])

    def test_explicit_no_subagents_wins(self):
        result = router.route_task(
            {
                "risk": "critical",
                "uncertainty": "high",
                "estimated_files": 50,
                "independent_workstreams": 5,
                "shared_write_surface": False,
                "read_heavy": True,
                "explicit_no_subagents": True,
            }
        )
        self.assertEqual("single-agent", result["mode"])
        self.assertEqual(0, result["max_concurrent_specialists"])


class EvidenceGateTests(unittest.TestCase):
    def test_valid_packet_passes(self):
        payload = json.loads(
            (ROOT / "evals" / "evidence" / "01-pass.json").read_text(encoding="utf-8")
        )
        payload.pop("expected_pass")
        self.assertEqual([], gate.validate_packet(payload))

    def test_missing_evidence_fails(self):
        payload = json.loads(
            (ROOT / "evals" / "evidence" / "02-missing-evidence.json").read_text(
                encoding="utf-8"
            )
        )
        payload.pop("expected_pass")
        errors = gate.validate_packet(payload)
        self.assertTrue(any("evidence" in error for error in errors))
        self.assertTrue(any("fresh" in error for error in errors))
        self.assertTrue(any("diff_reviewed" in error for error in errors))

    def test_failed_command_fails(self):
        payload = json.loads(
            (ROOT / "evals" / "evidence" / "03-failed-command.json").read_text(
                encoding="utf-8"
            )
        )
        payload.pop("expected_pass")
        errors = gate.validate_packet(payload)
        self.assertTrue(any("exit_code" in error for error in errors))
        self.assertTrue(any("unresolved" in error for error in errors))


class InstallerTests(unittest.TestCase):
    def test_installer_never_overwrites_conflict_without_force(self):
        source = PLUGIN / "adapters" / "codex" / "agents"
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            conflict = target / "reviewer.toml"
            conflict.write_text("different\n", encoding="utf-8")
            actions = installer.plan_install(source, target, force=False)
            status = {item["target"]: item["status"] for item in actions}
            self.assertEqual("conflict", status[str(conflict)])

    def test_installer_marks_identical_files(self):
        source = PLUGIN / "adapters" / "codex" / "agents"
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            sample = source / "researcher.toml"
            (target / sample.name).write_bytes(sample.read_bytes())
            actions = installer.plan_install(source, target, force=False)
            item = next(item for item in actions if item["target"].endswith(sample.name))
            self.assertEqual("identical", item["status"])


class RepositoryValidationTests(unittest.TestCase):
    def test_repository_is_valid(self):
        errors, warnings = validator.validate_repository()
        self.assertEqual([], errors)
        self.assertEqual([], warnings)


if __name__ == "__main__":
    unittest.main()
