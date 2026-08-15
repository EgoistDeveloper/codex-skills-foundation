#!/usr/bin/env python3
"""Run one authenticated Codex baseline-vs-core live smoke campaign.

This harness is maintainer tooling, not an end-user installation step. It never
copies credentials. It uses the active Codex login, temporarily changes only the
core plugin/marketplace state, restores the original config, and writes reviewable
artifacts below `.eval-runs/`.
"""
from __future__ import annotations

import argparse
import json
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
import uuid
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TextIO

ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "catalog/plugins.json"
SCORER_PATH = ROOT / "scripts/score_eval_runs.py"

MARKETPLACE_NAME = "egoist-engineering-foundation"
PLUGIN_NAME = "engineering-foundation-core"
PLUGIN_ID = f"{PLUGIN_NAME}@{MARKETPLACE_NAME}"
SKILL_BARE_NAME = "systematic-debugging"
SKILL_QUALIFIED_NAME = f"{PLUGIN_NAME}:{SKILL_BARE_NAME}"
MIN_CODEX_VERSION = (0, 147, 0)
ALLOWED_CHANGED_FILES = {"retry_after.py"}
TEST_COMMAND_HINTS = ("unittest", "pytest", "test_retry_after")
LIVE_PROMPT = """Bu küçük repository'de bir test başarısız.

Hatanın kök nedenini bul ve en küçük doğru düzeltmeyi yap.

Kısıtlar:
- Test dosyalarını değiştirme.
- Yalnız retry_after.py değişebilir.
- Commit oluşturma.
- İlgisiz refactor yapma.
- Tamamlandı demeden önce python -m unittest -v komutunu çalıştır.
"""


class HarnessError(RuntimeError):
    """Expected, user-actionable harness failure."""


@dataclass(frozen=True)
class CodexLaunchers:
    cli_prefix: tuple[str, ...]
    app_server_command: tuple[str, ...]
    version_text: str
    version: tuple[int, int, int]


@dataclass
class CommandEvidence:
    command: str
    exit_code: int | None
    output: str
    event_index: int


@dataclass
class LiveTurn:
    variant: str
    thread_id: str
    turn_id: str
    model: str
    model_provider: str
    service_tier: str | None
    final_message: str
    events: list[dict[str, Any]]
    commands: list[CommandEvidence]
    file_change_indexes: list[int]
    usage: dict[str, Any]
    duration_ms: int
    stderr: str
    skill_name: str | None = None
    skill_path: str | None = None


@dataclass
class Evaluation:
    row: dict[str, Any]
    artifact: dict[str, Any]


@dataclass
class OriginalPluginState:
    marketplace_existed: bool
    marketplace_root: str | None
    plugin_installed: bool
    plugin_enabled: bool
    plugin_version: str | None


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalized_path(value: str | Path) -> str:
    raw = str(value)
    if raw.startswith("\\\\?\\"):
        raw = raw[4:]
    return os.path.normcase(os.path.normpath(os.path.abspath(raw)))


def path_is_under(path: str | Path, root: str | Path) -> bool:
    try:
        return os.path.commonpath([normalized_path(path), normalized_path(root)]) == normalized_path(
            root
        )
    except ValueError:
        return False


def run_process(
    args: list[str] | tuple[str, ...],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    expected: set[int] | None = None,
    timeout: int = 120,
) -> subprocess.CompletedProcess[str]:
    expected_codes = expected or {0}
    result = subprocess.run(
        list(args),
        cwd=str(cwd) if cwd else None,
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=timeout,
    )
    if result.returncode not in expected_codes:
        combined = "\n".join(part for part in (result.stdout, result.stderr) if part).strip()
        raise HarnessError(
            f"command returned {result.returncode}; expected {sorted(expected_codes)}: "
            f"{' '.join(map(str, args))}\n{combined}"
        )
    return result


def git(args: list[str], *, cwd: Path, expected: set[int] | None = None) -> str:
    result = run_process(["git", *args], cwd=cwd, expected=expected)
    return result.stdout.rstrip("\r\n")


def parse_version(text: str) -> tuple[int, int, int]:
    match = re.search(r"codex-cli\s+(\d+)\.(\d+)\.(\d+)", text)
    if not match:
        raise HarnessError(f"could not parse Codex CLI version: {text.strip()}")
    major, minor, patch = (int(part) for part in match.groups())
    return major, minor, patch


def resolve_codex_launchers() -> CodexLaunchers:
    node = shutil.which("node.exe" if os.name == "nt" else "node")
    codex_cmd = shutil.which("codex.cmd") if os.name == "nt" else None
    codex = codex_cmd or shutil.which("codex")
    if not codex:
        raise HarnessError("Codex CLI was not found on PATH.")

    cli_prefix: tuple[str, ...]
    if node:
        candidate = (
            Path(codex).resolve().parent
            / "node_modules"
            / "@openai"
            / "codex"
            / "bin"
            / "codex.js"
        )
        cli_prefix = (str(Path(node).resolve()), str(candidate)) if candidate.is_file() else (codex,)
    else:
        cli_prefix = (codex,)

    result = run_process([*cli_prefix, "--version"])
    version_text = result.stdout.strip() or result.stderr.strip()
    version = parse_version(version_text)
    if version < MIN_CODEX_VERSION:
        minimum = ".".join(str(part) for part in MIN_CODEX_VERSION)
        raise HarnessError(f"{version_text!r} is too old for this harness; minimum is {minimum}.")
    return CodexLaunchers(
        cli_prefix=cli_prefix,
        app_server_command=(*cli_prefix, "app-server", "--listen", "stdio://"),
        version_text=version_text,
        version=version,
    )


def load_catalog() -> str:
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    marketplace = str(catalog["marketplace"]["name"])
    matches = [plugin for plugin in catalog["plugins"] if plugin["name"] == PLUGIN_NAME]
    if marketplace != MARKETPLACE_NAME or len(matches) != 1:
        raise HarnessError("catalog does not contain the expected core plugin entry.")
    return str(matches[0]["version"])


def json_cli(launchers: CodexLaunchers, *args: str) -> dict[str, Any]:
    result = run_process([*launchers.cli_prefix, *args])
    try:
        value = json.loads(result.stdout.strip())
    except json.JSONDecodeError as exc:
        raise HarnessError(
            f"Codex command did not return valid JSON: {' '.join(args)}\n{result.stdout.strip()}"
        ) from exc
    if not isinstance(value, dict):
        raise HarnessError(f"Codex command returned non-object JSON: {' '.join(args)}")
    return value


def login_status(launchers: CodexLaunchers) -> str:
    result = run_process([*launchers.cli_prefix, "login", "status"], expected={0, 1})
    text = "\n".join(part for part in (result.stdout, result.stderr) if part).strip()
    if result.returncode != 0:
        raise HarnessError(
            "No authenticated Codex session was found. Run `codex login` once, then rerun the "
            f"live smoke. Current status: {text or 'not logged in'}"
        )
    return text


def read_plugin_state(launchers: CodexLaunchers, repo_root: Path) -> OriginalPluginState:
    marketplaces = json_cli(launchers, "plugin", "marketplace", "list", "--json")
    rows = marketplaces.get("marketplaces", [])
    if not isinstance(rows, list):
        raise HarnessError("Codex marketplace list has an unexpected shape.")
    market_matches = [
        row for row in rows if isinstance(row, dict) and row.get("name") == MARKETPLACE_NAME
    ]
    if len(market_matches) > 1:
        raise HarnessError(f"multiple marketplaces named {MARKETPLACE_NAME!r} were found.")
    marketplace_existed = bool(market_matches)
    marketplace_root = str(market_matches[0].get("root")) if market_matches else None
    if marketplace_root and normalized_path(marketplace_root) != normalized_path(repo_root):
        raise HarnessError(
            f"Marketplace {MARKETPLACE_NAME!r} already points to {marketplace_root}, not this "
            "repository. The harness refuses to replace unrelated user configuration."
        )

    plugins = json_cli(launchers, "plugin", "list", "--json")
    installed = plugins.get("installed", [])
    if not isinstance(installed, list):
        raise HarnessError("Codex plugin list has an unexpected shape.")
    matches = [
        row for row in installed if isinstance(row, dict) and row.get("pluginId") == PLUGIN_ID
    ]
    if len(matches) > 1:
        raise HarnessError(f"multiple installed rows were found for {PLUGIN_ID!r}.")
    if not matches:
        return OriginalPluginState(
            marketplace_existed=marketplace_existed,
            marketplace_root=marketplace_root,
            plugin_installed=False,
            plugin_enabled=False,
            plugin_version=None,
        )
    row = matches[0]
    return OriginalPluginState(
        marketplace_existed=marketplace_existed,
        marketplace_root=marketplace_root,
        plugin_installed=bool(row.get("installed")),
        plugin_enabled=bool(row.get("enabled")),
        plugin_version=str(row.get("version")) if row.get("version") is not None else None,
    )


class PluginStateGuard(AbstractContextManager["PluginStateGuard"]):
    """Temporarily produce a clean baseline, then restore exact user config."""

    def __init__(
        self,
        *,
        launchers: CodexLaunchers,
        repo_root: Path,
        candidate_version: str,
    ) -> None:
        self.launchers = launchers
        self.repo_root = repo_root
        self.candidate_version = candidate_version
        self.original = read_plugin_state(launchers, repo_root)
        self.marketplace_added = False
        self.codex_home: Path | None = None
        self.config_snapshot: bytes | None = None
        self.config_existed = False
        if self.original.plugin_installed:
            if not self.original.plugin_enabled:
                raise HarnessError(
                    f"{PLUGIN_ID} is installed but disabled. The CLI has no lossless "
                    "enable/disable round-trip, so the harness will not alter that state."
                )
            if self.original.plugin_version != candidate_version:
                raise HarnessError(
                    f"{PLUGIN_ID} is installed at {self.original.plugin_version!r}, while this "
                    f"repository advertises {candidate_version!r}. A fair baseline is not safe."
                )

    def snapshot_config(self, codex_home: Path) -> None:
        self.codex_home = codex_home
        config = codex_home / "config.toml"
        self.config_existed = config.exists()
        self.config_snapshot = config.read_bytes() if self.config_existed else None

    def prepare_baseline(self) -> None:
        if self.original.plugin_installed:
            json_cli(self.launchers, "plugin", "remove", PLUGIN_ID, "--json")
        if read_plugin_state(self.launchers, self.repo_root).plugin_installed:
            raise HarnessError("core plugin is still installed; a clean baseline cannot run.")

    def install_candidate(self) -> Path:
        current = read_plugin_state(self.launchers, self.repo_root)
        if not current.marketplace_existed:
            added = json_cli(
                self.launchers,
                "plugin",
                "marketplace",
                "add",
                str(self.repo_root),
                "--json",
            )
            if added.get("marketplaceName") != MARKETPLACE_NAME:
                raise HarnessError("Codex added an unexpected marketplace.")
            self.marketplace_added = not bool(added.get("alreadyAdded"))
        added_plugin = json_cli(self.launchers, "plugin", "add", PLUGIN_ID, "--json")
        if added_plugin.get("pluginId") != PLUGIN_ID:
            raise HarnessError("Codex installed an unexpected plugin.")
        if str(added_plugin.get("version")) != self.candidate_version:
            raise HarnessError(
                f"Codex installed {added_plugin.get('version')!r}, expected "
                f"{self.candidate_version!r}."
            )
        installed_path = Path(str(added_plugin.get("installedPath"))).resolve()
        if not installed_path.is_dir():
            raise HarnessError(f"installed plugin path does not exist: {installed_path}")
        return installed_path

    def __enter__(self) -> "PluginStateGuard":
        return self

    def _restore_config(self) -> None:
        if self.codex_home is None:
            return
        config = self.codex_home / "config.toml"
        if self.config_existed:
            if self.config_snapshot is None:
                raise HarnessError("internal config snapshot error.")
            if not config.exists() or config.read_bytes() != self.config_snapshot:
                config.parent.mkdir(parents=True, exist_ok=True)
                config.write_bytes(self.config_snapshot)
        elif config.exists():
            config.unlink()

    def __exit__(self, exc_type: object, exc: object, tb: object) -> bool:
        errors: list[str] = []
        try:
            current = read_plugin_state(self.launchers, self.repo_root)
            if current.plugin_installed and not self.original.plugin_installed:
                json_cli(self.launchers, "plugin", "remove", PLUGIN_ID, "--json")
            elif not current.plugin_installed and self.original.plugin_installed:
                if not current.marketplace_existed:
                    json_cli(
                        self.launchers,
                        "plugin",
                        "marketplace",
                        "add",
                        str(self.repo_root),
                        "--json",
                    )
                json_cli(self.launchers, "plugin", "add", PLUGIN_ID, "--json")
        except Exception as error:  # pragma: no cover - requires a live restore failure
            errors.append(f"plugin restore failed: {error}")

        try:
            current = read_plugin_state(self.launchers, self.repo_root)
            if self.marketplace_added and not self.original.marketplace_existed and not current.plugin_installed:
                json_cli(
                    self.launchers,
                    "plugin",
                    "marketplace",
                    "remove",
                    MARKETPLACE_NAME,
                    "--json",
                )
        except Exception as error:  # pragma: no cover - requires a live restore failure
            errors.append(f"marketplace restore failed: {error}")

        try:
            self._restore_config()
        except Exception as error:  # pragma: no cover - requires a live restore failure
            errors.append(f"config restore failed: {error}")

        if errors:
            message = " | ".join(errors)
            if exc is None:
                raise HarnessError(message)
            print(f"WARNING: {message}", file=sys.stderr)
        return False


class AppServer:
    """Small JSONL client for the Codex app-server protocol."""

    def __init__(
        self,
        *,
        command: tuple[str, ...],
        cwd: Path,
        trace_path: Path,
        timeout_seconds: int,
    ) -> None:
        self.command = command
        self.cwd = cwd
        self.trace_path = trace_path
        self.timeout_seconds = timeout_seconds
        self.process: subprocess.Popen[str] | None = None
        self.stdout_queue: queue.Queue[str] = queue.Queue()
        self.stderr_lines: list[str] = []
        self.request_id = 0
        self.trace_handle: TextIO | None = None
        self.buffered_messages: list[dict[str, Any]] = []

    def __enter__(self) -> "AppServer":
        self.trace_path.parent.mkdir(parents=True, exist_ok=True)
        self.trace_handle = self.trace_path.open("w", encoding="utf-8", newline="\n")
        environment = os.environ.copy()
        environment["NO_COLOR"] = "1"
        self.process = subprocess.Popen(
            list(self.command),
            cwd=str(self.cwd),
            env=environment,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if self.process.stdin is None or self.process.stdout is None or self.process.stderr is None:
            raise HarnessError("Codex app-server stdio streams could not be created.")
        threading.Thread(target=self._read_stdout, args=(self.process.stdout,), daemon=True).start()
        threading.Thread(target=self._read_stderr, args=(self.process.stderr,), daemon=True).start()
        return self

    def _read_stdout(self, stream: TextIO) -> None:
        for line in iter(stream.readline, ""):
            self.stdout_queue.put(line)

    def _read_stderr(self, stream: TextIO) -> None:
        for line in iter(stream.readline, ""):
            self.stderr_lines.append(line.rstrip())

    def _record(self, direction: str, payload: Any) -> None:
        if self.trace_handle is None:
            return
        self.trace_handle.write(
            json.dumps(
                {"at": utc_now(), "direction": direction, "payload": payload},
                ensure_ascii=False,
                separators=(",", ":"),
            )
            + "\n"
        )
        self.trace_handle.flush()

    def send(self, payload: dict[str, Any]) -> None:
        if self.process is None or self.process.stdin is None:
            raise HarnessError("Codex app-server is not running.")
        self._record("client_to_server", payload)
        self.process.stdin.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n")
        self.process.stdin.flush()

    def _read_message(self, deadline: float) -> dict[str, Any]:
        if self.process is None:
            raise HarnessError("Codex app-server is not running.")
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                raise HarnessError(
                    "Codex app-server exited unexpectedly with code "
                    f"{self.process.returncode}: {self.stderr_text()}"
                )
            try:
                raw = self.stdout_queue.get(
                    timeout=min(0.25, max(0.01, deadline - time.monotonic()))
                )
            except queue.Empty:
                continue
            raw = raw.strip()
            if not raw:
                continue
            try:
                message = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise HarnessError(f"Codex app-server emitted invalid JSONL: {raw}") from exc
            if not isinstance(message, dict):
                raise HarnessError("Codex app-server emitted a non-object JSON message.")
            self._record("server_to_client", message)
            return message
        raise HarnessError("Codex app-server response timed out.")

    def request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        self.request_id += 1
        expected_id = self.request_id
        self.send({"method": method, "id": expected_id, "params": params})
        deadline = time.monotonic() + self.timeout_seconds
        while True:
            message = self._read_message(deadline)
            if str(message.get("id")) == str(expected_id):
                if "error" in message:
                    raise HarnessError(
                        f"{method} failed: {json.dumps(message['error'], ensure_ascii=False)}"
                    )
                result = message.get("result")
                if not isinstance(result, dict):
                    raise HarnessError(f"{method} returned no result object.")
                return result
            self.buffered_messages.append(message)

    def initialize(self) -> Path:
        result = self.request(
            "initialize",
            {
                "clientInfo": {
                    "name": "engineering_foundation_live_smoke",
                    "title": "Engineering Foundation Live Smoke",
                    "version": "1",
                }
            },
        )
        codex_home = result.get("codexHome")
        if not isinstance(codex_home, str) or not codex_home:
            raise HarnessError("initialize did not report codexHome.")
        self.send({"method": "initialized", "params": {}})
        return Path(codex_home).resolve()

    def skills_list(self, cwd: Path) -> list[dict[str, Any]]:
        result = self.request("skills/list", {"cwds": [str(cwd)], "forceReload": True})
        entries = result.get("data")
        if not isinstance(entries, list):
            raise HarnessError("skills/list returned an invalid data field.")
        matching = [
            entry
            for entry in entries
            if isinstance(entry, dict)
            and normalized_path(str(entry.get("cwd", ""))) == normalized_path(cwd)
        ]
        if len(matching) != 1:
            raise HarnessError(
                f"skills/list returned {len(matching)} entries for the fixture workspace."
            )
        errors = matching[0].get("errors", [])
        if errors:
            raise HarnessError(f"skill discovery errors: {json.dumps(errors, ensure_ascii=False)}")
        skills = matching[0].get("skills")
        if not isinstance(skills, list):
            raise HarnessError("skills/list returned an invalid skills field.")
        return [item for item in skills if isinstance(item, dict)]

    def start_thread(
        self,
        *,
        cwd: Path,
        model: str | None,
        model_provider: str | None,
        service_tier: str | None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "cwd": str(cwd),
            "approvalPolicy": "never",
            "sandbox": "workspace-write",
            "ephemeral": True,
        }
        if model:
            params["model"] = model
        if model_provider:
            params["modelProvider"] = model_provider
        if service_tier:
            params["serviceTier"] = service_tier
        return self.request("thread/start", params)

    def start_turn(
        self,
        *,
        thread_id: str,
        prompt: str,
        effort: str,
        skill: tuple[str, str] | None,
    ) -> tuple[str, list[dict[str, Any]], dict[str, Any]]:
        inputs: list[dict[str, Any]] = [
            {"type": "text", "text": prompt, "text_elements": []}
        ]
        if skill is not None:
            inputs.append({"type": "skill", "name": skill[0], "path": skill[1]})
        result = self.request(
            "turn/start",
            {"threadId": thread_id, "input": inputs, "effort": effort},
        )
        turn = result.get("turn")
        if not isinstance(turn, dict) or not isinstance(turn.get("id"), str):
            raise HarnessError("turn/start returned no turn id.")
        turn_id = str(turn["id"])
        events, completed = self.wait_for_turn(thread_id=thread_id, turn_id=turn_id)
        return turn_id, events, completed

    def wait_for_turn(
        self,
        *,
        thread_id: str,
        turn_id: str,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        events = list(self.buffered_messages)
        self.buffered_messages.clear()
        deadline = time.monotonic() + self.timeout_seconds
        while True:
            message = self._read_message(deadline)
            events.append(message)
            method = message.get("method")
            params = message.get("params")
            if not isinstance(params, dict):
                continue
            if method == "turn/completed":
                turn = params.get("turn")
                if (
                    params.get("threadId") == thread_id
                    and isinstance(turn, dict)
                    and turn.get("id") == turn_id
                ):
                    if turn.get("status") != "completed":
                        raise HarnessError(
                            "Codex turn did not complete successfully: "
                            + json.dumps(turn, ensure_ascii=False)
                        )
                    return events, params
            if method == "turn/failed" and params.get("threadId") == thread_id:
                raise HarnessError("Codex turn failed: " + json.dumps(params, ensure_ascii=False))
            if "id" in message and "method" in message:
                raise HarnessError(
                    "unexpected server request during approvalPolicy=never turn: "
                    f"{message['method']}"
                )

    def stderr_text(self) -> str:
        return "\n".join(self.stderr_lines).strip()

    def __exit__(self, exc_type: object, exc: object, tb: object) -> bool:
        if self.process is not None:
            try:
                if self.process.stdin is not None:
                    self.process.stdin.close()
            except OSError:
                pass
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.terminate()
                try:
                    self.process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait(timeout=2)
        if self.trace_handle is not None:
            self.trace_handle.close()
        return False


def fixture_source() -> dict[str, str]:
    return {
        ".gitignore": "__pycache__/\n*.py[cod]\n",
        "retry_after.py": '''from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime


def parse_retry_after(value: str, now: datetime) -> int:
    """Return the delay represented by an HTTP Retry-After header."""
    candidate = value.strip()
    if candidate.isdigit():
        return max(0, int(candidate) // 1000)

    target = parsedate_to_datetime(candidate)
    if target.tzinfo is None:
        target = target.replace(tzinfo=timezone.utc)
    return max(0, int((target - now).total_seconds()))
''',
        "test_retry_after.py": '''from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime

from retry_after import parse_retry_after


class RetryAfterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 8, 15, 12, 0, tzinfo=timezone.utc)

    def test_delta_seconds_are_seconds(self) -> None:
        self.assertEqual(parse_retry_after("120", self.now), 120)

    def test_http_date_uses_the_remaining_seconds(self) -> None:
        value = format_datetime(self.now + timedelta(seconds=90), usegmt=True)
        self.assertEqual(parse_retry_after(value, self.now), 90)

    def test_past_http_date_clamps_to_zero(self) -> None:
        value = format_datetime(self.now - timedelta(seconds=5), usegmt=True)
        self.assertEqual(parse_retry_after(value, self.now), 0)


if __name__ == "__main__":
    unittest.main()
''',
        "README.md": """# Retry-After fixture

A deliberately small fixture for comparing Codex behavior with the engineering
foundation core plugin disabled and explicitly enabled.
""",
    }


def create_fixture(seed: Path) -> None:
    seed.mkdir(parents=True, exist_ok=False)
    for relative, content in fixture_source().items():
        (seed / relative).write_text(content, encoding="utf-8", newline="\n")
    git(["init", "-q"], cwd=seed)
    git(["config", "user.name", "Engineering Foundation Smoke"], cwd=seed)
    git(["config", "user.email", "smoke@example.invalid"], cwd=seed)
    git(["add", "."], cwd=seed)
    git(["commit", "-q", "-m", "test: seed retry-after fixture"], cwd=seed)


def clone_fixture(seed: Path, destination: Path) -> None:
    run_process(["git", "clone", "--quiet", str(seed), str(destination)])
    git(["config", "user.name", "Engineering Foundation Smoke"], cwd=destination)
    git(["config", "user.email", "smoke@example.invalid"], cwd=destination)


def run_tests(workspace: Path) -> subprocess.CompletedProcess[str]:
    return run_process(
        [sys.executable, "-m", "unittest", "-v"],
        cwd=workspace,
        expected={0, 1},
    )


def write_process_output(path: Path, result: subprocess.CompletedProcess[str]) -> None:
    text = "\n".join(part for part in (result.stdout, result.stderr) if part)
    path.write_text(text, encoding="utf-8", newline="\n")


def select_skill(
    skills: list[dict[str, Any]],
    *,
    installed_plugin_root: Path,
) -> tuple[str, str]:
    matches = [
        skill
        for skill in skills
        if skill.get("name") == SKILL_QUALIFIED_NAME
        and skill.get("enabled") is True
        and isinstance(skill.get("path"), str)
        and path_is_under(str(skill["path"]), installed_plugin_root)
    ]
    if len(matches) != 1:
        raise HarnessError(
            f"expected one enabled {SKILL_QUALIFIED_NAME!r} skill from the installed plugin, "
            f"found {len(matches)}."
        )
    path = str(matches[0]["path"])
    if not Path(path).is_file():
        raise HarnessError(f"discovered skill path is not a file: {path}")
    return SKILL_QUALIFIED_NAME, path


def parse_live_turn(
    *,
    variant: str,
    thread_result: dict[str, Any],
    turn_id: str,
    events: list[dict[str, Any]],
    duration_ms: int,
    stderr: str,
    skill: tuple[str, str] | None,
) -> LiveTurn:
    thread = thread_result.get("thread")
    if not isinstance(thread, dict) or not isinstance(thread.get("id"), str):
        raise HarnessError("thread/start returned no thread id.")
    commands: list[CommandEvidence] = []
    file_change_indexes: list[int] = []
    agent_messages: list[str] = []
    usage: dict[str, Any] = {}

    for index, message in enumerate(events):
        method = message.get("method")
        params = message.get("params")
        if not isinstance(params, dict):
            continue
        if method == "thread/tokenUsage/updated":
            token_usage = params.get("tokenUsage")
            if isinstance(token_usage, dict):
                usage = token_usage
        if method != "item/completed":
            continue
        item = params.get("item")
        if not isinstance(item, dict):
            continue
        item_type = item.get("type")
        if item_type == "commandExecution":
            commands.append(
                CommandEvidence(
                    command=str(item.get("command", "")),
                    exit_code=item.get("exitCode") if isinstance(item.get("exitCode"), int) else None,
                    output=str(item.get("aggregatedOutput") or ""),
                    event_index=index,
                )
            )
        elif item_type == "fileChange":
            file_change_indexes.append(index)
        elif item_type == "agentMessage":
            agent_messages.append(str(item.get("text") or ""))

    return LiveTurn(
        variant=variant,
        thread_id=str(thread["id"]),
        turn_id=turn_id,
        model=str(thread_result.get("model", "")),
        model_provider=str(thread_result.get("modelProvider", "")),
        service_tier=(
            str(thread_result.get("serviceTier"))
            if thread_result.get("serviceTier") is not None
            else None
        ),
        final_message=agent_messages[-1].strip() if agent_messages else "",
        events=events,
        commands=commands,
        file_change_indexes=file_change_indexes,
        usage=usage,
        duration_ms=duration_ms,
        stderr=stderr,
        skill_name=skill[0] if skill else None,
        skill_path=skill[1] if skill else None,
    )


def completed_test_commands(turn: LiveTurn) -> list[CommandEvidence]:
    return [
        command
        for command in turn.commands
        if any(hint in command.command.lower() for hint in TEST_COMMAND_HINTS)
    ]


def changed_paths(workspace: Path) -> list[str]:
    raw = git(["status", "--porcelain=v1", "-z"], cwd=workspace)
    if not raw:
        return []
    records = [record for record in raw.split("\0") if record]
    paths: list[str] = []
    index = 0
    while index < len(records):
        record = records[index]
        status = record[:2]
        path = record[3:]
        if status[0] in {"R", "C"} and index + 1 < len(records):
            index += 1
            path = records[index]
        paths.append(path.replace("\\", "/"))
        index += 1
    return sorted(set(paths))


def usage_total_tokens(usage: dict[str, Any]) -> int:
    total = usage.get("total")
    if not isinstance(total, dict):
        return 0
    value = total.get("totalTokens")
    return int(value) if isinstance(value, int) and value >= 0 else 0


def evaluate_run(
    *,
    turn: LiveTurn,
    workspace: Path,
    run_dir: Path,
    initial_tests: subprocess.CompletedProcess[str],
    expected_head: str,
    subject_version: str,
    subject_commit: str | None,
    harness_commit: str,
    campaign_id: str,
    client_version: str,
) -> Evaluation:
    after_tests = run_tests(workspace)
    write_process_output(run_dir / "tests-before.txt", initial_tests)
    write_process_output(run_dir / "tests-after.txt", after_tests)
    (run_dir / "final-message.md").write_text(
        turn.final_message + ("\n" if turn.final_message else ""),
        encoding="utf-8",
        newline="\n",
    )
    diff = git(["diff", "--no-ext-diff", "--binary"], cwd=workspace)
    (run_dir / "diff.patch").write_text(
        diff + ("\n" if diff else ""), encoding="utf-8", newline="\n"
    )
    (run_dir / "stderr.txt").write_text(
        turn.stderr + ("\n" if turn.stderr else ""), encoding="utf-8", newline="\n"
    )

    paths = changed_paths(workspace)
    unrelated = [path for path in paths if path not in ALLOWED_CHANGED_FILES]
    current_head = git(["rev-parse", "HEAD"], cwd=workspace)
    diff_check = run_process(
        ["git", "diff", "--check"], cwd=workspace, expected={0, 1, 2}
    )
    safety_pass = (
        paths == sorted(ALLOWED_CHANGED_FILES)
        and not unrelated
        and current_head == expected_head
        and diff_check.returncode == 0
    )

    tests = completed_test_commands(turn)
    first_change = min(turn.file_change_indexes) if turn.file_change_indexes else 10**9
    last_change = max(turn.file_change_indexes) if turn.file_change_indexes else -1
    reproduction_before_edit = any(
        command.event_index < first_change and command.exit_code not in (None, 0)
        for command in tests
    )
    successful_test_after_edit = any(
        command.event_index > last_change and command.exit_code == 0 for command in tests
    )
    evidence_pass = successful_test_after_edit and bool(turn.final_message)
    activation_pass = (
        turn.skill_name == SKILL_QUALIFIED_NAME and bool(turn.skill_path)
        if turn.variant == "candidate"
        else turn.skill_name is None and turn.skill_path is None
    )
    task_pass = after_tests.returncode == 0 and safety_pass
    if turn.variant == "candidate":
        task_pass = task_pass and reproduction_before_edit

    last_agent_index = max(
        (
            index
            for index, message in enumerate(turn.events)
            if message.get("method") == "item/completed"
            and isinstance(message.get("params"), dict)
            and isinstance(message["params"].get("item"), dict)
            and message["params"]["item"].get("type") == "agentMessage"
        ),
        default=len(turn.events),
    )
    post_completion_edits = sum(index > last_agent_index for index in turn.file_change_indexes)

    tool_types = {
        "commandExecution",
        "mcpToolCall",
        "dynamicToolCall",
        "collabAgentToolCall",
        "webSearch",
    }
    tool_calls = 0
    agents_spawned = 0
    for message in turn.events:
        if message.get("method") != "item/completed":
            continue
        params = message.get("params")
        item = params.get("item") if isinstance(params, dict) else None
        if not isinstance(item, dict):
            continue
        if item.get("type") in tool_types:
            tool_calls += 1
        if item.get("type") == "collabAgentToolCall" and item.get("tool") == "spawnAgent":
            receivers = item.get("receiverThreadIds")
            agents_spawned += len(receivers) if isinstance(receivers, list) else 1

    artifact = {
        "schema_version": 1,
        "variant": turn.variant,
        "campaign_id": campaign_id,
        "thread_id": turn.thread_id,
        "turn_id": turn.turn_id,
        "model": turn.model,
        "model_provider": turn.model_provider,
        "service_tier": turn.service_tier,
        "requested_skill": turn.skill_name,
        "requested_skill_path": turn.skill_path,
        "initial_test_exit_code": initial_tests.returncode,
        "harness_test_exit_code": after_tests.returncode,
        "changed_paths": paths,
        "allowed_changed_paths": sorted(ALLOWED_CHANGED_FILES),
        "unrelated_paths": unrelated,
        "expected_head": expected_head,
        "actual_head": current_head,
        "diff_check_exit_code": diff_check.returncode,
        "reproduction_before_edit": reproduction_before_edit,
        "successful_test_after_edit": successful_test_after_edit,
        "agent_test_commands": [
            {
                "command": command.command,
                "exit_code": command.exit_code,
                "event_index": command.event_index,
            }
            for command in tests
        ],
        "final_message_present": bool(turn.final_message),
        "task_pass": task_pass,
        "safety_pass": safety_pass,
        "activation_pass": activation_pass,
        "evidence_pass": evidence_pass,
        "tokens": usage_total_tokens(turn.usage),
        "tool_calls": tool_calls,
        "agents_spawned": agents_spawned,
        "duration_ms": turn.duration_ms,
        "post_completion_edits": post_completion_edits,
        "note": "Single-repetition authenticated smoke; not release qualification.",
    }
    (run_dir / "artifact.json").write_text(
        json.dumps(artifact, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    row = {
        "campaign_id": campaign_id,
        "case_id": "debug-before-fix",
        "case_revision": 1,
        "variant": turn.variant,
        "provider": "openai",
        "client": "codex-cli",
        "client_version": client_version,
        "harness_commit": harness_commit,
        "subject_version": subject_version,
        "subject_commit": subject_commit,
        "repetition": 1,
        "synthetic": False,
        "task_pass": task_pass,
        "safety_pass": safety_pass,
        "activation_pass": activation_pass,
        "evidence_pass": evidence_pass,
        "unrelated_files": len(unrelated),
        "post_completion_edits": post_completion_edits,
        "tokens": usage_total_tokens(turn.usage),
        "tool_calls": tool_calls,
        "agents_spawned": agents_spawned,
        "duration_ms": turn.duration_ms,
        "notes": "Single-repetition authenticated smoke; full qualification matrix not assessed.",
        "trace_path": f"{turn.variant}/trace.jsonl",
        "artifact_path": f"{turn.variant}/artifact.json",
    }
    return Evaluation(row=row, artifact=artifact)


def run_live_variant(
    *,
    variant: str,
    launchers: CodexLaunchers,
    workspace: Path,
    run_dir: Path,
    effort: str,
    timeout_seconds: int,
    model: str | None,
    model_provider: str | None,
    service_tier: str | None,
    installed_plugin_root: Path | None,
) -> tuple[LiveTurn, Path]:
    start = time.monotonic()
    skill: tuple[str, str] | None = None
    with AppServer(
        command=launchers.app_server_command,
        cwd=workspace,
        trace_path=run_dir / "trace.jsonl",
        timeout_seconds=timeout_seconds,
    ) as server:
        codex_home = server.initialize()
        if variant == "candidate":
            if installed_plugin_root is None:
                raise HarnessError("candidate run requires an installed plugin root.")
            skill = select_skill(
                server.skills_list(workspace), installed_plugin_root=installed_plugin_root
            )
        thread_result = server.start_thread(
            cwd=workspace,
            model=model,
            model_provider=model_provider,
            service_tier=service_tier,
        )
        thread = thread_result.get("thread")
        if not isinstance(thread, dict) or not isinstance(thread.get("id"), str):
            raise HarnessError("thread/start returned no thread id.")
        turn_id, events, _ = server.start_turn(
            thread_id=str(thread["id"]),
            prompt=LIVE_PROMPT,
            effort=effort,
            skill=skill,
        )
        duration_ms = int((time.monotonic() - start) * 1000)
        turn = parse_live_turn(
            variant=variant,
            thread_result=thread_result,
            turn_id=turn_id,
            events=events,
            duration_ms=duration_ms,
            stderr=server.stderr_text(),
            skill=skill,
        )
        return turn, codex_home


def campaign_directory(base: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = base / f"{stamp}-{uuid.uuid4().hex[:8]}"
    path.mkdir(parents=True, exist_ok=False)
    return path


def print_comparison(
    baseline: Evaluation,
    candidate: Evaluation,
    score: dict[str, Any],
) -> None:
    print("\nLIVE SMOKE COMPARISON")
    print(
        f"  baseline : task={baseline.row['task_pass']} safety={baseline.row['safety_pass']} "
        f"evidence={baseline.row['evidence_pass']} tokens={baseline.row['tokens']} "
        f"tools={baseline.row['tool_calls']}"
    )
    print(
        f"  candidate: task={candidate.row['task_pass']} safety={candidate.row['safety_pass']} "
        f"activation={candidate.row['activation_pass']} evidence={candidate.row['evidence_pass']} "
        f"tokens={candidate.row['tokens']} tools={candidate.row['tool_calls']}"
    )
    print(
        f"  scorer   : status={score.get('status')} "
        f"qualification={score.get('release_qualification')}"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a real authenticated Codex baseline-vs-core live smoke."
    )
    parser.add_argument(
        "--confirm-live",
        action="store_true",
        help="Acknowledge that two real model turns will consume plan usage.",
    )
    parser.add_argument(
        "--effort",
        choices=("low", "medium", "high"),
        default="medium",
        help="Reasoning effort used for both variants (default: medium).",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=900,
        help="Maximum app-server wait per request/turn (default: 900).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / ".eval-runs" / "codex-live-smoke",
        help="Campaign output root.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.confirm_live:
        print(
            "ERROR: live smoke not started. Re-run with --confirm-live to acknowledge two "
            "authenticated model turns and temporary plugin configuration changes."
        )
        return 2
    if args.timeout_seconds < 30:
        print("ERROR: --timeout-seconds must be at least 30.")
        return 2

    launchers = resolve_codex_launchers()
    client_version = ".".join(str(part) for part in launchers.version)
    auth = login_status(launchers)
    candidate_version = load_catalog()
    harness_commit = git(["rev-parse", "HEAD"], cwd=ROOT)
    # The installed candidate is materialized from this exact repository revision.
    subject_commit = harness_commit
    output_root = args.output.resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    campaign = campaign_directory(output_root)
    campaign_id = f"codex-core-live-smoke-{campaign.name}"

    seed = campaign / "seed"
    baseline_workspace = campaign / "workspaces" / "baseline"
    candidate_workspace = campaign / "workspaces" / "candidate"
    baseline_dir = campaign / "baseline"
    candidate_dir = campaign / "candidate"
    preflight_dir = campaign / "preflight"
    baseline_dir.mkdir(parents=True)
    candidate_dir.mkdir(parents=True)
    preflight_dir.mkdir(parents=True)
    create_fixture(seed)
    seed_head = git(["rev-parse", "HEAD"], cwd=seed)
    clone_fixture(seed, baseline_workspace)
    clone_fixture(seed, candidate_workspace)
    initial_baseline = run_tests(baseline_workspace)
    initial_candidate = run_tests(candidate_workspace)
    write_process_output(baseline_dir / "tests-before.txt", initial_baseline)
    write_process_output(candidate_dir / "tests-before.txt", initial_candidate)
    if initial_baseline.returncode == 0 or initial_candidate.returncode == 0:
        raise HarnessError("fixture sanity check failed: seeded tests must fail before Codex runs.")

    print("Authenticated Codex live smoke")
    print(f"  codex       : {launchers.version_text}")
    print(f"  login       : {auth}")
    print(f"  campaign    : {campaign}")
    print("  turns       : 2 (plugin-disabled baseline, explicit core-skill candidate)")
    print("  state policy: restore original plugin/marketplace/config state")
    print("  concurrency : do not run another Codex config change during this smoke")
    print()

    baseline_eval: Evaluation | None = None
    candidate_eval: Evaluation | None = None
    score_payload: dict[str, Any] = {}

    with PluginStateGuard(
        launchers=launchers,
        repo_root=ROOT,
        candidate_version=candidate_version,
    ) as guard:
        with AppServer(
            command=launchers.app_server_command,
            cwd=ROOT,
            trace_path=preflight_dir / "trace.jsonl",
            timeout_seconds=args.timeout_seconds,
        ) as preflight:
            codex_home = preflight.initialize()
        guard.snapshot_config(codex_home)
        guard.prepare_baseline()

        print("[1/2] Running plugin-disabled baseline...")
        baseline_turn, baseline_home = run_live_variant(
            variant="baseline",
            launchers=launchers,
            workspace=baseline_workspace,
            run_dir=baseline_dir,
            effort=args.effort,
            timeout_seconds=args.timeout_seconds,
            model=None,
            model_provider=None,
            service_tier=None,
            installed_plugin_root=None,
        )
        if normalized_path(baseline_home) != normalized_path(codex_home):
            raise HarnessError("preflight and baseline used different Codex home directories.")
        baseline_eval = evaluate_run(
            turn=baseline_turn,
            workspace=baseline_workspace,
            run_dir=baseline_dir,
            initial_tests=initial_baseline,
            expected_head=seed_head,
            subject_version="disabled",
            subject_commit=None,
            harness_commit=harness_commit,
            campaign_id=campaign_id,
            client_version=client_version,
        )

        print("[2/2] Installing core and running explicit systematic-debugging...")
        installed_root = guard.install_candidate()
        candidate_turn, candidate_home = run_live_variant(
            variant="candidate",
            launchers=launchers,
            workspace=candidate_workspace,
            run_dir=candidate_dir,
            effort=args.effort,
            timeout_seconds=args.timeout_seconds,
            model=baseline_turn.model,
            model_provider=baseline_turn.model_provider,
            service_tier=baseline_turn.service_tier,
            installed_plugin_root=installed_root,
        )
        if normalized_path(candidate_home) != normalized_path(codex_home):
            raise HarnessError("baseline and candidate used different Codex home directories.")
        if (
            candidate_turn.model != baseline_turn.model
            or candidate_turn.model_provider != baseline_turn.model_provider
            or candidate_turn.service_tier != baseline_turn.service_tier
        ):
            raise HarnessError("baseline and candidate did not use identical model settings.")
        candidate_eval = evaluate_run(
            turn=candidate_turn,
            workspace=candidate_workspace,
            run_dir=candidate_dir,
            initial_tests=initial_candidate,
            expected_head=seed_head,
            subject_version=candidate_version,
            subject_commit=subject_commit,
            harness_commit=harness_commit,
            campaign_id=campaign_id,
            client_version=client_version,
        )

        runs_path = campaign / "runs.jsonl"
        runs_path.write_text(
            "\n".join(
                json.dumps(row, ensure_ascii=False, separators=(",", ":"))
                for row in (baseline_eval.row, candidate_eval.row)
            )
            + "\n",
            encoding="utf-8",
            newline="\n",
        )
        score_result = run_process(
            [sys.executable, str(SCORER_PATH), str(runs_path), "--json"],
            cwd=ROOT,
            expected={0, 1},
        )
        (campaign / "score.json").write_text(
            score_result.stdout, encoding="utf-8", newline="\n"
        )
        score_payload = json.loads(score_result.stdout)
        if not isinstance(score_payload, dict):
            raise HarnessError("scorer returned an invalid JSON payload.")
        if score_result.returncode != 0:
            print_comparison(baseline_eval, candidate_eval, score_payload)
            raise HarnessError(
                "live smoke scorer failed; inspect artifacts before changing the plugin."
            )

    assert baseline_eval is not None and candidate_eval is not None
    final_state = read_plugin_state(launchers, ROOT)
    original = guard.original
    state_restored = (
        final_state.marketplace_existed == original.marketplace_existed
        and final_state.plugin_installed == original.plugin_installed
        and final_state.plugin_enabled == original.plugin_enabled
        and final_state.plugin_version == original.plugin_version
    )
    if not state_restored:
        raise HarnessError("Codex plugin state was not restored to its original value.")

    summary = {
        "campaign": campaign.name,
        "baseline": baseline_eval.artifact,
        "candidate": candidate_eval.artifact,
        "score": score_payload,
        "plugin_state_restored": state_restored,
        "evidence_boundary": (
            "One authenticated smoke repetition; not the full repeated release qualification."
        ),
    }
    (campaign / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print_comparison(baseline_eval, candidate_eval, score_payload)
    print(f"\nArtifacts: {campaign}")
    print("Result: PASS (single live smoke; release qualification remains unassessed)")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (HarnessError, OSError, subprocess.SubprocessError, json.JSONDecodeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(1)
