#!/usr/bin/env python3
"""Select the exact release-candidate subject used by CI after publication."""

from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path
from typing import NamedTuple, Sequence


PACKAGE_IDENTITY_PATHS = (
    "plugins",
    "catalog/plugins.json",
    ".agents/plugins/marketplace.json",
    ".claude-plugin/marketplace.json",
)


class SubjectError(RuntimeError):
    """Raised when CI cannot select an exact candidate without identity drift."""


class SubjectSelection(NamedTuple):
    commit: str
    reason: str


def run_git(
    repository: Path,
    *args: str,
    expected: Sequence[int] = (0,),
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", *args],
        cwd=repository,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode not in expected:
        detail = result.stderr.strip() or result.stdout.strip()
        raise SubjectError(
            f"git {' '.join(args)} returned {result.returncode}"
            f"{': ' + detail if detail else ''}"
        )
    return result


def select_candidate_subject(
    repository: Path,
    intended_tag: str,
    current_commit: str,
) -> SubjectSelection:
    repository = repository.resolve(strict=True)
    head = run_git(repository, "rev-parse", current_commit).stdout.strip()
    tag_ref = f"refs/tags/{intended_tag}"
    tag_exists = run_git(
        repository,
        "show-ref",
        "--verify",
        "--quiet",
        tag_ref,
        expected=(0, 1),
    )
    if tag_exists.returncode == 1:
        return SubjectSelection(head, "unreleased-candidate")

    tag_result = run_git(
        repository,
        "rev-parse",
        "--verify",
        f"{tag_ref}^{{commit}}",
    )

    tag_commit = tag_result.stdout.strip()
    if tag_commit == head:
        return SubjectSelection(head, "current-tag-target")

    ancestry = run_git(
        repository,
        "merge-base",
        "--is-ancestor",
        tag_commit,
        head,
        expected=(0, 1),
    )
    if ancestry.returncode != 0:
        raise SubjectError(
            f"published tag {intended_tag} is not an ancestor of current commit {head}"
        )

    identity_diff = run_git(
        repository,
        "diff",
        "--quiet",
        tag_commit,
        head,
        "--",
        *PACKAGE_IDENTITY_PATHS,
        expected=(0, 1),
    )
    if identity_diff.returncode != 0:
        raise SubjectError(
            "package identity inputs changed after the published tag; "
            "advance the release identity before exact-candidate CI can continue"
        )
    return SubjectSelection(tag_commit, "published-package-identity")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    parser.add_argument("--tag", required=True)
    parser.add_argument("--current", default="HEAD")
    parser.add_argument(
        "--github-output",
        type=Path,
        default=(Path(os.environ["GITHUB_OUTPUT"]) if os.environ.get("GITHUB_OUTPUT") else None),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        selection = select_candidate_subject(args.repository, args.tag, args.current)
        if args.github_output is not None:
            with args.github_output.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(f"commit={selection.commit}\n")
                handle.write(f"reason={selection.reason}\n")
        print(f"candidate subject: {selection.commit} ({selection.reason})")
        return 0
    except SubjectError as error:
        print(f"ERROR: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
