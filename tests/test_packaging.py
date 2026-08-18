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
from pathlib import Path, PurePosixPath
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("package_plugins", ROOT / "scripts/package_plugins.py")
module = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(module)

EXPECTED_DIGESTS = {
    "engineering-foundation-core": "a505d9d7d376ace3f2cd5fd5369dc417d0067a4eb03d2b5141276378e0065941",
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


def write_minimal_catalog(repository: Path) -> Path:
    return write_catalog(
        repository,
        [
            {
                "name": "fixture-plugin",
                "version": "0.0.0",
                "path": "plugins/fixture-plugin",
            }
        ],
    )


def write_catalog(repository: Path, plugins: list[dict[str, str]]) -> Path:
    catalog = repository / "catalog/plugins.json"
    catalog.parent.mkdir(parents=True, exist_ok=True)
    catalog.write_text(json.dumps({"plugins": plugins}), encoding="utf-8")
    return catalog


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

    def test_plugin_path_ancestor_symlink_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repository = Path(tmp) / "repository"
            repository.mkdir()
            real_plugins = repository / "real-plugins"
            write_minimal_plugin(real_plugins / "fixture-plugin")
            linked_plugins = repository / "plugins"

            with real_symlink(self, real_plugins, linked_plugins, directory=True):
                with self.assertRaisesRegex(ValueError, "plugins"):
                    module.safe_files(
                        linked_plugins / "fixture-plugin", repository_root=repository
                    )

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
    def test_windows_plugin_path_ancestor_junction_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repository = Path(tmp) / "repository"
            repository.mkdir()
            real_plugins = repository / "real-plugins"
            write_minimal_plugin(real_plugins / "fixture-plugin")
            plugin_parent = repository / "plugins"

            with windows_junction(self, real_plugins, plugin_parent):
                self.assertFalse(plugin_parent.is_symlink())
                self.assertTrue(module.is_reparse_point(plugin_parent.lstat()))
                with self.assertRaisesRegex(ValueError, "plugins"):
                    module.safe_files(
                        plugin_parent / "fixture-plugin", repository_root=repository
                    )

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

    def test_release_path_rejects_cross_platform_backslash_traversal(self) -> None:
        with self.assertRaisesRegex(ValueError, "unsafe release path"):
            module.validate_relative_path(
                PurePosixPath(r"nested\..\representative-secret.txt")
            )

    @unittest.skipIf(os.name == "nt", "backslash is not a legal filename character on Windows")
    def test_posix_backslash_traversal_name_is_rejected_and_not_archived(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            repository = base / "repository"
            plugin_root = repository / "plugins/fixture-plugin"
            write_minimal_plugin(plugin_root)
            (plugin_root / r"nested\..\representative-secret.txt").write_text(
                "harmless content\n", encoding="utf-8"
            )
            output = base / "dist"
            output.mkdir()
            archive = output / "fixture-plugin-0.0.0.zip"

            with mock.patch.object(module, "ROOT", repository):
                with self.assertRaisesRegex(ValueError, "unsafe release path"):
                    module.build_archive(
                        {
                            "name": "fixture-plugin",
                            "version": "0.0.0",
                            "path": "plugins/fixture-plugin",
                        },
                        output,
                    )

            self.assertFalse(archive.exists())

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
            archive = output / "fixture-plugin-0.0.0.zip"
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

            self.assertFalse(archive.exists(), "a failed build must not leave a partial archive")
            self.assertEqual(list(output.iterdir()), [], "a failed build must remove temp files")

    def test_failed_rebuild_preserves_previous_complete_archive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            repository = base / "repository"
            plugin_root = repository / "plugins/fixture-plugin"
            write_minimal_plugin(plugin_root)
            output = base / "dist"
            output.mkdir()
            archive = output / "fixture-plugin-0.0.0.zip"
            previous = b"previous complete archive\n"
            archive.write_bytes(previous)

            with (
                mock.patch.object(module, "ROOT", repository),
                mock.patch.object(
                    module,
                    "read_verified_file",
                    side_effect=ValueError("simulated read failure"),
                ),
            ):
                with self.assertRaisesRegex(ValueError, "simulated read failure"):
                    module.build_archive(
                        {
                            "name": "fixture-plugin",
                            "version": "0.0.0",
                            "path": "plugins/fixture-plugin",
                        },
                        output,
                    )

            self.assertEqual(archive.read_bytes(), previous)
            self.assertEqual(list(output.iterdir()), [archive])

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

                self.assertFalse(
                    archive.exists(), "a rejected parent replacement must not publish an archive"
                )

    @unittest.skipUnless(os.name == "nt", "real Windows directory junctions require Windows")
    def test_main_rejects_output_junction_before_deleting_or_writing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            repository = base / "repository"
            write_minimal_plugin(repository / "plugins/fixture-plugin")
            catalog = write_minimal_catalog(repository)
            outside = base / "outside"
            outside.mkdir()
            existing = outside / "existing.zip"
            existing.write_bytes(b"harmless existing archive\n")
            output_junction = repository / "dist"

            with windows_junction(self, outside, output_junction):
                self.assertFalse(output_junction.is_symlink())
                self.assertTrue(module.is_reparse_point(output_junction.lstat()))
                with (
                    mock.patch.object(module, "ROOT", repository),
                    mock.patch.object(module, "CATALOG", catalog),
                    mock.patch.object(
                        module.sys,
                        "argv",
                        ["package_plugins.py", "--output", "dist"],
                    ),
                ):
                    result = module.main()

            self.assertEqual(result, 1)
            self.assertEqual(existing.read_bytes(), b"harmless existing archive\n")
            self.assertFalse((outside / "fixture-plugin-0.0.0.zip").exists())
            self.assertFalse((outside / "SHA256SUMS").exists())

    def test_main_rejects_output_directory_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            repository = base / "repository"
            write_minimal_plugin(repository / "plugins/fixture-plugin")
            catalog = write_minimal_catalog(repository)
            outside = base / "outside"
            outside.mkdir()
            existing = outside / "existing.zip"
            existing.write_bytes(b"harmless existing archive\n")
            output_link = repository / "dist"

            with real_symlink(self, outside, output_link, directory=True):
                with (
                    mock.patch.object(module, "ROOT", repository),
                    mock.patch.object(module, "CATALOG", catalog),
                    mock.patch.object(
                        module.sys,
                        "argv",
                        ["package_plugins.py", "--output", "dist"],
                    ),
                ):
                    result = module.main()

            self.assertEqual(result, 1)
            self.assertEqual(existing.read_bytes(), b"harmless existing archive\n")
            self.assertFalse((outside / "fixture-plugin-0.0.0.zip").exists())
            self.assertFalse((outside / "SHA256SUMS").exists())

    @unittest.skipUnless(os.name == "nt", "real Windows directory junctions require Windows")
    def test_main_rejects_nested_output_junction_before_creating_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            repository = base / "repository"
            write_minimal_plugin(repository / "plugins/fixture-plugin")
            catalog = write_minimal_catalog(repository)
            outside = base / "outside"
            outside.mkdir()
            output_parent = repository / "release"

            with windows_junction(self, outside, output_parent):
                with (
                    mock.patch.object(module, "ROOT", repository),
                    mock.patch.object(module, "CATALOG", catalog),
                    mock.patch.object(
                        module.sys,
                        "argv",
                        ["package_plugins.py", "--output", "release/dist"],
                    ),
                ):
                    result = module.main()

            self.assertEqual(result, 1)
            self.assertFalse((outside / "dist").exists())

    def test_main_rejects_broken_checksum_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            repository = base / "repository"
            write_minimal_plugin(repository / "plugins/fixture-plugin")
            catalog = write_minimal_catalog(repository)
            output = repository / "dist"
            output.mkdir()
            outside_checksum = base / "outside-checksums.txt"
            checksum_link = output / "SHA256SUMS"

            with real_symlink(self, outside_checksum, checksum_link, directory=False):
                self.assertFalse(checksum_link.exists())
                self.assertTrue(checksum_link.is_symlink())
                with (
                    mock.patch.object(module, "ROOT", repository),
                    mock.patch.object(module, "CATALOG", catalog),
                    mock.patch.object(
                        module.sys,
                        "argv",
                        ["package_plugins.py", "--output", "dist"],
                    ),
                ):
                    result = module.main()

                self.assertEqual(result, 1)
                self.assertFalse(outside_checksum.exists())

    def test_main_rejects_existing_archive_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            repository = base / "repository"
            write_minimal_plugin(repository / "plugins/fixture-plugin")
            catalog = write_minimal_catalog(repository)
            output = repository / "dist"
            output.mkdir()
            outside_archive = base / "outside.zip"
            outside_archive.write_bytes(b"harmless outside archive\n")
            archive_link = output / "fixture-plugin-0.0.0.zip"

            with real_symlink(self, outside_archive, archive_link, directory=False):
                with (
                    mock.patch.object(module, "ROOT", repository),
                    mock.patch.object(module, "CATALOG", catalog),
                    mock.patch.object(
                        module.sys,
                        "argv",
                        ["package_plugins.py", "--output", "dist"],
                    ),
                ):
                    result = module.main()

                self.assertEqual(result, 1)
                self.assertEqual(
                    outside_archive.read_bytes(), b"harmless outside archive\n"
                )

    def test_main_rejects_output_outside_repository_before_creating_it(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            repository = base / "repository"
            write_minimal_plugin(repository / "plugins/fixture-plugin")
            catalog = write_minimal_catalog(repository)
            outside_output = base / "outside-dist"

            with (
                mock.patch.object(module, "ROOT", repository),
                mock.patch.object(module, "CATALOG", catalog),
                mock.patch.object(
                    module.sys,
                    "argv",
                    ["package_plugins.py", "--output", str(outside_output)],
                ),
            ):
                result = module.main()

            self.assertEqual(result, 1)
            self.assertFalse(outside_output.exists())

    def test_main_removes_completed_outputs_when_a_later_plugin_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repository = Path(tmp) / "repository"
            write_minimal_plugin(repository / "plugins/first-plugin")
            (repository / "plugins/broken-plugin").mkdir(parents=True)
            catalog = write_catalog(
                repository,
                [
                    {
                        "name": "first-plugin",
                        "version": "0.0.0",
                        "path": "plugins/first-plugin",
                    },
                    {
                        "name": "broken-plugin",
                        "version": "0.0.0",
                        "path": "plugins/broken-plugin",
                    },
                ],
            )

            with (
                mock.patch.object(module, "ROOT", repository),
                mock.patch.object(module, "CATALOG", catalog),
                mock.patch.object(module.sys, "argv", ["package_plugins.py"]),
            ):
                result = module.main()

            self.assertEqual(result, 1)
            self.assertEqual(list((repository / "dist").iterdir()), [])

    def test_main_removes_first_build_when_determinism_rebuild_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repository = Path(tmp) / "repository"
            write_minimal_plugin(repository / "plugins/fixture-plugin")
            catalog = write_minimal_catalog(repository)
            original_build_archive = module.build_archive
            call_count = 0

            def fail_second_build(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count == 2:
                    raise ValueError("simulated deterministic rebuild failure")
                return original_build_archive(*args, **kwargs)

            with (
                mock.patch.object(module, "ROOT", repository),
                mock.patch.object(module, "CATALOG", catalog),
                mock.patch.object(module, "build_archive", fail_second_build),
                mock.patch.object(
                    module.sys,
                    "argv",
                    ["package_plugins.py", "--check"],
                ),
            ):
                result = module.main()

            self.assertEqual(result, 1)
            self.assertEqual(call_count, 2)
            self.assertEqual(list((repository / "dist").iterdir()), [])

    def test_main_rejects_duplicate_archive_destinations(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repository = Path(tmp) / "repository"
            write_minimal_plugin(repository / "plugins/fixture-plugin")
            plugin = {
                "name": "fixture-plugin",
                "version": "0.0.0",
                "path": "plugins/fixture-plugin",
            }
            catalog = write_catalog(repository, [plugin, plugin.copy()])

            with (
                mock.patch.object(module, "ROOT", repository),
                mock.patch.object(module, "CATALOG", catalog),
                mock.patch.object(module.sys, "argv", ["package_plugins.py"]),
            ):
                result = module.main()

            self.assertEqual(result, 1)
            self.assertEqual(list((repository / "dist").iterdir()), [])

    def test_build_archive_rejects_archive_filename_escape(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            repository = base / "repository"
            write_minimal_plugin(repository / "plugins/fixture-plugin")
            output = base / "dist"
            output.mkdir()
            escaped_archive = base / "escaped-0.0.0.zip"

            with mock.patch.object(module, "ROOT", repository):
                with self.assertRaisesRegex(ValueError, "archive filename"):
                    module.build_archive(
                        {
                            "name": "../escaped",
                            "version": "0.0.0",
                            "path": "plugins/fixture-plugin",
                        },
                        output,
                    )

            self.assertFalse(escaped_archive.exists())

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
