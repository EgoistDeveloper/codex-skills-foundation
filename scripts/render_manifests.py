#!/usr/bin/env python3
"""Render portable, Codex, Claude, and marketplace manifests from one catalog."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "catalog" / "plugins.json"
REPOSITORY = "https://github.com/EgoistDeveloper/codex-skills-foundation"
PORTABLE_SCHEMA = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"


def dumps(data: object) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def targets(catalog: dict) -> dict[Path, str]:
    outputs: dict[Path, str] = {}
    for plugin in catalog["plugins"]:
        root = ROOT / plugin["path"]
        common = {
            "name": plugin["name"],
            "version": plugin["version"],
            "description": plugin["description"],
            "author": {
                "name": "EgoistDeveloper",
                "url": catalog["marketplace"]["owner_url"],
            },
            "repository": REPOSITORY,
            "license": "MIT",
            "keywords": plugin["keywords"],
        }
        outputs[root / "plugin.json"] = dumps({"$schema": PORTABLE_SCHEMA, **common})
        outputs[root / ".codex-plugin" / "plugin.json"] = dumps({
            **common,
            "skills": "./skills/",
            "interface": {
                "displayName": plugin["display_name"],
                "shortDescription": plugin["short_description"],
                "longDescription": plugin["description"],
                "developerName": catalog["marketplace"]["owner_name"],
                "category": plugin["category"],
                "defaultPrompt": [plugin["default_prompt"]],
            },
        })
        outputs[root / ".claude-plugin" / "plugin.json"] = dumps({
            "$schema": "https://json.schemastore.org/claude-code-plugin-manifest.json",
            "displayName": plugin["display_name"],
            **common,
        })

    outputs[ROOT / ".agents" / "plugins" / "marketplace.json"] = dumps({
        "name": catalog["marketplace"]["name"],
        "interface": {"displayName": catalog["marketplace"]["display_name"]},
        "plugins": [
            {
                "name": p["name"],
                "source": {"source": "local", "path": f"./{p['path']}"},
                "policy": {
                    "installation": "AVAILABLE",
                    "authentication": "ON_INSTALL",
                },
                "category": p["category"],
            }
            for p in catalog["plugins"]
        ],
    })
    outputs[ROOT / ".claude-plugin" / "marketplace.json"] = dumps({
        "$schema": "https://json.schemastore.org/claude-code-marketplace.json",
        "name": catalog["marketplace"]["name"],
        "version": "1.0.0",
        "description": catalog["marketplace"]["description"],
        "owner": {
            "name": catalog["marketplace"]["owner_name"],
            "url": catalog["marketplace"]["owner_url"],
        },
        "plugins": [
            {
                "name": p["name"],
                "description": p["description"],
                "version": p["version"],
                "author": {
                    "name": "EgoistDeveloper",
                    "url": catalog["marketplace"]["owner_url"],
                },
                "source": f"./{p['path']}",
                "category": "development" if p["category"] == "Developer Tools" else "productivity",
            }
            for p in catalog["plugins"]
        ],
    })
    return outputs


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="Fail when generated files differ.")
    args = parser.parse_args()
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    drift: list[str] = []
    for path, expected in targets(catalog).items():
        if args.check:
            actual = path.read_text(encoding="utf-8") if path.exists() else None
            if actual != expected:
                drift.append(str(path.relative_to(ROOT)))
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(expected, encoding="utf-8")
    if drift:
        print("Generated manifest drift:")
        for item in drift:
            print(f"- {item}")
        print("Run: python scripts/render_manifests.py")
        return 1
    print("manifest rendering: PASS" if not args.check else "manifest drift check: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
