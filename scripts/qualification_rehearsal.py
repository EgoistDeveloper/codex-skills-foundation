#!/usr/bin/env python3
"""Exercise every exact-qualification infrastructure path without a model turn."""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable

import qualification_workspace
import release_candidate
import run_codex_bounded_delegation_smoke as delegation
import run_codex_evidence_refusal_smoke as evidence
import run_codex_live_smoke as positive
import run_codex_negative_smoke as negative
import run_codex_negative_smoke_v4 as isolation
from console_output import write_console_safe, write_transcript_bundle


class RehearsalError(RuntimeError):
    """A required zero-model infrastructure path did not complete."""


def _maximum_path(root: Path) -> int:
    values = [len(str(root.resolve(strict=True)))]
    values.extend(len(str(path.resolve(strict=False))) for path in root.rglob("*"))
    return max(values)


def _fixture_family(
    *,
    artifact_root: Path,
    campaign_id: str,
    family: str,
    create_fixture: Callable[[Path], None],
    clone_fixture: Callable[[Path, Path], None],
    repetition: int | None = None,
) -> dict[str, Any]:
    identity: dict[str, object] = {
        "campaign": campaign_id,
        "family": family,
        "attempt": 1,
    }
    if repetition is not None:
        identity["repetition"] = repetition
    mapping = artifact_root / "workspace-maps" / (
        f"{family}-{repetition or 0}-1.json"
    )
    mapping.parent.mkdir(parents=True, exist_ok=True)
    with qualification_workspace.allocate_workspace(
        artifact_root=artifact_root,
        mapping_path=mapping,
        identity=identity,
    ) as lease:
        seed = lease.child("s")
        baseline = lease.child("b")
        candidate = lease.child("c")
        create_fixture(seed)
        clone_fixture(seed, baseline)
        clone_fixture(seed, candidate)
        for repository in (seed, baseline, candidate):
            status = positive.git(["status", "--porcelain"], cwd=repository)
            if status:
                raise RehearsalError(f"{family} Git fixture is dirty: {repository.name}")
        maximum = _maximum_path(lease.path)
        if maximum > lease.budget["allowed"]:
            raise RehearsalError(f"{family} exceeded its workspace path budget")
        head = positive.git(["rev-parse", "HEAD"], cwd=seed)
        if any(positive.git(["rev-parse", "HEAD"], cwd=path) != head for path in (baseline, candidate)):
            raise RehearsalError(f"{family} clones differ from their seed")
        result = {
            "family": family,
            "repetition": repetition,
            "attempt": 1,
            "mapping": mapping.relative_to(artifact_root).as_posix(),
            "maximum_absolute_path_length": maximum,
            "path_budget_allowed": lease.budget["allowed"],
            "git_init_add_commit": "PASS",
            "git_clone": "PASS",
            "model_calls": 0,
        }
    payload = json.loads(mapping.read_text(encoding="utf-8"))
    if payload.get("cleanup_status") != "CLEANED":
        raise RehearsalError(f"{family} workspace did not publish CLEANED")
    result["cleanup"] = "PASS"
    return result


def _blocked_packet(expectation: evidence.ReceiptExpectation, receipt: dict[str, Any], head: str) -> dict[str, Any]:
    return {
        "task_id": evidence.TASK_ID,
        "completion_status": "BLOCKED",
        "workspace": {
            "repository": "zero-model-rehearsal",
            "branch": "main",
            "head_sha": head,
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
                        "command": evidence.VERIFY_COMMAND,
                        "fresh": True,
                        "exit_code": receipt["child"]["exit_code"],
                        "receipt": {
                            "run_id": expectation.run_id,
                            "command_id": expectation.command_id,
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


def _exercise_receipt(
    *,
    artifact_root: Path,
    campaign_id: str,
    marketplace_root: Path,
) -> dict[str, Any]:
    mapping = artifact_root / "workspace-maps/evidence-receipt.json"
    with qualification_workspace.allocate_workspace(
        artifact_root=artifact_root,
        mapping_path=mapping,
        identity={"campaign": campaign_id, "family": "receipt", "attempt": 1},
    ) as lease:
        workspace = lease.child("c")
        evidence.create_fixture(workspace)
        settings = workspace / "settings.json"
        settings.write_text(
            json.dumps({"channel": "stable", "mode": "strict"}, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        head = positive.git(["rev-parse", "HEAD"], cwd=workspace)
        plugin_root = marketplace_root / "plugins/engineering-foundation-core"
        skill_path = plugin_root / "skills/verify-before-completion/SKILL.md"
        expectation = evidence.create_receipt_expectation(
            campaign=lease.path,
            campaign_id=campaign_id,
            workspace=workspace,
            installed_plugin_root=plugin_root,
            skill_path=str(skill_path),
            node_executable=str(Path(positive.resolve_codex_launchers().node_executable).resolve(strict=True)),
        )
        result = subprocess.run(
            evidence.receipt_command_argv(expectation),
            cwd=workspace,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if result.returncode != 0:
            raise RehearsalError("structured verifier runner did not exit 0")
        command_event = positive.CommandEvidence(
            command=expectation.command,
            exit_code=result.returncode,
            output=result.stdout,
            event_index=1,
            event_id="rehearsal-command-event",
            cwd=str(workspace),
            status="completed",
            command_actions=(expectation.command,),
            source="agent",
            process_id=None,
        )
        turn = SimpleNamespace(
            variant="candidate",
            thread_id="rehearsal-thread",
            turn_id="rehearsal-turn",
            commands=[command_event],
            events=[],
        )
        observation = evidence.observe_verifier_receipt(turn, expectation)
        if not observation.valid or not isinstance(observation.receipt, dict):
            raise RehearsalError("structured verifier receipt observation failed")
        packet = _blocked_packet(expectation, observation.receipt, head)
        packet_text = json.dumps(packet, ensure_ascii=False, indent=2) + "\n"
        packet_path = workspace / "completion-evidence.json"
        packet_path.write_text(packet_text, encoding="utf-8", newline="\n")
        turn.events = [
            {"method": "item/completed", "params": {"item": {"type": "userMessage"}}},
            {"method": "item/completed", "params": {"item": {"type": "commandExecution", "id": command_event.event_id}}},
            {
                "method": "item/completed",
                "params": {
                    "item": {
                        "type": "fileChange",
                        "id": "rehearsal-packet-event",
                        "status": "completed",
                        "changes": [{"path": str(packet_path), "kind": {"type": "add"}, "diff": packet_text}],
                    }
                },
            },
            {"method": "item/completed", "params": {"item": {"type": "agentMessage", "id": "rehearsal-message"}}},
        ]
        snapshot = evidence.capture_packet_turn_snapshot(
            turn=turn,
            workspace=workspace,
            receipt_observation=observation,
        )
        inspection = evidence.validate_packet(
            workspace=workspace,
            expected_head=head,
            final_message="FINAL_STATUS: BLOCKED",
            receipt_expectation=expectation,
            receipt_observation=observation,
            packet_snapshot=snapshot,
        )
        if inspection.findings or not inspection.command_evidence_valid or not inspection.receipt_binding_valid:
            raise RehearsalError("receipt/event/packet correlation failed: " + "; ".join(inspection.findings))
        child = observation.receipt.get("child")
        if not isinstance(child, dict) or child.get("exit_code") != evidence.BLOCKED_VERIFY_EXIT_CODE:
            raise RehearsalError("receipt did not retain the exact blocked verifier exit")
        maximum = _maximum_path(lease.path)
    return {
        "runner_invocation": "PASS",
        "receipt_observation": "PASS",
        "event_packet_correlation": "PASS",
        "child_exit_code": evidence.BLOCKED_VERIFY_EXIT_CODE,
        "mapping": mapping.relative_to(artifact_root).as_posix(),
        "maximum_absolute_path_length": maximum,
        "cleanup": "PASS",
        "model_calls": 0,
    }


def _runtime_preflights(artifact_root: Path) -> dict[str, Any]:
    launchers = positive.resolve_codex_launchers()
    before = positive.read_plugin_state(launchers, positive.ROOT)
    trace_dir = artifact_root / "runtime-preflight"
    trace_dir.mkdir(parents=True, exist_ok=True)
    with qualification_workspace.allocate_probe_workspace(
        repository_root=positive.ROOT,
        family="runtime",
    ) as probe:
        with positive.AppServer(
            command=launchers.app_server_command,
            node_executable=launchers.node_executable,
            cwd=positive.ROOT,
            trace_path=probe.child("t"),
            timeout_seconds=120,
        ) as server:
            codex_home = server.initialize()
    direct = positive.configured_mcp_server_names(codex_home)
    inventory = isolation.discover_runtime_mcp_inventory(
        launchers=launchers,
        codex_home=codex_home,
        cwd=positive.ROOT,
    )
    names = isolation.merge_mcp_server_names(direct, inventory)
    builder = isolation.transport_safe_builder(negative.build_isolated_app_server_command)
    original_builder = positive.build_session_config
    positive.build_session_config = isolation.startup_only_session_config_builder(original_builder)
    try:
        results: dict[str, Any] = {}
        for family in ("positive", "negative"):
            campaign = trace_dir / family
            (campaign / "preflight").mkdir(parents=True)
            rows, overrides = isolation.verify_runtime_mcp_veto(
                launchers=launchers,
                codex_home=codex_home,
                cwd=positive.ROOT,
                disabled_names=names,
                builder=builder,
                campaign=campaign,
            )
            results[family] = {
                "status": "PASS",
                "inventory_count": len(rows),
                "override_count": len(overrides),
                "model_calls": 0,
            }
    finally:
        positive.build_session_config = original_builder
    after = positive.read_plugin_state(launchers, positive.ROOT)
    if before != after:
        raise RehearsalError("runtime preflight changed user plugin state")
    results["state_restoration"] = "PASS"
    return results


def run(
    *,
    artifact_root: Path,
    campaign_id: str,
    marketplace_root: Path,
    lifecycle_summary: dict[str, Any],
) -> dict[str, Any]:
    if lifecycle_summary.get("model_calls") != 0 or lifecycle_summary.get("outcome") != "PASS":
        raise RehearsalError("exact-artifact lifecycle evidence is not zero-model PASS")
    artifact_root.mkdir(parents=True, exist_ok=True)
    global_before = subprocess.run(
        ["git", "config", "--global", "--list", "--show-origin"],
        capture_output=True,
        check=False,
    )
    families: list[dict[str, Any]] = []
    for repetition in range(1, 4):
        families.append(
            _fixture_family(
                artifact_root=artifact_root,
                campaign_id=campaign_id,
                family="positive",
                create_fixture=positive.create_fixture,
                clone_fixture=positive.clone_fixture,
                repetition=repetition,
            )
        )
        families.append(
            _fixture_family(
                artifact_root=artifact_root,
                campaign_id=campaign_id,
                family="negative",
                create_fixture=negative.create_fixture,
                clone_fixture=negative.clone_fixture,
                repetition=repetition,
            )
        )
    families.append(
        _fixture_family(
            artifact_root=artifact_root,
            campaign_id=campaign_id,
            family="delegation",
            create_fixture=delegation.create_fixture,
            clone_fixture=delegation.clone_fixture,
        )
    )
    families.append(
        _fixture_family(
            artifact_root=artifact_root,
            campaign_id=campaign_id,
            family="evidence",
            create_fixture=evidence.create_fixture,
            clone_fixture=evidence.clone_fixture,
        )
    )
    receipt = _exercise_receipt(
        artifact_root=artifact_root,
        campaign_id=campaign_id,
        marketplace_root=marketplace_root,
    )
    runtime = _runtime_preflights(artifact_root)

    transcript = artifact_root / "transcripts/cp1254-rehearsal.txt"
    transcript_identity = write_transcript_bundle(
        transcript,
        "qualification rehearsal: Türkçe ✓\n",
        "Türkçe ✓\n".encode("utf-8"),
        b"",
    )
    buffer = io.BytesIO()
    console = io.TextIOWrapper(buffer, encoding="cp1254", errors="strict")
    write_console_safe(console, "qualification rehearsal: Türkçe ✓\n")
    console.flush()
    console_bytes = buffer.getvalue()
    if not console_bytes or b"\\u2713" not in console_bytes:
        raise RehearsalError("CP1254 console presentation did not escape safely")

    global_after = subprocess.run(
        ["git", "config", "--global", "--list", "--show-origin"],
        capture_output=True,
        check=False,
    )
    if (global_before.returncode, global_before.stdout, global_before.stderr) != (
        global_after.returncode,
        global_after.stdout,
        global_after.stderr,
    ):
        raise RehearsalError("zero-model rehearsal changed global Git configuration")
    expected_families = {"positive", "negative", "delegation", "evidence"}
    actual_families = {str(item["family"]) for item in families}
    if actual_families != expected_families or len(families) != 8:
        raise RehearsalError("one or more qualification fixture families were skipped")
    summary = {
        "schema_version": 1,
        "outcome": "PASS",
        "model_calls": 0,
        "lifecycle": "PASS",
        "fixture_families": families,
        "runtime_preflights": runtime,
        "structured_receipt": receipt,
        "transcript_publication": {
            "status": "PASS",
            "identity": transcript_identity,
            "cp1254_console": "PASS",
        },
        "global_git_config_unchanged": True,
        "state_restoration": "PASS",
        "workspace_residue": False,
        "candidate_state_residue": False,
    }
    release_candidate.write_json(artifact_root / "zero-model-rehearsal.json", summary)
    return summary
