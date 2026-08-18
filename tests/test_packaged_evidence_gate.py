from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CORE_ROOT = ROOT / "plugins/engineering-foundation-core"
SKILL_ROOT = CORE_ROOT / "skills/verify-before-completion"
PACKAGED_GATE = SKILL_ROOT / "scripts/evidence_gate.py"
PACKAGED_RUNNER = SKILL_ROOT / "scripts/run_verifier_with_receipt.py"
ROOT_GATE = ROOT / "scripts/evidence_gate.py"

PACKAGE_SPEC = importlib.util.spec_from_file_location(
    "package_plugins_for_packaged_evidence_gate",
    ROOT / "scripts/package_plugins.py",
)
package_plugins = importlib.util.module_from_spec(PACKAGE_SPEC)
assert PACKAGE_SPEC.loader
PACKAGE_SPEC.loader.exec_module(package_plugins)


def core_catalog_entry() -> dict:
    catalog = json.loads((ROOT / "catalog/plugins.json").read_text(encoding="utf-8"))
    return next(
        plugin
        for plugin in catalog["plugins"]
        if plugin["name"] == "engineering-foundation-core"
    )


def run_gate(gate: Path, evidence: Path, contract: Path | None = None) -> subprocess.CompletedProcess[str]:
    command = [sys.executable, "-I", str(gate), str(evidence)]
    if contract is not None:
        command.extend(["--contract", str(contract)])
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    return subprocess.run(
        command,
        cwd=evidence.parent,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def write_minimal_core_plugin(repository: Path, *, include_helper: bool) -> Path:
    plugin_root = repository / "plugins/engineering-foundation-core"
    (plugin_root / ".codex-plugin").mkdir(parents=True)
    (plugin_root / ".claude-plugin").mkdir()
    skill_root = plugin_root / "skills/verify-before-completion"
    skill_root.mkdir(parents=True)
    for manifest in (
        plugin_root / "plugin.json",
        plugin_root / ".codex-plugin/plugin.json",
        plugin_root / ".claude-plugin/plugin.json",
    ):
        manifest.write_text("{}\n", encoding="utf-8")
    (skill_root / "SKILL.md").write_text(
        "---\nname: verify-before-completion\ndescription: fixture\n---\n",
        encoding="utf-8",
    )
    if include_helper:
        helper = skill_root / "scripts/evidence_gate.py"
        helper.parent.mkdir()
        helper.write_text("# fixture helper\n", encoding="utf-8")
        (helper.parent / "run_verifier_with_receipt.py").write_text(
            "# fixture receipt runner\n", encoding="utf-8"
        )
    return plugin_root


class PackagedEvidenceGateTests(unittest.TestCase):
    def build_and_extract_core(self, destination: Path) -> Path:
        archive, _ = package_plugins.build_archive(core_catalog_entry(), destination)
        extracted = destination / "extracted-core"
        extracted.mkdir()
        with zipfile.ZipFile(archive) as package:
            package.extractall(extracted)
        return extracted

    def copy_fixtures(self, destination: Path) -> tuple[Path, Path, Path, Path]:
        destination.mkdir()
        names = (
            "completion-evidence.pass.json",
            "completion-evidence.fail.json",
            "completion-evidence.partial.json",
            "task-contract.static-validation.json",
        )
        copied = []
        for name in names:
            target = destination / name
            shutil.copyfile(ROOT / "examples" / name, target)
            copied.append(target)
        return copied[0], copied[1], copied[2], copied[3]

    def test_skill_declares_a_resolvable_packaged_helper(self) -> None:
        skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("[scripts/evidence_gate.py](scripts/evidence_gate.py)", skill)
        self.assertIn(
            "[scripts/run_verifier_with_receipt.py](scripts/run_verifier_with_receipt.py)",
            skill,
        )
        self.assertTrue(PACKAGED_GATE.is_file())
        self.assertTrue(PACKAGED_RUNNER.is_file())

    def test_core_archive_contains_packaged_evidence_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive, _ = package_plugins.build_archive(core_catalog_entry(), Path(tmp))
            with zipfile.ZipFile(archive) as package:
                names = package.namelist()
                self.assertIn(
                    "skills/verify-before-completion/scripts/evidence_gate.py",
                    names,
                )
                self.assertIn(
                    "skills/verify-before-completion/scripts/run_verifier_with_receipt.py",
                    names,
                )
                self.assertFalse(any("__pycache__" in name for name in names))
                self.assertFalse(any(name.endswith((".pyc", ".pyo")) for name in names))

    def test_extracted_package_gate_runs_without_source_repository(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            extracted = self.build_and_extract_core(base)
            valid, _, _, contract = self.copy_fixtures(base / "consumer-workspace")
            gate = extracted / "skills/verify-before-completion/scripts/evidence_gate.py"

            result = run_gate(gate, valid, contract)

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("evidence gate: PASS", result.stdout)

    def test_extracted_package_gate_preserves_fail_closed_outcomes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            extracted = self.build_and_extract_core(base)
            valid, failed, partial, contract = self.copy_fixtures(base / "consumer-workspace")
            gate = extracted / "skills/verify-before-completion/scripts/evidence_gate.py"

            cases = ((valid, 0, "PASS"), (failed, 1, "FAIL"), (partial, 1, "FAIL"))
            for evidence, exit_code, status in cases:
                with self.subTest(evidence=evidence.name):
                    result = run_gate(gate, evidence, contract)
                    self.assertEqual(result.returncode, exit_code, result.stdout + result.stderr)
                    self.assertIn(f"evidence gate: {status}", result.stdout)

            invalid = valid.parent / "invalid-evidence.json"
            invalid.write_text("{not-json\n", encoding="utf-8")
            result = run_gate(gate, invalid, contract)
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertIn("cannot read evidence", result.stdout)
            self.assertNotIn("evidence gate: PASS", result.stdout)

    def test_root_entrypoint_matches_packaged_canonical_cli(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            valid, failed, partial, contract = self.copy_fixtures(Path(tmp) / "fixtures")
            for evidence in (valid, failed, partial):
                with self.subTest(evidence=evidence.name):
                    root_result = run_gate(ROOT_GATE, evidence, contract)
                    packaged_result = run_gate(PACKAGED_GATE, evidence, contract)
                    self.assertEqual(root_result.returncode, packaged_result.returncode)
                    self.assertEqual(root_result.stdout, packaged_result.stdout)
                    self.assertEqual(root_result.stderr, packaged_result.stderr)

    def test_root_entrypoint_does_not_write_package_bytecode(self) -> None:
        cache = PACKAGED_GATE.parent / "__pycache__"
        self.assertFalse(cache.exists(), f"generated cache must be removed before testing: {cache}")

        result = run_gate(
            ROOT_GATE,
            ROOT / "examples/completion-evidence.pass.json",
            ROOT / "examples/task-contract.static-validation.json",
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(cache.exists(), "root compatibility entry point wrote package bytecode")

    def test_package_builder_rejects_core_without_required_helper(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            repository = base / "repository"
            write_minimal_core_plugin(repository, include_helper=False)
            output = repository / "dist"
            output.mkdir(parents=True)
            plugin = {
                "name": "engineering-foundation-core",
                "version": "0.0.0",
                "path": "plugins/engineering-foundation-core",
            }

            original_root = package_plugins.ROOT
            package_plugins.ROOT = repository
            try:
                with self.assertRaisesRegex(ValueError, "evidence_gate.py"):
                    package_plugins.build_archive(plugin, output)
            finally:
                package_plugins.ROOT = original_root

    def test_package_builder_rejects_generated_python_cache(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            repository = base / "repository"
            plugin_root = write_minimal_core_plugin(repository, include_helper=True)
            cache = plugin_root / "skills/verify-before-completion/scripts/__pycache__"
            cache.mkdir()
            (cache / "evidence_gate.cpython-311.pyc").write_bytes(b"generated bytecode")
            output = repository / "dist"
            output.mkdir(parents=True)
            plugin = {
                "name": "engineering-foundation-core",
                "version": "0.0.0",
                "path": "plugins/engineering-foundation-core",
            }

            original_root = package_plugins.ROOT
            package_plugins.ROOT = repository
            try:
                with self.assertRaisesRegex(ValueError, "generated Python cache"):
                    package_plugins.build_archive(plugin, output)
            finally:
                package_plugins.ROOT = original_root

    def test_core_archive_has_no_dangling_local_markdown_links(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            extracted = self.build_and_extract_core(Path(tmp))
            for markdown in extracted.rglob("*.md"):
                text = markdown.read_text(encoding="utf-8")
                for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", text):
                    clean = target.split("#", 1)[0]
                    if not clean or "://" in clean or clean.startswith("mailto:"):
                        continue
                    resolved = (markdown.parent / clean).resolve()
                    self.assertTrue(
                        resolved.is_relative_to(extracted.resolve()),
                        f"{markdown.relative_to(extracted)} escapes package: {target}",
                    )
                    self.assertTrue(
                        resolved.exists(),
                        f"{markdown.relative_to(extracted)} -> {target}",
                    )


if __name__ == "__main__":
    unittest.main()
