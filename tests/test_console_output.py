from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = ROOT / "scripts"
QUALIFICATION_PATH = SCRIPT_DIR / "run_exact_artifact_qualification.py"
CONSOLE_OUTPUT_PATH = SCRIPT_DIR / "console_output.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


console_output = load_module("console_output_for_tests", CONSOLE_OUTPUT_PATH)


def load_qualification_module():
    return load_module(
        "run_exact_artifact_qualification_for_console_tests",
        QUALIFICATION_PATH,
    )


@contextmanager
def installed_stream(
    attribute: str,
    encoding: str,
) -> Iterator[tuple[io.TextIOWrapper, io.BytesIO]]:
    original = getattr(sys, attribute)
    buffer = io.BytesIO()
    stream = io.TextIOWrapper(
        buffer,
        encoding=encoding,
        errors="strict",
        newline="",
        write_through=True,
    )
    try:
        setattr(sys, attribute, stream)
        yield stream, buffer
    finally:
        setattr(sys, attribute, original)
        stream.flush()
        stream.detach()


class RecordingStream:
    def __init__(self, encoding: object = None) -> None:
        self.encoding = encoding
        self.values: list[str] = []

    def write(self, value: str) -> int:
        self.values.append(value)
        return len(value)


class RaisingStream:
    encoding = "utf-8"

    def __init__(self, error: BaseException) -> None:
        self.error = error

    def write(self, value: str) -> int:
        raise self.error


class MisreportedEncodingStream:
    encoding = "utf-8"

    def __init__(self) -> None:
        self.values: list[str] = []
        self.calls = 0

    def write(self, value: str) -> int:
        self.calls += 1
        if self.calls == 1:
            raise UnicodeEncodeError("cp1254", value, 0, 1, "unencodable")
        self.values.append(value)
        return len(value)


class ConsoleOutputTests(unittest.TestCase):
    def setUp(self) -> None:
        self.qualification = load_qualification_module()
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def transcript(self, name: str = "transcript.txt") -> Path:
        return self.root / name

    @staticmethod
    def child_bytes(stdout: bytes, stderr: bytes = b"") -> list[str]:
        source = (
            "import sys\n"
            f"sys.stdout.buffer.write({stdout!r})\n"
            f"sys.stderr.buffer.write({stderr!r})\n"
        )
        return [sys.executable, "-c", source]

    @staticmethod
    def rendered_bytes(text: str, encoding: str) -> bytes:
        buffer = io.BytesIO()
        stream = io.TextIOWrapper(
            buffer,
            encoding=encoding,
            errors="strict",
            newline="",
            write_through=True,
        )
        console_output.write_console_safe(stream, text)
        return buffer.getvalue()

    def test_cp1254_escapes_ufffd_without_question_mark_or_deletion(self) -> None:
        rendered = self.rendered_bytes("before\ufffdafter", "cp1254").decode(
            "cp1254"
        )
        self.assertEqual(rendered, r"before\ufffdafter")
        self.assertNotIn("?", rendered)
        self.assertIn("before", rendered)
        self.assertIn("after", rendered)

    def test_ascii_escapes_ufffd(self) -> None:
        rendered = self.rendered_bytes("\ufffd", "ascii").decode("ascii")
        self.assertEqual(rendered, r"\ufffd")

    def test_utf8_preserves_ufffd(self) -> None:
        rendered = self.rendered_bytes("\ufffd", "utf-8")
        self.assertEqual(rendered, "\ufffd".encode("utf-8"))

    def test_turkish_cp1254_characters_remain_readable(self) -> None:
        text = "Türkçe: ğüşiöçİŞĞ"
        rendered = self.rendered_bytes(text, "cp1254").decode("cp1254")
        self.assertEqual(rendered, text)

    def test_astral_character_uses_deterministic_uppercase_escape(self) -> None:
        rendered = self.rendered_bytes("🙂", "cp1254").decode("ascii")
        self.assertEqual(rendered, r"\U0001f642")

    def test_newlines_empty_text_and_multiline_are_preserved(self) -> None:
        for text in ("", "one\n", "one\r\ntwo\n\ufffd\n"):
            with self.subTest(text=ascii(text)):
                rendered = self.rendered_bytes(text, "cp1254").decode("cp1254")
                expected = console_output.render_for_console(text, "cp1254")
                self.assertEqual(rendered, expected)
                self.assertEqual(rendered.count("\n"), text.count("\n"))

    def test_stdout_and_stderr_presentation_are_independently_safe(self) -> None:
        with installed_stream("stdout", "cp1254") as (_, stdout_buffer):
            with installed_stream("stderr", "ascii") as (_, stderr_buffer):
                console_output.write_console_safe(sys.stdout, "out\ufffd\n")
                console_output.write_console_safe(sys.stderr, "err\ufffd\n")
        self.assertEqual(
            stdout_buffer.getvalue().decode("cp1254"), r"out\ufffd" + "\n"
        )
        self.assertEqual(
            stderr_buffer.getvalue().decode("ascii"), r"err\ufffd" + "\n"
        )

    def test_redirected_text_wrapper_uses_declared_encoding(self) -> None:
        buffer = io.BytesIO()
        stream = io.TextIOWrapper(
            buffer,
            encoding="cp1254",
            errors="strict",
            newline="",
            write_through=True,
        )
        self.assertFalse(stream.isatty())
        console_output.write_console_safe(stream, "pipe\ufffd")
        self.assertEqual(buffer.getvalue().decode("cp1254"), r"pipe\ufffd")

    def test_missing_or_unknown_stream_encoding_uses_ascii_fallback(self) -> None:
        for encoding in (None, "not-a-real-codec"):
            with self.subTest(encoding=encoding):
                stream = RecordingStream(encoding)
                console_output.write_console_safe(stream, "\ufffd")
                self.assertEqual(stream.values, [r"\ufffd"])

    def test_misreported_stream_encoding_retries_only_unicode_error(self) -> None:
        stream = MisreportedEncodingStream()
        console_output.write_console_safe(stream, "\ufffd")
        self.assertEqual(stream.calls, 2)
        self.assertEqual(stream.values, [r"\ufffd"])

    def test_broken_pipe_and_non_encoding_oserror_are_not_swallowed(self) -> None:
        for error in (BrokenPipeError("closed"), OSError("device failed")):
            with self.subTest(error=type(error).__name__):
                with self.assertRaises(type(error)):
                    console_output.write_console_safe(RaisingStream(error), "text")

    def test_atomic_utf8_artifact_preserves_text_and_hash(self) -> None:
        path = self.root / "canonical.txt"
        text = "before\ufffdafter\n"
        value = console_output.atomic_write_utf8(path, text)
        self.assertEqual(value, text.encode("utf-8"))
        self.assertEqual(path.read_bytes(), value)
        self.assertEqual(
            hashlib.sha256(path.read_bytes()).hexdigest(),
            hashlib.sha256(text.encode("utf-8")).hexdigest(),
        )

    def test_canonical_write_failure_remains_fatal(self) -> None:
        path = self.root / "canonical.txt"
        with mock.patch.object(
            console_output.os,
            "replace",
            side_effect=PermissionError("denied"),
        ):
            with self.assertRaises(PermissionError):
                console_output.atomic_write_utf8(path, "evidence")
        self.assertFalse(path.exists())

    def test_run_process_preserves_raw_invalid_utf8_and_escapes_console(self) -> None:
        transcript = self.transcript()
        with installed_stream("stdout", "cp1254") as (_, buffer):
            self.qualification.run_process(
                self.child_bytes(b"\xff\xfe"),
                transcript=transcript,
                timeout=30,
            )
        self.assertEqual(
            transcript.with_name("transcript.stdout.bin").read_bytes(),
            b"\xff\xfe",
        )
        self.assertEqual(
            transcript.with_name("transcript.stderr.bin").read_bytes(),
            b"",
        )
        canonical = transcript.read_text(encoding="utf-8")
        self.assertEqual(canonical.count("\ufffd"), 2)
        self.assertTrue(
            buffer.getvalue().decode("cp1254").endswith(r"\ufffd\ufffd")
        )
        identity = json.loads(
            transcript.with_name("transcript.artifacts.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(
            identity["artifacts"]["stdout"],
            {
                "filename": "transcript.stdout.bin",
                "sha256": hashlib.sha256(b"\xff\xfe").hexdigest(),
                "byte_size": 2,
            },
        )
        self.assertEqual(identity["artifacts"]["stderr"]["byte_size"], 0)
        self.assertEqual(
            identity["artifacts"]["transcript"]["sha256"],
            hashlib.sha256(transcript.read_bytes()).hexdigest(),
        )

    def test_run_process_keeps_console_text_out_of_canonical_hash(self) -> None:
        transcript = self.transcript()
        with installed_stream("stdout", "cp1254") as (_, buffer):
            self.qualification.run_process(
                self.child_bytes("\ufffd".encode("utf-8")),
                transcript=transcript,
                timeout=30,
            )
        canonical = transcript.read_bytes()
        rendered = buffer.getvalue()
        self.assertIn("\ufffd".encode("utf-8"), canonical)
        self.assertIn(rb"\ufffd", rendered)
        self.assertNotEqual(
            hashlib.sha256(canonical).digest(),
            hashlib.sha256(rendered).digest(),
        )

    def test_console_rendering_does_not_mutate_receipt_or_scorer_input(self) -> None:
        evidence = {
            "receipt": {"payload_sha256": "a" * 64},
            "message": "blocked\ufffd",
        }
        before = json.dumps(evidence, ensure_ascii=False, sort_keys=True).encode(
            "utf-8"
        )
        stream = RecordingStream("cp1254")
        console_output.write_console_safe(stream, before.decode("utf-8"))
        after = json.dumps(evidence, ensure_ascii=False, sort_keys=True).encode(
            "utf-8"
        )
        self.assertEqual(after, before)
        self.assertIn(r"\ufffd", stream.values[0])

    def test_run_process_continues_after_safe_presentation(self) -> None:
        transcript = self.transcript()
        continued = False
        with installed_stream("stdout", "cp1254"):
            self.qualification.run_process(
                self.child_bytes("\ufffd".encode("utf-8")),
                transcript=transcript,
                timeout=30,
            )
            continued = True
        self.assertTrue(continued)
        self.assertTrue(transcript.is_file())

    def test_presentation_io_failure_cannot_bypass_caller_finally(self) -> None:
        transcript = self.transcript()
        original = sys.stdout
        restored = False
        try:
            sys.stdout = RaisingStream(OSError("presentation failed"))
            with self.assertRaises(OSError):
                self.qualification.run_process(
                    self.child_bytes(b"output"),
                    transcript=transcript,
                    timeout=30,
                )
        finally:
            sys.stdout = original
            restored = True
        self.assertTrue(restored)
        self.assertTrue(transcript.is_file())

    def test_environment_values_are_not_emitted_by_console_helper(self) -> None:
        stream = RecordingStream("ascii")
        with mock.patch.dict(os.environ, {"H04RW_TEST_SECRET": "private-value"}):
            console_output.write_console_safe(stream, "harmless")
        self.assertEqual(stream.values, ["harmless"])
        self.assertNotIn("private-value", "".join(stream.values))

    def test_tracked_fixture_contains_no_absolute_user_path(self) -> None:
        source = Path(__file__).read_text(encoding="utf-8")
        self.assertNotIn("C:" + "\\Users\\", source)
        self.assertNotIn("/" + "home/", source)

    def test_cp1254_subprocess_executes_real_transcript_seam(self) -> None:
        transcript = self.root / "integration.txt"
        source = (
            "import sys\n"
            "from pathlib import Path\n"
            f"sys.path.insert(0,{str(SCRIPT_DIR)!r})\n"
            "import run_exact_artifact_qualification as q\n"
            "q.run_process([sys.executable,'-c',"
            "\"import sys;sys.stdout.buffer.write('\\\\ufffd'.encode('utf-8'))\"],"
            "transcript=Path(sys.argv[1]),timeout=30)\n"
        )
        env = {
            **os.environ,
            "PYTHONIOENCODING": "cp1254:strict",
            "PYTHONUTF8": "0",
        }
        result = subprocess.run(
            [sys.executable, "-c", source, str(transcript)],
            cwd=ROOT,
            env=env,
            capture_output=True,
            check=False,
        )
        self.assertEqual(
            result.returncode,
            0,
            result.stderr.decode("ascii", "replace"),
        )
        self.assertEqual(result.stdout, rb"\ufffd")
        self.assertIn("\ufffd", transcript.read_text(encoding="utf-8"))
        self.assertEqual(
            transcript.with_name("integration.stdout.bin").read_bytes(),
            "\ufffd".encode("utf-8"),
        )


if __name__ == "__main__":
    unittest.main()
