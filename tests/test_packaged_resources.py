from __future__ import annotations

import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import packaged_resources


def load_script(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


package_plugins = load_script(
    "package_plugins_for_packaged_resources", ROOT / "scripts/package_plugins.py"
)
validate_repository = load_script(
    "validate_repository_for_packaged_resources", ROOT / "scripts/validate_repository.py"
)

EXPECTED_DIGESTS = {
    "engineering-foundation-core": "a505d9d7d376ace3f2cd5fd5369dc417d0067a4eb03d2b5141276378e0065941",
    "engineering-foundation-laravel": "64fb34691d66b7051c77c0a90058631ef7e0b308cd010878777642696d65a79c",
    "engineering-foundation-design": "3f7d5f37d264e7aa1d2ab94dea12a62806e5cef1728225319845429a33a63296",
    "engineering-foundation-cloud": "4fe88385d98e3ef2b36aa2b304b891c76db61db99f88480e211efb6b7a575982",
    "engineering-foundation-authoring": "cbd7906aa03af50e850b253f4ecf17ced202b126f4fa33ba120036f5f196f07b",
}


def write_fixture_plugin(
    repository: Path,
    body: str,
    *,
    resources: dict[str, str | bytes] | None = None,
) -> tuple[Path, Path, dict[str, str]]:
    plugin_root = repository / "plugins/fixture-plugin"
    (plugin_root / ".codex-plugin").mkdir(parents=True)
    (plugin_root / ".claude-plugin").mkdir()
    skill_root = plugin_root / "skills/example-skill"
    skill_root.mkdir(parents=True)
    for manifest in (
        plugin_root / "plugin.json",
        plugin_root / ".codex-plugin/plugin.json",
        plugin_root / ".claude-plugin/plugin.json",
    ):
        manifest.write_text("{}\n", encoding="utf-8")
    (skill_root / "SKILL.md").write_text(
        "---\nname: example-skill\ndescription: fixture\n---\n\n" + body,
        encoding="utf-8",
    )
    for relative, content in (resources or {}).items():
        path = skill_root / Path(relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content, encoding="utf-8")
    return plugin_root, skill_root, {
        "name": "fixture-plugin",
        "version": "0.0.0",
        "path": "plugins/fixture-plugin",
    }


def source_references(plugin_root: Path) -> list[packaged_resources.ResourceReference]:
    return packaged_resources.validate_source_plugin(plugin_root, "fixture-plugin")


def zip_from_members(members: list[tuple[str, bytes]]) -> tuple[io.BytesIO, zipfile.ZipFile]:
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w", compression=zipfile.ZIP_STORED) as archive:
        for name, content in members:
            archive.writestr(name, content)
    payload.seek(0)
    return payload, zipfile.ZipFile(payload, "r")


class PackagedResourceTests(unittest.TestCase):
    def assert_source_error(
        self,
        body: str,
        code: str,
        *,
        resources: dict[str, str | bytes] | None = None,
    ) -> packaged_resources.ResourceClosureError:
        with tempfile.TemporaryDirectory() as tmp:
            plugin_root, _, _ = write_fixture_plugin(
                Path(tmp) / "repository", body, resources=resources
            )
            with self.assertRaises(packaged_resources.ResourceClosureError) as raised:
                source_references(plugin_root)
            self.assertEqual(raised.exception.finding.code, code)
            return raised.exception

    def test_valid_skill_markdown_script_reference(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plugin_root, _, _ = write_fixture_plugin(
                Path(tmp) / "repository",
                "Use [the helper](scripts/tool.py).\n",
                resources={"scripts/tool.py": "print('safe')\n"},
            )
            references = source_references(plugin_root)
            self.assertEqual(len(references), 1)
            self.assertEqual(references[0].resource_path, "scripts/tool.py")
            self.assertEqual(references[0].zip_member, "skills/example-skill/scripts/tool.py")

    def test_valid_reference_markdown_link(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plugin_root, _, _ = write_fixture_plugin(
                Path(tmp) / "repository",
                "Read [preflight](references/preflight.md).\n",
                resources={"references/preflight.md": "# Preflight\n"},
            )
            references = source_references(plugin_root)
            self.assertEqual([item.resource_type for item in references], ["references"])

    def test_valid_markdown_image_asset(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plugin_root, _, _ = write_fixture_plugin(
                Path(tmp) / "repository",
                "![Example](assets/example.png)\n",
                resources={"assets/example.png": b"harmless-image-fixture"},
            )
            references = source_references(plugin_root)
            self.assertEqual(references[0].surface, "markdown_image")
            self.assertEqual(references[0].resource_type, "assets")

    def test_markdown_titles_and_parenthesized_destinations_are_recognized(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plugin_root, _, _ = write_fixture_plugin(
                Path(tmp) / "repository",
                (
                    '[helper](scripts/tool.py "Run helper")\n'
                    "![Example](assets/example.png 'Preview')\n"
                    "[alternate](<scripts/tool(1).py>)\n"
                ),
                resources={
                    "scripts/tool.py": "# helper\n",
                    "scripts/tool(1).py": "# alternate\n",
                    "assets/example.png": b"harmless-image-fixture",
                },
            )
            references = source_references(plugin_root)
            self.assertEqual(
                [reference.resource_path for reference in references],
                ["scripts/tool.py", "assets/example.png", "scripts/tool(1).py"],
            )

    def test_missing_titled_and_parenthesized_destinations_fail_closed(self) -> None:
        for body in (
            '[x](scripts/missing.py "title")\n',
            "![x](assets/missing.png 'title')\n",
            "[x](<scripts/missing(1).py>)\n",
        ):
            with self.subTest(body=body):
                self.assert_source_error(body, "missing_resource")

    def test_angle_destinations_with_spaces_are_source_declarations(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plugin_root, _, _ = write_fixture_plugin(
                Path(tmp) / "repository",
                (
                    "[helper](<scripts/my tool.py>)\n"
                    "[guide](<references/my guide.md>)\n"
                    "![diagram](<assets/system diagram.png>)\n"
                ),
                resources={
                    "scripts/my tool.py": "# helper\n",
                    "references/my guide.md": "# Guide\n",
                    "assets/system diagram.png": b"harmless-image-fixture",
                },
            )

            references = source_references(plugin_root)

            self.assertEqual(
                [reference.resource_path for reference in references],
                [
                    "scripts/my tool.py",
                    "references/my guide.md",
                    "assets/system diagram.png",
                ],
            )

    def test_missing_angle_destinations_with_spaces_fail_source_closure(self) -> None:
        for body in (
            "[helper](<scripts/missing tool.py>)\n",
            "[guide](<references/missing guide.md>)\n",
            "![diagram](<assets/missing diagram.png>)\n",
        ):
            with self.subTest(body=body):
                self.assert_source_error(body, "missing_resource")

    def test_inline_code_with_spaces_remains_non_declarative(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plugin_root, _, _ = write_fixture_plugin(
                Path(tmp) / "repository",
                (
                    "Run `python scripts/missing tool.py --check`. "
                    "The prose `references/missing guide.md is optional` is illustrative.\n"
                ),
            )

            self.assertEqual(source_references(plugin_root), [])

    def test_package_and_zip_closure_preserve_spaced_resource_members(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repository = Path(tmp) / "repository"
            plugin_root, _, plugin = write_fixture_plugin(
                repository,
                (
                    "[helper](<scripts/my tool.py>)\n"
                    "[guide](<references/my guide.md>)\n"
                    "![diagram](<assets/system diagram.png>)\n"
                ),
                resources={
                    "scripts/my tool.py": "# helper\n",
                    "references/my guide.md": "# Guide\n",
                    "assets/system diagram.png": b"harmless-image-fixture",
                },
            )
            output = repository / "dist"
            output.mkdir(parents=True)
            original_root = package_plugins.ROOT
            package_plugins.ROOT = repository
            try:
                archive_path, _ = package_plugins.build_archive(plugin, output)
            finally:
                package_plugins.ROOT = original_root

            with zipfile.ZipFile(archive_path) as archive:
                names = archive.namelist()
                validated = packaged_resources.validate_zip_closure(
                    plugin_root,
                    "fixture-plugin",
                    archive,
                    repository_root=repository,
                )
            self.assertEqual(len(validated), 3)
            self.assertIn("skills/example-skill/scripts/my tool.py", names)
            self.assertIn("skills/example-skill/references/my guide.md", names)
            self.assertIn("skills/example-skill/assets/system diagram.png", names)

    def test_spaced_resource_source_case_mismatch_fails_on_windows_too(self) -> None:
        cases = (
            (
                "[helper](<scripts/My Tool.py>)\n",
                {"scripts/my tool.py": "# helper\n"},
            ),
            (
                "[guide](<references/My Guide.md>)\n",
                {"references/my guide.md": "# Guide\n"},
            ),
            (
                "![diagram](<assets/System Diagram.png>)\n",
                {"assets/system diagram.png": b"harmless-image-fixture"},
            ),
        )
        for body, resources in cases:
            with self.subTest(body=body):
                self.assert_source_error(body, "case_mismatch", resources=resources)

    def test_spaced_resource_zip_case_mismatch_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plugin_root, skill_root, _ = write_fixture_plugin(
                Path(tmp) / "repository",
                "[helper](<scripts/my tool.py>)\n",
                resources={"scripts/my tool.py": "# helper\n"},
            )
            references = source_references(plugin_root)
            payload, archive = zip_from_members(
                [
                    ("skills/example-skill/SKILL.md", (skill_root / "SKILL.md").read_bytes()),
                    ("skills/example-skill/scripts/My Tool.py", b"wrong case"),
                ]
            )
            try:
                with self.assertRaises(packaged_resources.ResourceClosureError) as raised:
                    packaged_resources.validate_zip_closure(
                        plugin_root,
                        "fixture-plugin",
                        archive,
                        references=references,
                    )
                self.assertEqual(raised.exception.finding.code, "zip_case_mismatch")
            finally:
                archive.close()
                payload.close()

    def test_valid_standalone_inline_code_resource(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plugin_root, _, _ = write_fixture_plugin(
                Path(tmp) / "repository",
                "Run `scripts/tool.py`.\n",
                resources={"scripts/tool.py": "# helper\n"},
            )
            references = source_references(plugin_root)
            self.assertEqual(references[0].surface, "inline_code")

    def test_reference_document_declaration_is_scanned(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plugin_root, _, _ = write_fixture_plugin(
                Path(tmp) / "repository",
                "No declaration here.\n",
                resources={
                    "references/guide.md": "Run `scripts/tool.py`.\n",
                    "scripts/tool.py": "# helper\n",
                },
            )
            references = source_references(plugin_root)
            self.assertEqual(len(references), 1)
            self.assertEqual(references[0].document.as_posix(), "references/guide.md")

    def test_fenced_code_block_is_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plugin_root, _, _ = write_fixture_plugin(
                Path(tmp) / "repository",
                "```sh\npython scripts/missing.py\n```\n",
            )
            self.assertEqual(source_references(plugin_root), [])

    def test_escaped_backticks_are_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plugin_root, _, _ = write_fixture_plugin(
                Path(tmp) / "repository",
                "Literal: \\`scripts/missing.py\\`.\n",
            )
            self.assertEqual(source_references(plugin_root), [])

    def test_external_anchor_malformed_and_shell_tokens_are_ignored(self) -> None:
        body = (
            "[external](https://example.test/scripts/tool.py) [anchor](#scripts)\n"
            "[ftp](ftp://example.test/scripts/tool.py) "
            "![cdn](//cdn.example.test/assets/example.png)\n"
            "[malformed](scripts/missing.py\n"
            "`python scripts/missing.py`\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            plugin_root, _, _ = write_fixture_plugin(Path(tmp) / "repository", body)
            self.assertEqual(source_references(plugin_root), [])

    def test_placeholder_wildcard_and_directory_examples_are_ignored(self) -> None:
        body = (
            "`scripts/*.py` `scripts/tool?.py` `scripts/tool[0-9].py` "
            "`scripts/$TOOL.py` `<path>/scripts/tool.py` `$ROOT/scripts/tool.py` "
            "`references/` `assets/`\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            plugin_root, _, _ = write_fixture_plugin(Path(tmp) / "repository", body)
            self.assertEqual(source_references(plugin_root), [])

    def test_missing_script_fails_closed(self) -> None:
        self.assert_source_error("`scripts/missing.py`\n", "missing_resource")

    def test_missing_reference_fails_closed(self) -> None:
        self.assert_source_error("`references/missing.md`\n", "missing_resource")

    def test_missing_asset_fails_closed(self) -> None:
        self.assert_source_error("![x](assets/missing.png)\n", "missing_resource")

    def test_exact_case_mismatch_fails_on_every_platform(self) -> None:
        self.assert_source_error(
            "`scripts/tool.py`\n",
            "case_mismatch",
            resources={"scripts/Tool.py": "# helper\n"},
        )

    def test_parent_traversal_is_rejected(self) -> None:
        self.assert_source_error("`../scripts/tool.py`\n", "parent_traversal")

    def test_dot_and_empty_segments_are_rejected(self) -> None:
        for reference, code in (
            ("scripts/./tool.py", "dot_segment"),
            ("scripts//tool.py", "empty_segment"),
        ):
            with self.subTest(reference=reference):
                self.assert_source_error(f"`{reference}`\n", code)

    def test_absolute_posix_path_is_rejected(self) -> None:
        self.assert_source_error("`/scripts/tool.py`\n", "absolute_path")

    def test_windows_drive_path_is_rejected(self) -> None:
        self.assert_source_error("`C:/scripts/tool.py`\n", "windows_absolute_path")

    def test_unc_path_is_rejected(self) -> None:
        self.assert_source_error(
            r"`\\server\share\assets\example.png`" + "\n",
            "backslash",
        )

    def test_backslash_path_is_rejected(self) -> None:
        self.assert_source_error(r"`scripts\tool.py`" + "\n", "backslash")

    def test_percent_encoded_traversal_is_rejected(self) -> None:
        self.assert_source_error(
            "`%2e%2e/scripts/tool.py`\n",
            "percent_encoding",
        )

    def test_query_string_is_rejected(self) -> None:
        for body in (
            "`scripts/tool.py?raw=1`\n",
            "`scripts/tool.py?raw`\n",
            "[x](scripts/tool?file=output.json)\n",
            "[x](scripts/tool?.py)\n",
        ):
            with self.subTest(body=body):
                self.assert_source_error(body, "query_string")

    def test_valid_markdown_reference_fragment(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plugin_root, _, _ = write_fixture_plugin(
                Path(tmp) / "repository",
                "[section](references/guide.md#safe-section)\n",
                resources={"references/guide.md": "# Safe section\n"},
            )
            references = source_references(plugin_root)
            self.assertEqual(references[0].fragment, "safe-section")

    def test_fragment_on_non_markdown_resource_is_rejected(self) -> None:
        self.assert_source_error(
            "[tool](scripts/tool.py#entry)\n",
            "invalid_fragment",
            resources={"scripts/tool.py": "# helper\n"},
        )

    def test_control_character_is_rejected(self) -> None:
        self.assert_source_error("`scripts/tool\x00.py`\n", "control_character")

    def test_source_file_exists_but_zip_member_is_absent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plugin_root, skill_root, _ = write_fixture_plugin(
                Path(tmp) / "repository",
                "`scripts/tool.py`\n",
                resources={"scripts/tool.py": "# helper\n"},
            )
            references = source_references(plugin_root)
            payload, archive = zip_from_members(
                [("skills/example-skill/SKILL.md", (skill_root / "SKILL.md").read_bytes())]
            )
            try:
                with self.assertRaises(packaged_resources.ResourceClosureError) as raised:
                    packaged_resources.validate_zip_closure(
                        plugin_root,
                        "fixture-plugin",
                        archive,
                        references=references,
                    )
                self.assertEqual(raised.exception.finding.code, "missing_zip_member")
            finally:
                archive.close()
                payload.close()

    def test_zip_member_under_wrong_path_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plugin_root, skill_root, _ = write_fixture_plugin(
                Path(tmp) / "repository",
                "`scripts/tool.py`\n",
                resources={"scripts/tool.py": "# helper\n"},
            )
            references = source_references(plugin_root)
            payload, archive = zip_from_members(
                [
                    ("skills/example-skill/SKILL.md", (skill_root / "SKILL.md").read_bytes()),
                    ("scripts/tool.py", b"wrong archive path"),
                ]
            )
            try:
                with self.assertRaises(packaged_resources.ResourceClosureError) as raised:
                    packaged_resources.validate_zip_closure(
                        plugin_root,
                        "fixture-plugin",
                        archive,
                        references=references,
                    )
                self.assertEqual(raised.exception.finding.code, "missing_zip_member")
            finally:
                archive.close()
                payload.close()

    def test_zip_member_with_wrong_case_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plugin_root, skill_root, _ = write_fixture_plugin(
                Path(tmp) / "repository",
                "`scripts/tool.py`\n",
                resources={"scripts/tool.py": "# helper\n"},
            )
            references = source_references(plugin_root)
            payload, archive = zip_from_members(
                [
                    ("skills/example-skill/SKILL.md", (skill_root / "SKILL.md").read_bytes()),
                    ("skills/example-skill/scripts/Tool.py", b"wrong case"),
                ]
            )
            try:
                with self.assertRaises(packaged_resources.ResourceClosureError) as raised:
                    packaged_resources.validate_zip_closure(
                        plugin_root,
                        "fixture-plugin",
                        archive,
                        references=references,
                    )
                self.assertEqual(raised.exception.finding.code, "zip_case_mismatch")
            finally:
                archive.close()
                payload.close()

    def test_duplicate_zip_member_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plugin_root, _, _ = write_fixture_plugin(
                Path(tmp) / "repository", "No declarations.\n"
            )
            payload = io.BytesIO()
            with self.assertWarns(UserWarning):
                with zipfile.ZipFile(payload, "w") as writer:
                    writer.writestr("duplicate.txt", b"first")
                    writer.writestr("duplicate.txt", b"second")
            payload.seek(0)
            with zipfile.ZipFile(payload, "r") as archive:
                with self.assertRaises(packaged_resources.ResourceClosureError) as raised:
                    packaged_resources.validate_zip_closure(
                        plugin_root,
                        "fixture-plugin",
                        archive,
                        references=[],
                    )
            self.assertEqual(raised.exception.finding.code, "duplicate_zip_member")

    def test_actual_zip_markdown_declarations_are_parsed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plugin_root, _, _ = write_fixture_plugin(
                Path(tmp) / "repository",
                "No source declaration.\n",
                resources={"scripts/tool.py": "# helper\n"},
            )
            packaged_skill = (
                b"---\nname: example-skill\ndescription: fixture\n---\n\n"
                b"Run `scripts/tool.py`.\n"
            )
            payload, archive = zip_from_members(
                [
                    ("skills/example-skill/SKILL.md", packaged_skill),
                    ("skills/example-skill/scripts/tool.py", b"# helper\n"),
                ]
            )
            try:
                with self.assertRaises(packaged_resources.ResourceClosureError) as raised:
                    packaged_resources.validate_zip_closure(
                        plugin_root,
                        "fixture-plugin",
                        archive,
                    )
                self.assertEqual(raised.exception.finding.code, "zip_declaration_drift")
            finally:
                archive.close()
                payload.close()

    def test_repository_validator_integration_rejects_missing_resource(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repository = Path(tmp) / "repository"
            _, _, plugin = write_fixture_plugin(
                repository, "Run `scripts/missing.py`.\n"
            )
            report = validate_repository.Report()
            original_root = validate_repository.ROOT
            validate_repository.ROOT = repository
            try:
                validate_repository.validate_packaged_resource_closure([plugin], report)
            finally:
                validate_repository.ROOT = original_root
            self.assertTrue(any("scripts/missing.py" in error for error in report.errors))

    def test_package_builder_rejects_missing_declared_resource(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repository = Path(tmp) / "repository"
            _, _, plugin = write_fixture_plugin(
                repository, "Run `scripts/missing.py`.\n"
            )
            output = repository / "dist"
            output.mkdir(parents=True)
            original_root = package_plugins.ROOT
            package_plugins.ROOT = repository
            try:
                with self.assertRaisesRegex(ValueError, "scripts/missing.py"):
                    package_plugins.build_archive(plugin, output)
            finally:
                package_plugins.ROOT = original_root

    def test_package_builder_inspects_actual_zip_for_omitted_member(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repository = Path(tmp) / "repository"
            _, _, plugin = write_fixture_plugin(
                repository,
                "Run `scripts/tool.py`.\n",
                resources={"scripts/tool.py": "# helper\n"},
            )
            output = repository / "dist"
            output.mkdir(parents=True)
            original_root = package_plugins.ROOT
            original_writestr = package_plugins.zipfile.ZipFile.writestr

            def omit_resource(archive, zinfo, data, *args, **kwargs):
                name = zinfo.filename if isinstance(zinfo, zipfile.ZipInfo) else str(zinfo)
                if name == "skills/example-skill/scripts/tool.py":
                    return None
                return original_writestr(archive, zinfo, data, *args, **kwargs)

            package_plugins.ROOT = repository
            try:
                with mock.patch.object(
                    package_plugins.zipfile.ZipFile,
                    "writestr",
                    new=omit_resource,
                ):
                    with self.assertRaisesRegex(ValueError, "missing declared resource"):
                        package_plugins.build_archive(plugin, output)
            finally:
                package_plugins.ROOT = original_root
            self.assertFalse((output / "fixture-plugin-0.0.0.zip").exists())

    def test_file_symlink_resource_is_rejected_where_supported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plugin_root, skill_root, _ = write_fixture_plugin(
                Path(tmp) / "repository", "`scripts/link.py`\n"
            )
            scripts = skill_root / "scripts"
            scripts.mkdir()
            target = scripts / "target.py"
            target.write_text("# target\n", encoding="utf-8")
            link = scripts / "link.py"
            try:
                link.symlink_to(target)
            except (OSError, NotImplementedError) as exc:
                self.skipTest(f"real filesystem file symlinks are unavailable: {exc}")
            with self.assertRaises(packaged_resources.ResourceClosureError) as raised:
                source_references(plugin_root)
            self.assertEqual(raised.exception.finding.code, "linked_resource")

    def test_directory_symlink_component_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            plugin_root, skill_root, _ = write_fixture_plugin(
                base / "repository", "`scripts/tool.py`\n"
            )
            outside = base / "outside"
            outside.mkdir()
            (outside / "tool.py").write_text("# outside\n", encoding="utf-8")
            link = skill_root / "scripts"
            try:
                link.symlink_to(outside, target_is_directory=True)
            except (OSError, NotImplementedError) as exc:
                self.skipTest(f"real filesystem directory symlinks are unavailable: {exc}")
            with self.assertRaises(packaged_resources.ResourceClosureError) as raised:
                source_references(plugin_root)
            self.assertEqual(raised.exception.finding.code, "linked_resource")

    @unittest.skipUnless(os.name == "nt", "real Windows directory junctions require Windows")
    def test_real_windows_junction_resource_component_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            plugin_root, skill_root, _ = write_fixture_plugin(
                base / "repository", "`scripts/tool.py`\n"
            )
            outside = base / "outside"
            outside.mkdir()
            (outside / "tool.py").write_text("# harmless outside fixture\n", encoding="utf-8")
            junction = skill_root / "scripts"
            result = subprocess.run(
                ["cmd.exe", "/d", "/c", "mklink", "/J", str(junction), str(outside)],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode != 0:
                self.fail(
                    "failed to create a real Windows directory junction: "
                    + result.stdout
                    + result.stderr
                )
            try:
                self.assertFalse(junction.is_symlink())
                self.assertTrue(packaged_resources.is_reparse_point(junction.lstat()))
                with self.assertRaises(packaged_resources.ResourceClosureError) as raised:
                    source_references(plugin_root)
                self.assertEqual(raised.exception.finding.code, "reparse_resource")
            finally:
                if junction.exists():
                    os.rmdir(junction)

    @unittest.skipUnless(hasattr(os, "mkfifo"), "real FIFO fixtures require os.mkfifo")
    def test_unsupported_special_resource_file_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plugin_root, skill_root, _ = write_fixture_plugin(
                Path(tmp) / "repository", "`scripts/pipe`\n"
            )
            scripts = skill_root / "scripts"
            scripts.mkdir()
            pipe = scripts / "pipe"
            os.mkfifo(pipe)
            with self.assertRaises(packaged_resources.ResourceClosureError) as raised:
                source_references(plugin_root)
            self.assertEqual(raised.exception.finding.code, "not_regular_file")

    def test_all_existing_plugin_trees_and_built_zips_pass_closure(self) -> None:
        catalog = json.loads((ROOT / "catalog/plugins.json").read_text(encoding="utf-8"))
        inventory = packaged_resources.inventory_plugins(ROOT, catalog["plugins"])
        self.assertEqual(len(inventory), 5)
        self.assertEqual(sum(len(items) for items in inventory.values()), 6)
        self.assertEqual(
            {
                kind: sum(
                    item.resource_type == kind
                    for items in inventory.values()
                    for item in items
                )
                for kind in packaged_resources.RESOURCE_KINDS
            },
            {"scripts": 1, "references": 4, "assets": 1},
        )

        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            for plugin in catalog["plugins"]:
                archive_path, digest = package_plugins.build_archive(plugin, output)
                self.assertEqual(digest, EXPECTED_DIGESTS[plugin["name"]])
                plugin_root = ROOT / plugin["path"]
                with zipfile.ZipFile(archive_path) as archive:
                    validated = packaged_resources.validate_zip_closure(
                        plugin_root,
                        plugin["name"],
                        archive,
                    )
                self.assertEqual(validated, inventory[plugin["name"]])

    def test_h02_packaged_evidence_helper_remains_required(self) -> None:
        catalog = json.loads((ROOT / "catalog/plugins.json").read_text(encoding="utf-8"))
        inventory = packaged_resources.inventory_plugins(ROOT, catalog["plugins"])
        core = inventory["engineering-foundation-core"]
        matches = [
            item
            for item in core
            if item.zip_member
            == "skills/verify-before-completion/scripts/evidence_gate.py"
        ]
        self.assertEqual(len(matches), 1)
        self.assertTrue(
            (
                ROOT
                / "plugins/engineering-foundation-core"
                / matches[0].zip_member
            ).is_file()
        )


if __name__ == "__main__":
    unittest.main()
