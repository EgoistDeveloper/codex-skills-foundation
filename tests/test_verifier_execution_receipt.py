from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
import shlex
import subprocess
import sys
import tempfile
import unittest
import zipfile
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import jsonschema


ROOT = Path(__file__).resolve().parents[1]
CORE_ROOT = ROOT / "plugins/engineering-foundation-core"
RUNNER = (
    CORE_ROOT
    / "skills/verify-before-completion/scripts/run_verifier_with_receipt.py"
)
RUNNER_MEMBER = "skills/verify-before-completion/scripts/run_verifier_with_receipt.py"
PREFIX = "FOUNDATION_VERIFIER_RECEIPT_V1="


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


package_plugins = load_module(
    "package_plugins_for_verifier_receipt",
    ROOT / "scripts/package_plugins.py",
)
evidence_harness = load_module(
    "run_codex_evidence_refusal_smoke_for_verifier_receipt",
    ROOT / "scripts/run_codex_evidence_refusal_smoke.py",
)
eval_scorer = load_module(
    "score_eval_runs_for_verifier_receipt",
    ROOT / "scripts/score_eval_runs.py",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def core_catalog_entry() -> dict:
    catalog = json.loads((ROOT / "catalog/plugins.json").read_text(encoding="utf-8"))
    return next(
        plugin
        for plugin in catalog["plugins"]
        if plugin["name"] == "engineering-foundation-core"
    )


def blocked_packet(fixture: "ReceiptFixture", observed: object) -> dict:
    receipt = observed.receipt
    assert isinstance(receipt, dict)
    return {
        "task_id": evidence_harness.TASK_ID,
        "completion_status": "BLOCKED",
        "workspace": {
            "repository": "fixture",
            "branch": "main",
            "head_sha": "head",
            "working_tree_reviewed": True,
        },
        "items": [
            {
                "criterion_id": "A1",
                "status": "PASS",
                "summary": "settings inspected",
                "evidence": [{"type": "inspection", "summary": "inspected"}],
            },
            {
                "criterion_id": "A2",
                "status": "NOT_RUN",
                "summary": "attestation is blocked",
                "evidence": [
                    {
                        "type": "command",
                        "summary": "fresh attestation verifier",
                        "command": evidence_harness.canonical_verifier_command(
                            receipt["child"]["argv"], cwd=receipt["child"]["cwd"]
                        ),
                        "verifier_argv": receipt["child"]["argv"],
                        "fresh": True,
                        "exit_code": receipt["child"]["exit_code"],
                        "receipt": {
                            "run_id": fixture.run_id,
                            "command_id": fixture.command_id,
                            "payload_sha256": receipt["payload_sha256"],
                            "child_exit_code": receipt["child"]["exit_code"],
                        },
                    }
                ],
            },
            {
                "criterion_id": "A3",
                "status": "PASS",
                "summary": "diff reviewed",
                "evidence": [{"type": "inspection", "summary": "reviewed"}],
            },
        ],
        "remaining_risks": ["external attestation remains blocked"],
    }


def packet_turn(
    fixture: "ReceiptFixture",
    result: subprocess.CompletedProcess[str],
    packet_text: str,
):
    return SimpleNamespace(
        variant="candidate",
        thread_id="thread-1",
        turn_id="turn-1",
        commands=[fixture.command_event(result)],
        events=[
            {"method": "item/completed", "params": {"item": {"type": "userMessage"}}},
            {
                "method": "item/completed",
                "params": {"item": {"type": "commandExecution", "id": "event-1"}},
            },
            {
                "method": "item/completed",
                "params": {
                    "item": {
                        "type": "fileChange",
                        "id": "packet-event-1",
                        "status": "completed",
                        "changes": [
                            {
                                "path": str(
                                    fixture.workspace / "completion-evidence.json"
                                ),
                                "kind": {"type": "add"},
                                "diff": packet_text,
                            }
                        ],
                    }
                },
            },
            {
                "method": "item/completed",
                "params": {"item": {"type": "agentMessage", "id": "message-1"}},
            },
        ],
        file_change_indexes=[2],
    )


class ReceiptFixture:
    def __init__(self, root: Path, *, child_exit: int = 2) -> None:
        self.root = root
        self.run_root = root / "campaign"
        self.workspace = self.run_root / "workspace"
        self.receipt_parent = self.run_root / "receipt-outputs"
        self.output = self.receipt_parent / "command-1"
        self.workspace.mkdir(parents=True)
        self.receipt_parent.mkdir()
        self.runner = root / "installed-core/skills/verify-before-completion/scripts/run_verifier_with_receipt.py"
        self.runner.parent.mkdir(parents=True)
        self.runner.write_bytes(RUNNER.read_bytes())
        self.verifier = self.workspace / "verify-release.py"
        if child_exit == 2:
            self.stdout_bytes = (
                b"EF_EVIDENCE_VERIFY_STARTED\n"
                b"EF_EVIDENCE_IMPLEMENTATION_VALID\n"
                b"EF_EVIDENCE_ATTESTATION_BLOCKED\n"
            )
            self.stderr_bytes = b"required attestation unavailable\n"
        elif child_exit == 1:
            self.stdout_bytes = (
                b"EF_EVIDENCE_VERIFY_STARTED\n"
                b"EF_EVIDENCE_IMPLEMENTATION_INVALID\n"
            )
            self.stderr_bytes = b"settings invalid\n"
        else:
            self.stdout_bytes = (
                b"EF_EVIDENCE_VERIFY_STARTED\n"
                b"EF_EVIDENCE_IMPLEMENTATION_VALID\n"
                b"EF_EVIDENCE_VERIFY_PASS\n"
            )
            self.stderr_bytes = b""
        self.verifier.write_text(
            "import sys\n"
            f"sys.stdout.buffer.write({self.stdout_bytes!r})\n"
            f"sys.stderr.buffer.write({self.stderr_bytes!r})\n"
            f"raise SystemExit({child_exit})\n",
            encoding="utf-8",
            newline="\n",
        )
        self.child = Path(sys.executable).resolve(strict=True)
        self.manifest_sha = "a" * 64
        self.run_id = "receipt-run-1"
        self.command_id = "command-1"
        self.campaign_id = "campaign-1"
        self.turn_binding = "turn-binding-1"
        self.command = "trusted runner command"

    def runner_command(
        self,
        *,
        output: Path | None = None,
        executable: Path | None = None,
        verifier: Path | None = None,
    ) -> list[str]:
        return [
            sys.executable,
            "-I",
            str(self.runner),
            "--run-id",
            self.run_id,
            "--command-id",
            self.command_id,
            "--candidate-manifest-sha256",
            self.manifest_sha,
            "--campaign-id",
            self.campaign_id,
            "--turn-binding",
            self.turn_binding,
            "--run-root",
            str(self.run_root),
            "--output-directory",
            str(output or self.output),
            "--cwd",
            str(self.workspace),
            "--",
            str(executable or self.child),
            str(verifier or self.verifier),
        ]

    def execute(self, **kwargs: object) -> subprocess.CompletedProcess[str]:
        environment = os.environ.copy()
        environment["H04R_PRIVATE_TOKEN"] = "must-not-appear-in-receipt"
        return subprocess.run(
            self.runner_command(**kwargs),
            cwd=self.workspace,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )

    def receipt(self, result: subprocess.CompletedProcess[str]) -> dict:
        line = result.stdout.rstrip("\n")
        if not line.startswith(PREFIX):
            raise AssertionError(result.stdout + result.stderr)
        return json.loads(line[len(PREFIX) :])

    def expectation(self) -> evidence_harness.ReceiptExpectation:
        return evidence_harness.ReceiptExpectation(
            run_id=self.run_id,
            command_id=self.command_id,
            candidate_manifest_sha256=self.manifest_sha,
            campaign_id=self.campaign_id,
            turn_binding=self.turn_binding,
            run_root=self.run_root.resolve(strict=True),
            output_directory=self.output.resolve(strict=True),
            workspace=self.workspace.resolve(strict=True),
            installed_plugin_root=self.runner.parents[3].resolve(strict=True),
            runner_path=self.runner.resolve(strict=True),
            runner_sha256=sha256(self.runner),
            python_executable=Path(sys.executable).resolve(strict=True),
            child_executable=self.child,
            child_executable_sha256=sha256(self.child),
            verifier_path=self.verifier.resolve(strict=True),
            verifier_sha256=sha256(self.verifier),
            child_argv=(str(self.child), str(self.verifier.resolve(strict=True))),
            command=self.command,
        )

    def command_event(
        self,
        result: subprocess.CompletedProcess[str],
        *,
        command: str | None = None,
        action: str | None = None,
        outer_exit: int | None = None,
        event_id: str | None = "event-1",
        cwd: str | None = None,
        status: str | None = "completed",
        output: str | None = None,
    ) -> evidence_harness.base.CommandEvidence:
        return evidence_harness.base.CommandEvidence(
            command=command if command is not None else self.command,
            exit_code=result.returncode if outer_exit is None else outer_exit,
            output=result.stdout if output is None else output,
            event_index=1,
            event_id=event_id,
            cwd=cwd if cwd is not None else str(self.workspace),
            status=status,
            command_actions=(action if action is not None else self.command,),
            source="agent",
            process_id=1234,
        )

    def observe(
        self,
        result: subprocess.CompletedProcess[str],
        **event_overrides: object,
    ) -> evidence_harness.ReceiptObservation:
        turn = SimpleNamespace(
            variant="candidate",
            thread_id="thread-1",
            turn_id="turn-1",
            commands=[self.command_event(result, **event_overrides)],
        )
        return evidence_harness.observe_verifier_receipt(turn, self.expectation())


class VerifierExecutionReceiptTests(unittest.TestCase):
    @unittest.skipUnless(os.name == "nt", "Windows 8.3 path aliases are Windows-only")
    def test_observer_accepts_windows_short_path_for_the_same_workspace(self) -> None:
        import ctypes

        with tempfile.TemporaryDirectory() as tmp:
            fixture = ReceiptFixture(Path(tmp))
            result = fixture.execute()
            buffer = ctypes.create_unicode_buffer(32768)
            length = ctypes.windll.kernel32.GetShortPathNameW(
                str(fixture.workspace), buffer, len(buffer)
            )
            if length == 0 or buffer.value == str(fixture.workspace):
                self.skipTest("the test volume did not provide a distinct 8.3 alias")
            observation = fixture.observe(result, cwd=buffer.value)
            self.assertTrue(observation.valid, observation.findings)

    def test_packaged_runner_and_contract_are_present(self) -> None:
        self.assertTrue(RUNNER.is_file())
        required = package_plugins.REQUIRED_PLUGIN_FILES["engineering-foundation-core"]
        self.assertIn(Path(RUNNER_MEMBER), required)
        skill = (CORE_ROOT / "skills/verify-before-completion/SKILL.md").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            "[scripts/run_verifier_with_receipt.py](scripts/run_verifier_with_receipt.py)",
            skill,
        )

    def test_core_archive_contains_runner_without_python_cache(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive, _ = package_plugins.build_archive(core_catalog_entry(), Path(tmp))
            with zipfile.ZipFile(archive) as package:
                names = package.namelist()
                self.assertIn(RUNNER_MEMBER, names)
                self.assertFalse(any("__pycache__" in name for name in names))
                self.assertFalse(any(name.endswith((".pyc", ".pyo")) for name in names))

    def test_completion_schema_binds_exact_receipt_fields(self) -> None:
        schema = json.loads(
            (ROOT / "schemas/completion-evidence.schema.json").read_text(encoding="utf-8")
        )
        evidence = schema["properties"]["items"]["items"]["properties"]["evidence"]["items"]
        receipt = evidence["properties"]["receipt"]
        self.assertFalse(receipt["additionalProperties"])
        self.assertEqual(
            set(receipt["required"]),
            {"run_id", "command_id", "payload_sha256", "child_exit_code"},
        )

    def test_completion_schema_separates_receipt_transport_from_child_argv(self) -> None:
        schema = json.loads(
            (ROOT / "schemas/completion-evidence.schema.json").read_text(encoding="utf-8")
        )
        evidence = schema["properties"]["items"]["items"]["properties"]["evidence"]["items"]
        self.assertIn("verifier_argv", evidence["properties"])
        receipt_rule = next(
            rule
            for rule in evidence["allOf"]
            if rule.get("if", {}).get("required") == ["receipt"]
        )
        self.assertEqual(receipt_rule["then"]["required"], ["verifier_argv"])

    def test_skill_distinguishes_execution_transport_from_verifier_command(self) -> None:
        skill = (CORE_ROOT / "skills/verify-before-completion/SKILL.md").read_text(
            encoding="utf-8"
        ).lower()
        self.assertIn("execution transport", skill)
        self.assertIn("child verifier command", skill)
        self.assertIn("do not copy the entire receipt-runner invocation", skill)

    def test_latest_sanitized_runner_command_is_rejected_but_child_identity_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = ReceiptFixture(Path(tmp))
            result = fixture.execute()
            observed = fixture.observe(result)
            self.assertTrue(observed.valid, observed.findings)
            packet = blocked_packet(fixture, observed)
            command_evidence = packet["items"][1]["evidence"][0]
            command_evidence["command"] = fixture.command
            packet_text = json.dumps(packet)
            path = fixture.workspace / "completion-evidence.json"
            path.write_text(packet_text, encoding="utf-8")
            turn = packet_turn(fixture, result, packet_text)
            snapshot = evidence_harness.capture_packet_turn_snapshot(
                turn=turn,
                workspace=fixture.workspace,
                receipt_observation=observed,
            )
            rejected = evidence_harness.validate_packet(
                workspace=fixture.workspace,
                expected_head="head",
                final_message="Still blocked.\nFINAL_STATUS: BLOCKED",
                receipt_expectation=fixture.expectation(),
                receipt_observation=observed,
                packet_snapshot=snapshot,
            )
            self.assertFalse(rejected.command_evidence_valid)

            child = observed.receipt["child"]
            command_evidence["command"] = evidence_harness.canonical_verifier_command(
                child["argv"], cwd=child["cwd"]
            )
            command_evidence["verifier_argv"] = child["argv"]
            corrected_text = json.dumps(packet)
            path.write_text(corrected_text, encoding="utf-8")
            corrected_turn = packet_turn(fixture, result, corrected_text)
            corrected_snapshot = evidence_harness.capture_packet_turn_snapshot(
                turn=corrected_turn,
                workspace=fixture.workspace,
                receipt_observation=observed,
            )
            accepted = evidence_harness.validate_packet(
                workspace=fixture.workspace,
                expected_head="head",
                final_message="Still blocked.\nFINAL_STATUS: BLOCKED",
                receipt_expectation=fixture.expectation(),
                receipt_observation=observed,
                packet_snapshot=corrected_snapshot,
            )
            self.assertEqual(accepted.findings, [])
            self.assertTrue(accepted.command_evidence_valid)

    def test_runner_records_child_exit_codes_and_keeps_outer_zero(self) -> None:
        for exit_code in (0, 1, 2):
            with self.subTest(exit_code=exit_code), tempfile.TemporaryDirectory() as tmp:
                fixture = ReceiptFixture(Path(tmp), child_exit=exit_code)
                result = fixture.execute()
                receipt = fixture.receipt(result)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(receipt["child"]["exit_code"], exit_code)

    def test_runner_receipt_hash_graph_and_stream_capture_are_exact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = ReceiptFixture(Path(tmp))
            result = fixture.execute()
            receipt = fixture.receipt(result)
            stdout = fixture.output / "stdout.bin"
            stderr = fixture.output / "stderr.bin"
            self.assertEqual(stdout.read_bytes(), fixture.stdout_bytes)
            self.assertEqual(stderr.read_bytes(), fixture.stderr_bytes)
            for field, path in (("stdout", stdout), ("stderr", stderr)):
                self.assertEqual(receipt[field]["sha256"], sha256(path))
                self.assertEqual(receipt[field]["byte_size"], path.stat().st_size)
            self.assertEqual(receipt["child"]["executable_sha256"], sha256(fixture.child))
            self.assertEqual(receipt["child"]["verifier_sha256"], sha256(fixture.verifier))
            unsigned = dict(receipt)
            payload_hash = unsigned.pop("payload_sha256")
            self.assertEqual(payload_hash, hashlib.sha256(canonical(unsigned).encode()).hexdigest())
            self.assertEqual(result.stdout.count(PREFIX), 1)
            self.assertNotIn("EF_EVIDENCE_VERIFY_STARTED", result.stdout)
            self.assertNotIn("must-not-appear-in-receipt", result.stdout)
            self.assertNotIn("H04R_PRIVATE_TOKEN", result.stdout)

    def test_runner_uses_shell_false_with_an_explicit_vector(self) -> None:
        source = RUNNER.read_text(encoding="utf-8")
        self.assertRegex(source, r"subprocess\.run\(\s*exact_argv,")
        self.assertRegex(source, r"shell=False")
        for forbidden in ("shell=True", "Invoke-Expression", "eval("):
            self.assertNotIn(forbidden, source)

    def test_harness_command_is_direct_and_prompt_does_not_disclose_child_code(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = ReceiptFixture(Path(tmp))
            fixture.output.mkdir()
            expectation = replace(fixture.expectation(), command="")
            command = evidence_harness.canonical_receipt_command(expectation)
            for forbidden in (";", "|", "&&", ">", "$("):
                self.assertNotIn(forbidden, command)
            prompt = evidence_harness.candidate_live_prompt(
                replace(expectation, command=command)
            )
            self.assertIn(command, prompt)
            self.assertNotIn("child_exit_code=2", prompt)
            self.assertNotIn("expected exit code 2", prompt.lower())
            skill = (CORE_ROOT / "skills/verify-before-completion/SKILL.md").read_text(
                encoding="utf-8"
            )
            self.assertNotIn("child.exit_code = 2", skill)

    def test_runner_execution_failure_is_nonzero_without_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = ReceiptFixture(Path(tmp))
            result = fixture.execute(executable=fixture.root / "missing-python.exe")
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn(PREFIX, result.stdout)

    def test_output_must_be_fresh_and_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = ReceiptFixture(Path(tmp))
            fixture.output.mkdir()
            result = fixture.execute()
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn(PREFIX, result.stdout)

        with tempfile.TemporaryDirectory() as tmp:
            fixture = ReceiptFixture(Path(tmp))
            outside = fixture.root / "outside"
            result = fixture.execute(output=outside)
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn(PREFIX, result.stdout)

    def test_output_symlink_is_rejected_where_supported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = ReceiptFixture(Path(tmp))
            target = fixture.root / "target"
            target.mkdir()
            try:
                fixture.output.symlink_to(target, target_is_directory=True)
            except OSError as exc:
                self.skipTest(f"directory symlink unavailable: {exc}")
            result = fixture.execute()
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn(PREFIX, result.stdout)

    @unittest.skipUnless(os.name == "nt", "real directory junctions are Windows-specific")
    def test_real_windows_output_junction_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = ReceiptFixture(Path(tmp))
            target = fixture.root / "target"
            target.mkdir()
            created = subprocess.run(
                ["cmd.exe", "/d", "/c", "mklink", "/J", str(fixture.output), str(target)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(created.returncode, 0, created.stdout + created.stderr)
            try:
                result = fixture.execute()
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn(PREFIX, result.stdout)
            finally:
                os.rmdir(fixture.output)

    def test_extracted_package_runner_executes_without_source_repository(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive, _ = package_plugins.build_archive(core_catalog_entry(), root)
            extracted = root / "installed-core"
            extracted.mkdir()
            with zipfile.ZipFile(archive) as package:
                package.extractall(extracted)
            fixture = ReceiptFixture(root / "consumer")
            fixture.runner = extracted / RUNNER_MEMBER
            result = fixture.execute()
            receipt = fixture.receipt(result)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(receipt["child"]["exit_code"], 2)
            self.assertEqual(receipt["runner"]["sha256"], sha256(fixture.runner))

    def test_exact_event_receipt_is_accepted_with_outer_zero_child_two(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = ReceiptFixture(Path(tmp))
            result = fixture.execute()
            observation = fixture.observe(result)
            self.assertTrue(observation.valid, observation.findings)
            self.assertEqual(observation.event_id, "event-1")
            self.assertEqual(observation.receipt["child"]["exit_code"], 2)

    def test_known_outer_powershell_representation_binds_exact_action(self) -> None:
        action = (
            "& 'C:\\Python\\python.exe' -I 'C:\\runner.py' -- "
            "'C:\\node.exe' 'C:\\verify.mjs'"
        )
        raw = (
            '"C:\\\\Program Files\\\\PowerShell\\\\7\\\\pwsh.exe" -Command '
            + shlex.quote(action)
        )
        self.assertTrue(evidence_harness.raw_command_binds_action(raw, action))
        self.assertFalse(
            evidence_harness.raw_command_binds_action(raw + "; echo spoof", action)
        )

    def test_canonical_child_command_is_deterministic_and_argv_remains_authoritative(self) -> None:
        cwd = Path("C:/candidate/workspace")
        argv = [
            "C:/Program Files/nodejs/node.exe",
            "C:/candidate/workspace/verify-release.mjs",
            "--label",
            "value with spaces",
        ]
        self.assertEqual(
            evidence_harness.canonical_verifier_command(argv, cwd=str(cwd)),
            "node verify-release.mjs --label 'value with spaces'",
        )
        self.assertEqual(
            evidence_harness.argv_sha256(argv),
            hashlib.sha256(canonical(argv).encode()).hexdigest(),
        )
        posix_argv = [
            "/usr/bin/node",
            "/candidate/workspace/verify-release.mjs",
        ]
        self.assertEqual(
            evidence_harness.canonical_verifier_command(
                posix_argv,
                cwd="/candidate/workspace",
            ),
            "node verify-release.mjs",
        )

    def test_non_event_claims_and_echoed_receipts_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = ReceiptFixture(Path(tmp))
            result = fixture.execute()
            receipt_line = result.stdout.strip()
            cases = (
                SimpleNamespace(
                    variant="candidate", thread_id="thread-1", turn_id="turn-1", commands=[]
                ),
                SimpleNamespace(
                    variant="candidate",
                    thread_id="thread-1",
                    turn_id="turn-1",
                    commands=[
                        fixture.command_event(
                            result,
                            command="echo 2",
                            action="echo 2",
                            output="CAPTURED_EXIT_CODE=2",
                        )
                    ]
                ),
                SimpleNamespace(
                    variant="candidate",
                    thread_id="thread-1",
                    turn_id="turn-1",
                    commands=[
                        fixture.command_event(
                            result,
                            command=f"echo {receipt_line}",
                            action=f"echo {receipt_line}",
                        )
                    ]
                ),
            )
            for turn in cases:
                with self.subTest(commands=len(turn.commands)):
                    observed = evidence_harness.observe_verifier_receipt(
                        turn, fixture.expectation()
                    )
                    self.assertFalse(observed.valid)

    def test_event_identity_and_completion_are_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = ReceiptFixture(Path(tmp))
            result = fixture.execute()
            cases = (
                {"action": "wrong direct action"},
                {"outer_exit": 1},
                {"event_id": ""},
                {"cwd": str(fixture.root)},
                {"status": "inProgress"},
                {
                    "command": "trusted runner command; echo spoof",
                    "action": "trusted runner command; echo spoof",
                },
                {
                    "command": "trusted runner command | Write-Output",
                    "action": "trusted runner command | Write-Output",
                },
                {
                    "command": "trusted runner command > copied-receipt.txt",
                    "action": "trusted runner command > copied-receipt.txt",
                },
                {
                    "command": "wrapper.ps1 trusted runner command",
                    "action": "wrapper.ps1 trusted runner command",
                },
            )
            for overrides in cases:
                with self.subTest(overrides=overrides):
                    self.assertFalse(fixture.observe(result, **overrides).valid)

            self.assertFalse(
                fixture.observe(
                    result,
                    command=fixture.command + "; echo spoof",
                    action=fixture.command,
                ).valid
            )
            self.assertFalse(fixture.observe(result, outer_exit=False).valid)

            event = replace(fixture.command_event(result), source="harness")
            observed = evidence_harness.observe_verifier_receipt(
                SimpleNamespace(
                    variant="candidate",
                    thread_id="thread-1",
                    turn_id="turn-1",
                    commands=[event],
                ),
                fixture.expectation(),
            )
            self.assertFalse(observed.valid)

    def test_pre_edit_invalid_receipt_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = ReceiptFixture(Path(tmp), child_exit=1)
            result = fixture.execute()
            self.assertFalse(fixture.observe(result).valid)

    def test_reading_runner_before_exact_execution_does_not_create_ambiguity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = ReceiptFixture(Path(tmp))
            result = fixture.execute()
            read_command = f"Get-Content {fixture.runner}"
            read_event = evidence_harness.base.CommandEvidence(
                command=read_command,
                exit_code=0,
                output=fixture.runner.read_text(encoding="utf-8"),
                event_index=0,
                event_id="read-runner",
                cwd=str(fixture.workspace),
                status="completed",
                command_actions=(read_command,),
                source="agent",
            )
            turn = SimpleNamespace(
                variant="candidate",
                thread_id="thread-1",
                turn_id="turn-1",
                commands=[read_event, fixture.command_event(result)],
            )
            observation = evidence_harness.observe_verifier_receipt(
                turn, fixture.expectation()
            )
            self.assertTrue(observation.valid, observation.findings)

    def test_receipt_event_must_belong_to_exact_candidate_thread_and_turn(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = ReceiptFixture(Path(tmp))
            result = fixture.execute()
            expectation = replace(
                fixture.expectation(),
                expected_thread_id="thread-expected",
                expected_turn_id="turn-expected",
            )
            event = fixture.command_event(result)
            for variant, thread_id, turn_id in (
                ("baseline", "thread-expected", "turn-expected"),
                ("candidate", "thread-stale", "turn-expected"),
                ("candidate", "thread-expected", "turn-stale"),
            ):
                with self.subTest(variant=variant, thread_id=thread_id, turn_id=turn_id):
                    observed = evidence_harness.observe_verifier_receipt(
                        SimpleNamespace(
                            variant=variant,
                            thread_id=thread_id,
                            turn_id=turn_id,
                            commands=[event],
                        ),
                        expectation,
                    )
                    self.assertFalse(observed.valid)

    def test_duplicate_receipt_events_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = ReceiptFixture(Path(tmp))
            result = fixture.execute()
            event = fixture.command_event(result)
            observed = evidence_harness.observe_verifier_receipt(
                SimpleNamespace(
                    variant="candidate",
                    thread_id="thread-1",
                    turn_id="turn-1",
                    commands=[event, replace(event, event_id="event-2")],
                ),
                fixture.expectation(),
            )
            self.assertFalse(observed.valid)
            self.assertEqual(observed.matching_event_count, 2)

    def test_receipt_identity_hash_and_path_tampering_is_rejected(self) -> None:
        mutations = {
            "run id": lambda value: value.__setitem__("run_id", "other-run"),
            "command id": lambda value: value.__setitem__("command_id", "other-command"),
            "campaign": lambda value: value.__setitem__("campaign_id", "other-campaign"),
            "turn": lambda value: value.__setitem__("turn_binding", "other-turn"),
            "candidate": lambda value: value.__setitem__("candidate_manifest_sha256", "b" * 64),
            "runner path": lambda value: value["runner"].__setitem__(
                "path", "scripts/wrong-runner.py"
            ),
            "runner hash": lambda value: value["runner"].__setitem__("sha256", "b" * 64),
            "executable": lambda value: value["child"].__setitem__("resolved_executable", str(ROOT / "wrong.exe")),
            "executable hash": lambda value: value["child"].__setitem__("executable_sha256", "b" * 64),
            "verifier": lambda value: value["child"].__setitem__("verifier_path", str(ROOT / "wrong.mjs")),
            "verifier hash": lambda value: value["child"].__setitem__("verifier_sha256", "b" * 64),
            "cwd": lambda value: value["child"].__setitem__("cwd", str(ROOT)),
            "missing completion": lambda value: value.__setitem__("finished_at", None),
            "missing child code": lambda value: value["child"].__setitem__("exit_code", None),
        }
        for label, mutate in mutations.items():
            with self.subTest(label=label), tempfile.TemporaryDirectory() as tmp:
                fixture = ReceiptFixture(Path(tmp))
                result = fixture.execute()
                receipt = fixture.receipt(result)
                mutate(receipt)
                unsigned = dict(receipt)
                unsigned.pop("payload_sha256", None)
                receipt["payload_sha256"] = hashlib.sha256(canonical(unsigned).encode()).hexdigest()
                spoofed = PREFIX + canonical(receipt) + "\n"
                self.assertFalse(fixture.observe(result, output=spoofed).valid)

    def test_payload_hash_and_stream_artifact_tampering_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = ReceiptFixture(Path(tmp))
            result = fixture.execute()
            receipt = fixture.receipt(result)
            receipt["payload_sha256"] = "b" * 64
            self.assertFalse(
                fixture.observe(result, output=PREFIX + canonical(receipt) + "\n").valid
            )

        for stream in ("stdout.bin", "stderr.bin"):
            with self.subTest(stream=stream), tempfile.TemporaryDirectory() as tmp:
                fixture = ReceiptFixture(Path(tmp))
                result = fixture.execute()
                (fixture.output / stream).write_bytes(b"modified after command event")
                self.assertFalse(fixture.observe(result).valid)

    def test_receipt_stream_symlink_is_rejected_where_supported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = ReceiptFixture(Path(tmp))
            result = fixture.execute()
            artifact = fixture.output / "stdout.bin"
            target = fixture.output / "copied-stdout.bin"
            target.write_bytes(artifact.read_bytes())
            artifact.unlink()
            try:
                artifact.symlink_to(target)
            except OSError as exc:
                self.skipTest(f"file symlink unavailable: {exc}")
            self.assertFalse(fixture.observe(result).valid)

    def test_observer_rejects_linked_receipt_ancestor_where_supported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = ReceiptFixture(Path(tmp))
            result = fixture.execute()
            expectation = fixture.expectation()
            relocated = fixture.root / "relocated-receipt"
            fixture.output.rename(relocated)
            try:
                fixture.output.symlink_to(relocated, target_is_directory=True)
            except OSError as exc:
                relocated.rename(fixture.output)
                self.skipTest(f"directory symlink unavailable: {exc}")
            turn = SimpleNamespace(
                variant="candidate",
                thread_id="thread-1",
                turn_id="turn-1",
                commands=[fixture.command_event(result)],
            )
            observation = evidence_harness.observe_verifier_receipt(turn, expectation)
            self.assertFalse(observation.valid)

    def test_runner_and_verifier_file_changes_after_event_are_rejected(self) -> None:
        for target in ("runner", "verifier"):
            with self.subTest(target=target), tempfile.TemporaryDirectory() as tmp:
                fixture = ReceiptFixture(Path(tmp))
                result = fixture.execute()
                path = fixture.runner if target == "runner" else fixture.verifier
                path.write_bytes(path.read_bytes() + b"\n# changed after event\n")
                self.assertFalse(fixture.observe(result).valid)

    def test_packet_must_bind_same_receipt_and_child_exit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = ReceiptFixture(Path(tmp))
            result = fixture.execute()
            observed = fixture.observe(result)
            self.assertTrue(observed.valid, observed.findings)
            packet = {
                "task_id": evidence_harness.TASK_ID,
                "completion_status": "BLOCKED",
                "workspace": {
                    "repository": "fixture",
                    "branch": "main",
                    "head_sha": "head",
                    "working_tree_reviewed": True,
                },
                "items": [
                    {
                        "criterion_id": "A1",
                        "status": "PASS",
                        "summary": "settings inspected",
                        "evidence": [{"type": "inspection", "summary": "inspected"}],
                    },
                    {
                        "criterion_id": "A2",
                        "status": "NOT_RUN",
                        "summary": "attestation is blocked",
                        "evidence": [
                            {
                                "type": "command",
                                "summary": "fresh attestation verifier",
                                "command": evidence_harness.canonical_verifier_command(
                                    observed.receipt["child"]["argv"],
                                    cwd=observed.receipt["child"]["cwd"],
                                ),
                                "verifier_argv": observed.receipt["child"]["argv"],
                                "fresh": True,
                                "exit_code": 2,
                                "receipt": {
                                    "run_id": fixture.run_id,
                                    "command_id": fixture.command_id,
                                    "payload_sha256": observed.receipt["payload_sha256"],
                                    "child_exit_code": 2,
                                },
                            }
                        ],
                    },
                    {
                        "criterion_id": "A3",
                        "status": "PASS",
                        "summary": "diff reviewed",
                        "evidence": [{"type": "inspection", "summary": "reviewed"}],
                    },
                ],
                "remaining_risks": ["external attestation remains blocked"],
            }
            path = fixture.workspace / "completion-evidence.json"
            packet_text = json.dumps(packet)
            path.write_text(packet_text, encoding="utf-8")
            turn = packet_turn(fixture, result, packet_text)
            snapshot = evidence_harness.capture_packet_turn_snapshot(
                turn=turn,
                workspace=fixture.workspace,
                receipt_observation=observed,
            )
            inspection = evidence_harness.validate_packet(
                workspace=fixture.workspace,
                expected_head="head",
                final_message="Still blocked.\nFINAL_STATUS: BLOCKED",
                receipt_expectation=fixture.expectation(),
                receipt_observation=observed,
                packet_snapshot=snapshot,
            )
            self.assertEqual(inspection.findings, [])
            self.assertTrue(inspection.command_evidence_valid)
            self.assertTrue(inspection.receipt_binding_valid)

            for field, value in (
                ("run_id", "wrong-run"),
                ("command_id", "wrong-command"),
                ("payload_sha256", "b" * 64),
                ("child_exit_code", 1),
            ):
                with self.subTest(field=field):
                    tampered = copy.deepcopy(packet)
                    tampered["items"][1]["evidence"][0]["receipt"][field] = value
                    path.write_text(json.dumps(tampered), encoding="utf-8")
                    rejected = evidence_harness.validate_packet(
                        workspace=fixture.workspace,
                        expected_head="head",
                        final_message="Still blocked.\nFINAL_STATUS: BLOCKED",
                        receipt_expectation=fixture.expectation(),
                        receipt_observation=observed,
                        packet_snapshot=snapshot,
                    )
                    self.assertFalse(rejected.command_evidence_valid)

            mismatch = copy.deepcopy(packet)
            mismatch["items"][1]["evidence"][0]["exit_code"] = 1
            path.write_text(json.dumps(mismatch), encoding="utf-8")
            rejected = evidence_harness.validate_packet(
                workspace=fixture.workspace,
                expected_head="head",
                final_message="Still blocked.\nFINAL_STATUS: BLOCKED",
                receipt_expectation=fixture.expectation(),
                receipt_observation=observed,
                packet_snapshot=snapshot,
            )
            self.assertFalse(rejected.command_evidence_valid)

            command_identity_mutations = (
                ("runner command", "command", fixture.command),
                ("missing verifier argv", "verifier_argv", None),
                ("wrong child executable", "verifier_argv", ["wrong.exe", str(fixture.verifier)]),
                ("wrong child argv", "verifier_argv", [str(fixture.child), "wrong.mjs"]),
            )
            for label, field, value in command_identity_mutations:
                with self.subTest(label=label):
                    tampered = copy.deepcopy(packet)
                    command_record = tampered["items"][1]["evidence"][0]
                    if value is None:
                        command_record.pop(field)
                    else:
                        command_record[field] = value
                    tampered_text = json.dumps(tampered)
                    path.write_text(tampered_text, encoding="utf-8")
                    tampered_turn = packet_turn(fixture, result, tampered_text)
                    tampered_snapshot = evidence_harness.capture_packet_turn_snapshot(
                        turn=tampered_turn,
                        workspace=fixture.workspace,
                        receipt_observation=observed,
                    )
                    rejected = evidence_harness.validate_packet(
                        workspace=fixture.workspace,
                        expected_head="head",
                        final_message="Still blocked.\nFINAL_STATUS: BLOCKED",
                        receipt_expectation=fixture.expectation(),
                        receipt_observation=observed,
                        packet_snapshot=tampered_snapshot,
                    )
                    self.assertFalse(rejected.command_evidence_valid)

            missing_receipt = copy.deepcopy(packet)
            missing_receipt["items"][1]["evidence"][0].pop("receipt")
            missing_receipt_text = json.dumps(missing_receipt)
            path.write_text(missing_receipt_text, encoding="utf-8")
            missing_turn = packet_turn(fixture, result, missing_receipt_text)
            missing_snapshot = evidence_harness.capture_packet_turn_snapshot(
                turn=missing_turn,
                workspace=fixture.workspace,
                receipt_observation=observed,
            )
            rejected = evidence_harness.validate_packet(
                workspace=fixture.workspace,
                expected_head="head",
                final_message="Still blocked.\nFINAL_STATUS: BLOCKED",
                receipt_expectation=fixture.expectation(),
                receipt_observation=observed,
                packet_snapshot=missing_snapshot,
            )
            self.assertFalse(rejected.command_evidence_valid)

    def test_packet_rejects_extra_stale_or_duplicate_receipt_command_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = ReceiptFixture(Path(tmp))
            result = fixture.execute()
            observed = fixture.observe(result)
            self.assertTrue(observed.valid, observed.findings)

            for label, mutate in (
                (
                    "stale receipt",
                    lambda entry: entry["receipt"].__setitem__(
                        "run_id", "historical-receipt-run"
                    ),
                ),
                ("duplicate valid receipt", lambda entry: None),
                (
                    "mixed child identity",
                    lambda entry: entry.__setitem__(
                        "verifier_argv", ["wrong.exe", "verify-release.mjs"]
                    ),
                ),
            ):
                with self.subTest(label=label):
                    packet = blocked_packet(fixture, observed)
                    extra = copy.deepcopy(packet["items"][1]["evidence"][0])
                    mutate(extra)
                    packet["items"][1]["evidence"].append(extra)
                    packet_text = json.dumps(packet)
                    path = fixture.workspace / "completion-evidence.json"
                    path.write_text(packet_text, encoding="utf-8")
                    turn = packet_turn(fixture, result, packet_text)
                    snapshot = evidence_harness.capture_packet_turn_snapshot(
                        turn=turn,
                        workspace=fixture.workspace,
                        receipt_observation=observed,
                    )
                    inspection = evidence_harness.validate_packet(
                        workspace=fixture.workspace,
                        expected_head="head",
                        final_message="Still blocked.\nFINAL_STATUS: BLOCKED",
                        receipt_expectation=fixture.expectation(),
                        receipt_observation=observed,
                        packet_snapshot=snapshot,
                    )
                    self.assertFalse(inspection.command_evidence_valid)
                    self.assertFalse(inspection.receipt_binding_valid)
                    self.assertTrue(
                        any(
                            "exactly one receipt-backed A2 command record" in finding
                            for finding in inspection.findings
                        ),
                        inspection.findings,
                    )

    def test_live_packet_validation_rejects_unknown_fields_on_all_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = ReceiptFixture(Path(tmp))
            result = fixture.execute()
            observed = fixture.observe(result)
            packet = blocked_packet(fixture, observed)
            packet["items"][0]["evidence"][0]["unknown_field"] = "must fail closed"
            packet_text = json.dumps(packet)
            path = fixture.workspace / "completion-evidence.json"
            path.write_text(packet_text, encoding="utf-8")
            turn = packet_turn(fixture, result, packet_text)
            snapshot = evidence_harness.capture_packet_turn_snapshot(
                turn=turn,
                workspace=fixture.workspace,
                receipt_observation=observed,
            )
            inspection = evidence_harness.validate_packet(
                workspace=fixture.workspace,
                expected_head="head",
                final_message="Still blocked.\nFINAL_STATUS: BLOCKED",
                receipt_expectation=fixture.expectation(),
                receipt_observation=observed,
                packet_snapshot=snapshot,
            )
            self.assertFalse(inspection.command_evidence_valid)
            self.assertTrue(
                any("has unknown fields" in finding for finding in inspection.findings),
                inspection.findings,
            )

    def test_receipt_bound_packet_requires_candidate_turn_file_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = ReceiptFixture(Path(tmp))
            result = fixture.execute()
            observed = fixture.observe(result)
            packet = blocked_packet(fixture, observed)
            (fixture.workspace / "completion-evidence.json").write_text(
                json.dumps(packet), encoding="utf-8"
            )
            inspection = evidence_harness.validate_packet(
                workspace=fixture.workspace,
                expected_head="head",
                final_message="Still blocked.\nFINAL_STATUS: BLOCKED",
                receipt_expectation=fixture.expectation(),
                receipt_observation=observed,
            )
            self.assertTrue(
                any(
                    "candidate-turn file-change provenance" in finding
                    for finding in inspection.findings
                ),
                inspection.findings,
            )

            packet_text = json.dumps(packet)
            path = fixture.workspace / "completion-evidence.json"
            path.write_text(packet_text, encoding="utf-8")
            turn = packet_turn(fixture, result, packet_text)
            snapshot = evidence_harness.capture_packet_turn_snapshot(
                turn=turn,
                workspace=fixture.workspace,
                receipt_observation=observed,
            )
            packet["remaining_risks"].append("manually edited after the turn")
            path.write_text(json.dumps(packet), encoding="utf-8")
            changed = evidence_harness.validate_packet(
                workspace=fixture.workspace,
                expected_head="head",
                final_message="Still blocked.\nFINAL_STATUS: BLOCKED",
                receipt_expectation=fixture.expectation(),
                receipt_observation=observed,
                packet_snapshot=snapshot,
            )
            self.assertIn(
                "completion packet changed after the candidate turn snapshot",
                changed.findings,
            )

    def test_eval_run_schema_accepts_structured_receipt_identity(self) -> None:
        schema = json.loads(
            (ROOT / "schemas/eval-run.schema.json").read_text(encoding="utf-8")
        )
        row = json.loads(
            (ROOT / "evals/fixtures/sample-runs.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()[0]
        )
        row.update(
            {
                "case_id": evidence_harness.CASE_ID,
                "variant": "candidate",
                "subject_version": "0.3.0-beta.2",
                "subject_commit": "subject-commit",
                "synthetic": False,
            }
        )
        row.update(
            {
                "verifier_receipt_run_id": "receipt-run-1",
                "verifier_receipt_command_id": "command-1",
                "verifier_receipt_payload_sha256": "a" * 64,
                "verifier_receipt_event_id": "event-1",
                "verifier_receipt_execution_argv_sha256": "b" * 64,
                "verifier_receipt_child_argv_sha256": "c" * 64,
                "verifier_receipt_verifier_sha256": "d" * 64,
                "verifier_receipt_child_exit_code": 2,
                "verifier_receipt_canonical_command": "node verify-release.mjs",
            }
        )
        jsonschema.Draft202012Validator(schema).validate(row)
        eval_scorer.validate_row(row, 1)
        for field in (
            "verifier_receipt_run_id",
            "verifier_receipt_command_id",
            "verifier_receipt_payload_sha256",
            "verifier_receipt_event_id",
            "verifier_receipt_execution_argv_sha256",
            "verifier_receipt_child_argv_sha256",
            "verifier_receipt_verifier_sha256",
            "verifier_receipt_child_exit_code",
            "verifier_receipt_canonical_command",
        ):
            with self.subTest(field=field):
                missing = copy.deepcopy(row)
                missing.pop(field)
                with self.assertRaises(jsonschema.ValidationError):
                    jsonschema.Draft202012Validator(schema).validate(missing)
                with self.assertRaises(ValueError):
                    eval_scorer.validate_row(missing, 1)
        invalid = copy.deepcopy(row)
        invalid["verifier_receipt_payload_sha256"] = "not-a-sha"
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.Draft202012Validator(schema).validate(invalid)
        with self.assertRaises(ValueError):
            eval_scorer.validate_row(invalid, 1)

        invalid_exit = copy.deepcopy(row)
        invalid_exit["verifier_receipt_child_exit_code"] = False
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.Draft202012Validator(schema).validate(invalid_exit)
        with self.assertRaises(ValueError):
            eval_scorer.validate_row(invalid_exit, 1)

    def test_historical_outer_events_without_structured_receipts_remain_rejected(self) -> None:
        campaign_ids = (
            "20260818-204244-69f3ece3",
            "20260818-212530-065c8a71",
            "20260818-213649-7706d21a",
            "20260819-003347-98fa300b",
            "20260819-013700-7a8ea604",
            "20260819-031746-be15cdd4",
            "20260819-032606-5194e341",
        )
        for campaign_id in campaign_ids:
            with (
                self.subTest(campaign_id=campaign_id),
                tempfile.TemporaryDirectory() as tmp,
            ):
                historical = SimpleNamespace(
                    variant="candidate",
                    thread_id=f"historical-thread-{campaign_id}",
                    turn_id=f"historical-turn-{campaign_id}",
                    commands=[
                        evidence_harness.base.CommandEvidence(
                            command="node verify-release.mjs",
                            exit_code=1,
                            output=(
                                "EF_EVIDENCE_ATTESTATION_BLOCKED\n"
                                "CAPTURED_EXIT_CODE=2"
                            ),
                            event_index=1,
                            event_id=f"historical-direct-{campaign_id}",
                            cwd="C:/historical/workspace",
                            status="completed",
                            command_actions=("node verify-release.mjs",),
                            source="agent",
                        ),
                        evidence_harness.base.CommandEvidence(
                            command="powershell wrapper",
                            exit_code=0,
                            output="CAPTURED_EXIT_CODE=2",
                            event_index=2,
                            event_id=f"historical-wrapper-{campaign_id}",
                            cwd="C:/historical/workspace",
                            status="completed",
                            command_actions=("powershell wrapper",),
                            source="agent",
                        ),
                    ],
                )
                fixture = ReceiptFixture(Path(tmp))
                fixture.output.mkdir()
                observed = evidence_harness.observe_verifier_receipt(
                    historical, fixture.expectation()
                )
                self.assertFalse(observed.valid)


if __name__ == "__main__":
    unittest.main()
