from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAME_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$")


def frontmatter(path: Path) -> dict[str, str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    end = lines.index("---", 1)
    data: dict[str, str] = {}
    for line in lines[1:end]:
        if line.startswith("  ") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        if value.strip():
            data[key.strip()] = value.strip().strip('"')
    return data


class SkillTests(unittest.TestCase):
    def test_skill_names_and_descriptions(self) -> None:
        paths = list(ROOT.glob("plugins/*/skills/*/SKILL.md"))
        self.assertGreaterEqual(len(paths), 10)
        for path in paths:
            data = frontmatter(path)
            name = path.parent.name
            self.assertEqual(data.get("name"), name, path)
            self.assertRegex(name, NAME_RE, path)
            description = data.get("description", "")
            self.assertIn("Use ", description, path)
            self.assertIn("Do not ", description, path)
            self.assertLessEqual(len(description), 1024, path)

    def test_skill_bodies_are_compact(self) -> None:
        for path in ROOT.glob("plugins/*/skills/*/SKILL.md"):
            self.assertLessEqual(len(path.read_text(encoding="utf-8").splitlines()), 500, path)

    def test_no_portable_allowed_tools(self) -> None:
        for path in ROOT.glob("plugins/*/skills/*/SKILL.md"):
            self.assertNotIn("allowed-tools:", path.read_text(encoding="utf-8"), path)


if __name__ == "__main__":
    unittest.main()
