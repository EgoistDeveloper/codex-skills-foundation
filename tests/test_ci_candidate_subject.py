from __future__ import annotations

import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "ci_candidate_subject.py"


def load_module():
    spec = importlib.util.spec_from_file_location("ci_candidate_subject", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load CI candidate-subject helper")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CandidateSubjectTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.repository = Path(self.temporary.name) / "repository"
        self.repository.mkdir()
        self.git("init", "-b", "main")
        self.git("config", "user.name", "CI Test")
        self.git("config", "user.email", "ci@example.invalid")
        self.write("README.md", "release docs\n")
        self.write("plugins/core/plugin.json", "{}\n")
        self.write("catalog/plugins.json", "{}\n")
        self.write(".agents/plugins/marketplace.json", "{}\n")
        self.write(".claude-plugin/marketplace.json", "{}\n")
        self.commit("release")
        self.release_commit = self.head()
        self.git("tag", "v0.3.0-beta.2")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def git(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args],
            cwd=self.repository,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def write(self, relative: str, content: str) -> None:
        path = self.repository / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def commit(self, message: str) -> None:
        self.git("add", "-A")
        self.git("commit", "-m", message)

    def head(self) -> str:
        return self.git("rev-parse", "HEAD").stdout.strip()

    def test_published_tag_is_selected_after_documentation_only_change(self) -> None:
        module = load_module()
        self.write("README.md", "published beta.2 docs\n")
        self.commit("docs")

        selection = module.select_candidate_subject(
            self.repository, "v0.3.0-beta.2", self.head()
        )

        self.assertEqual(selection.commit, self.release_commit)
        self.assertEqual(selection.reason, "published-package-identity")

    def test_package_identity_change_fails_closed_under_published_tag(self) -> None:
        module = load_module()
        self.write("plugins/core/plugin.json", '{"changed":true}\n')
        self.commit("change package")

        with self.assertRaisesRegex(module.SubjectError, "package identity inputs changed"):
            module.select_candidate_subject(
                self.repository, "v0.3.0-beta.2", self.head()
            )

    def test_current_tag_target_is_selected_directly(self) -> None:
        module = load_module()

        selection = module.select_candidate_subject(
            self.repository, "v0.3.0-beta.2", self.head()
        )

        self.assertEqual(selection.commit, self.release_commit)
        self.assertEqual(selection.reason, "current-tag-target")

    def test_absent_tag_keeps_the_current_unreleased_candidate(self) -> None:
        module = load_module()
        self.git("tag", "-d", "v0.3.0-beta.2")
        self.write("README.md", "future candidate\n")
        self.commit("future")

        selection = module.select_candidate_subject(
            self.repository, "v0.3.0-beta.2", self.head()
        )

        self.assertEqual(selection.commit, self.head())
        self.assertEqual(selection.reason, "unreleased-candidate")

    def test_present_tag_that_cannot_peel_to_a_commit_fails_closed(self) -> None:
        module = load_module()
        self.git("tag", "-d", "v0.3.0-beta.2")
        blob_path = self.repository / "tag-blob.txt"
        blob_path.write_text("not a commit\n", encoding="utf-8")
        blob = self.git("hash-object", "-w", str(blob_path)).stdout.strip()
        self.git("update-ref", "refs/tags/v0.3.0-beta.2", blob)

        with self.assertRaisesRegex(module.SubjectError, "returned 128"):
            module.select_candidate_subject(
                self.repository, "v0.3.0-beta.2", self.head()
            )

    def test_non_package_tooling_change_reuses_the_published_subject(self) -> None:
        module = load_module()
        self.write("scripts/tool.py", "print('checked')\n")
        self.commit("tooling")

        selection = module.select_candidate_subject(
            self.repository, "v0.3.0-beta.2", self.head()
        )

        self.assertEqual(selection.commit, self.release_commit)
        self.assertEqual(selection.reason, "published-package-identity")

    def test_workflow_selects_subject_before_both_candidate_consumers(self) -> None:
        workflow = (ROOT / ".github/workflows/validate.yml").read_text(encoding="utf-8")

        self.assertEqual(workflow.count("id: candidate-subject"), 2)
        self.assertEqual(
            workflow.count("python scripts/ci_candidate_subject.py --tag v0.3.0-beta.2"),
            2,
        )
        self.assertEqual(
            workflow.count(
                "git switch -c h04-ci-package-subject "
                "${{ steps.candidate-subject.outputs.commit }}"
            ),
            2,
        )


if __name__ == "__main__":
    unittest.main()
