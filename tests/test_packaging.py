from __future__ import annotations

import contextlib
import importlib.util
import json
import os
import stat
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("package_plugins", ROOT / "scripts/package_plugins.py")
module = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(module)

EXPECTED_DIGESTS = {
    "engineering-foundation-core": "2eb3327e0a1288cdc55627a8feaa4315f39d59071de853b02ebe62bca1f1e0ac",
    "engineering-foundation-laravel": "64fb34691d66b7051c77c0a90058631ef7e0b308cd010878777642696d65a79c",
    "engineering-foundation-design": "3f7d5f37d264e7aa1d2ab94dea12a62806e5cef1728225319845429a33a63296",
    "engineering-foundation-cloud": "4fe88385d98e3ef2b36aa2b304b891c76db61db99f88480e211efb6b7a575982",
    "engineering-foundation-authoring": "cbd7906aa03af50e850b253f4ecf17ced202b126f4fa33ba120036f5f196f07b",
}


def write_minimal_plugin(plugin_root: Path) -> None:
    (plugin_root / ".codex-plugin").mkdir(parents=True)
    (plugin_root / ".claude-plugin").mkdir()
    (plugin_root / "skills/fixture").mkdir(parents=True)
    (plugin_root / "plugin.json").write_text("{}\n", encoding="utf-8")
    (plugin_root / ".codex-plugin/plugin.json").write_text("{}\n", encoding="utf-8")
    (plugin_root / ".claude-plugin/plugin.json").write_text("{}\n", encoding="utf-8")
    (plugin_root / "skills/fixture/SKILL.md").write_text(
        "---\nname: fixture\ndescription: fixture\n---\n", encoding="utf-8"
    )
    (plugin_root / "inside.txt").write_text("inside\n", encoding="utf-8")


@contextlib.contextmanager
def real_symlink(test: unittest.TestCase, target: Path, link: Path, *, directory: bool):
    try:
        link.symlink_to(target, target_is_directory=directory)
    except (NotImplementedError, OSError) as exc:
        test.skipTest(f"real filesystem symlinks are unavailable: {exc}")
    try:
        yield link
    finally:
        if link.is_symlink():
            link.unlink()


@contextlib.contextmanager
def windows_junction(test: unittest.TestCase, target: Path, junction: Path):
    if os.name != "nt":
        test.skipTest("real Windows directory junctions require Windows")
    result = subprocess.run(
        ["cmd.exe", "/d", "/c", "mklink", "/J", str(junction), str(target)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        test.fail(
            "failed to create a real Windows directory junction: "
            f"stdout={result.stdout!r} stderr={result.stderr!r}"
        )
    try:
        yield junction
    finally:
        if junction.exists():
            os.rmdir(junction)


class PackagingTests(unittest.TestCase):
    def test_ordinary_safe_tree_is_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repository = Path(tmp) / "repository"
            plugin_root = repository / "plugins/fixture-plugin"
            write_minimal_plugin(plugin_root)

            names = [
                path.relative_to(plugin_root).as_posix()
                for path in module.safe_files(plugin_root, repository_root=repository)
            ]

            self.assertEqual(names, sorted(names))
            self.assertIn("inside.txt", names)
            self.assertIn("skills/fixture/SKILL.md", names)

    def test_file_symlink_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            repository = base / "repository"
            plugin_root = repository / "plugins/fixture-plugin"
            write_minimal_plugin(plugin_root)
            outside = base / "representative-secret.txt"
            outside.write_text("harmless outside content\n", encoding="utf-8")
            link = plugin_root / "linked-file.txt"

            with real_symlink(self, outside, link, directory=False):
                with self.assertRaisesRegex(ValueError, "linked-file"):
                    module.safe_files(plugin_root, repository_root=repository)

    def test_directory_symlink_is_rejected_without_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            repository = base / "repository"
            plugin_root = repository / "plugins/fixture-plugin"
            write_minimal_plugin(plugin_root)
            outside = base / "outside"
            outside.mkdir()
            secret = outside / "representative-secret.txt"
            secret.write_text("harmless outside content\n", encoding="utf-8")
            link = plugin_root / "linked-directory"

            with real_symlink(self, outside, link, directory=True):
                with self.assertRaisesRegex(ValueError, "linked-directory"):
                    module.safe_files(plugin_root, repository_root=repository)
                self.assertTrue(secret.is_file())

    def test_plugin_root_symlink_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            repository = base / "repository"
            (repository / "plugins").mkdir(parents=True)
            real_plugin = base / "real-plugin"
            write_minimal_plugin(real_plugin)
            plugin_link = repository / "plugins/fixture-plugin"

            with real_symlink(self, real_plugin, plugin_link, directory=True):
                with self.assertRaisesRegex(ValueError, "fixture-plugin"):
                    module.safe_files(plugin_link, repository_root=repository)

    @unittest.skipUnless(os.name == "nt", "real Windows directory junctions require Windows")
    def test_windows_descendant_junction_escape_is_rejected_and_not_archived(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            repository = base / "repository"
            plugin_root = repository / "plugins/fixture-plugin"
            write_minimal_plugin(plugin_root)
            outside = base / "outside"
            outside.mkdir()
            secret = outside / "representative-secret.txt"
            secret.write_text("harmless outside content\n", encoding="utf-8")
            junction = plugin_root / "linked-outside"
            output = base / "dist"
            output.mkdir()

            with windows_junction(self, outside, junction):
                self.assertFalse(junction.is_symlink())
                self.assertTrue(module.is_reparse_point(junction.lstat()))
                with self.assertRaisesRegex(ValueError, "linked-outside"):
                    module.safe_files(plugin_root, repository_root=repository)
                with mock.patch.object(module, "ROOT", repository):
                    with self.assertRaisesRegex(ValueError, "linked-outside"):
                        module.build_archive(
                            {
                                "name": "fixture-plugin",
                                "version": "0.0.0",
                                "path": "plugins/fixture-plugin",
                            },
                            output,
                        )
                self.assertFalse((output / "fixture-plugin-0.0.0.zip").exists())
                self.assertTrue(secret.is_file())

    @unittest.skipUnless(os.name == "nt", "real Windows directory junctions require Windows")
    def test_windows_plugin_root_junction_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            repository = base / "repository"
            (repository / "plugins").mkdir(parents=True)
            real_plugin = base / "real-plugin"
            write_minimal_plugin(real_plugin)
            plugin_junction = repository / "plugins/fixture-plugin"

            with windows_junction(self, real_plugin, plugin_junction):
                self.assertFalse(plugin_junction.is_symlink())
                self.assertTrue(module.is_reparse_point(plugin_junction.lstat()))
                with self.assertRaisesRegex(ValueError, "fixture-plugin"):
                    module.safe_files(plugin_junction, repository_root=repository)

    @unittest.skipUnless(os.name == "nt", "real Windows directory junctions require Windows")
    def test_nested_windows_junction_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            repository = base / "repository"
            plugin_root = repository / "plugins/fixture-plugin"
            write_minimal_plugin(plugin_root)
            nested = plugin_root / "nested"
            nested.mkdir()
            outside = base / "outside"
            outside.mkdir()
            (outside / "representative-secret.txt").write_text(
                "harmless outside content\n", encoding="utf-8"
            )
            junction = nested / "linked-outside"

            with windows_junction(self, outside, junction):
                self.assertFalse(junction.is_symlink())
                self.assertTrue(module.is_reparse_point(junction.lstat()))
                with self.assertRaisesRegex(ValueError, "linked-outside"):
                    module.safe_files(plugin_root, repository_root=repository)

    @unittest.skipUnless(hasattr(os, "mkfifo"), "FIFO fixtures require os.mkfifo support")
    def test_unsupported_special_file_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repository = Path(tmp) / "repository"
            plugin_root = repository / "plugins/fixture-plugin"
            write_minimal_plugin(plugin_root)
            fifo = plugin_root / "unsupported.pipe"
            os.mkfifo(fifo)

            with self.assertRaisesRegex(ValueError, "unsupported.pipe"):
                module.safe_files(plugin_root, repository_root=repository)

    def test_plugin_root_must_resolve_under_repository_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            repository = base / "repository"
            repository.mkdir()
            plugin_root = base / "outside-plugin"
            write_minimal_plugin(plugin_root)

            with self.assertRaisesRegex(ValueError, "outside repository root"):
                module.safe_files(plugin_root, repository_root=repository)

    def test_build_archive_revalidates_file_immediately_before_read(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            repository = base / "repository"
            plugin_root = repository / "plugins/fixture-plugin"
            write_minimal_plugin(plugin_root)
            outside = base / "representative-secret.txt"
            outside.write_text("harmless outside content\n", encoding="utf-8")
            inside = plugin_root / "inside.txt"
            output = base / "dist"
            output.mkdir()
            original_safe_files = module.safe_files
            link_created = False

            def replace_after_enumeration(*args, **kwargs):
                nonlocal link_created
                files = original_safe_files(*args, **kwargs)
                inside.unlink()
                try:
                    inside.symlink_to(outside)
                except (NotImplementedError, OSError) as exc:
                    self.skipTest(f"real filesystem symlinks are unavailable: {exc}")
                link_created = True
                return files

            try:
                with mock.patch.object(module, "ROOT", repository):
                    with mock.patch.object(module, "safe_files", replace_after_enumeration):
                        with self.assertRaisesRegex(ValueError, "inside.txt"):
                            module.build_archive(
                                {
                                    "name": "fixture-plugin",
                                    "version": "0.0.0",
                                    "path": "plugins/fixture-plugin",
                                },
                                output,
                            )
            finally:
                if link_created and inside.is_symlink():
                    inside.unlink()

    @unittest.skipUnless(os.name == "nt", "real Windows directory junctions require Windows")
    def test_build_archive_revalidates_parent_components_before_read(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            repository = base / "repository"
            plugin_root = repository / "plugins/fixture-plugin"
            write_minimal_plugin(plugin_root)
            nested = plugin_root / "nested"
            nested.mkdir()
            (nested / "payload.txt").write_text("enumerated content\n", encoding="utf-8")
            replacement = plugin_root / "replacement"
            original_nested = plugin_root / "nested-original"
            output = base / "dist"
            output.mkdir()
            archive = output / "fixture-plugin-0.0.0.zip"
            original_safe_files = module.safe_files

            with contextlib.ExitStack() as stack:

                def replace_parent_after_enumeration(*args, **kwargs):
                    files = original_safe_files(*args, **kwargs)
                    nested.rename(original_nested)
                    replacement.mkdir()
                    (replacement / "payload.txt").write_text(
                        "post-enumeration replacement\n", encoding="utf-8"
                    )
                    stack.enter_context(windows_junction(self, replacement, nested))
                    return files

                with mock.patch.object(module, "ROOT", repository):
                    with mock.patch.object(module, "safe_files", replace_parent_after_enumeration):
                        with self.assertRaisesRegex(ValueError, "nested"):
                            module.build_archive(
                                {
                                    "name": "fixture-plugin",
                                    "version": "0.0.0",
                                    "path": "plugins/fixture-plugin",
                                },
                                output,
                            )

                if archive.exists():
                    with zipfile.ZipFile(archive) as zf:
                        if "nested/payload.txt" in zf.namelist():
                            self.assertNotEqual(
                                zf.read("nested/payload.txt"),
                                b"post-enumeration replacement\n",
                            )

    def test_each_plugin_builds_a_safe_deterministic_archive(self) -> None:
        catalog = json.loads((ROOT / "catalog/plugins.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            for plugin in catalog["plugins"]:
                archive, first_digest = module.build_archive(plugin, output)
                _, second_digest = module.build_archive(plugin, output)
                self.assertEqual(first_digest, second_digest)
                self.assertEqual(first_digest, EXPECTED_DIGESTS[plugin["name"]])
                with zipfile.ZipFile(archive) as zf:
                    names = zf.namelist()
                    self.assertEqual(names, sorted(names))
                    self.assertIn("plugin.json", names)
                    self.assertIn(".codex-plugin/plugin.json", names)
                    self.assertIn(".claude-plugin/plugin.json", names)
                    self.assertTrue(any(name.endswith("/SKILL.md") for name in names))
                    self.assertTrue(all(not Path(name).is_absolute() and ".." not in Path(name).parts for name in names))
                    for info in zf.infolist():
                        self.assertEqual(info.create_system, 3)
                        self.assertEqual(info.compress_type, zipfile.ZIP_STORED)
                        mode = info.external_attr >> 16
                        self.assertEqual(mode & 0o170000, stat.S_IFREG)
                        self.assertEqual(mode & 0o777, 0o644)


if __name__ == "__main__":
    unittest.main()
