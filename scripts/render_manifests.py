#!/usr/bin/env python3
"""Render portable, Codex, Claude, and marketplace manifests from one catalog."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "catalog" / "plugins.json"
PORTABLE_SCHEMA = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
CLAUDE_PLUGIN_SCHEMA = "https://json.schemastore.org/claude-code-plugin-manifest.json"
CLAUDE_MARKETPLACE_SCHEMA = "https://json.schemastore.org/claude-code-marketplace.json"


def dumps(data: object) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def common(plugin: dict, marketplace: dict) -> dict:
    return {
        "name": plugin["name"],
        "version": plugin["version"],
        "description": plugin["description"],
        "author": {"name": marketplace["owner_name"], "url": marketplace["owner_url"]},
        "homepage": marketplace["homepage"],
        "repository": marketplace["repository"],
        "license": "MIT",
        "keywords": plugin["keywords"],
    }


def targets(catalog: dict) -> dict[Path, str]:
    outputs: dict[Path, str] = {}
    market = catalog["marketplace"]
    for plugin in catalog["plugins"]:
        root = ROOT / plugin["path"]
        shared = common(plugin, market)
        outputs[root / "plugin.json"] = dumps({
            "$schema": PORTABLE_SCHEMA,
            **shared,
            "extensions": {
                "com.openai.codex": {"manifest": "./.codex-plugin/plugin.json"},
                "com.anthropic.claude-code": {"manifest": "./.claude-plugin/plugin.json"},
            },
        })
        outputs[root / ".codex-plugin" / "plugin.json"] = dumps({
            **shared,
            "skills": "./skills/",
            "interface": {
                "displayName": plugin["display_name"],
                "shortDescription": plugin["short_description"],
                "longDescription": plugin["description"],
                "developerName": market["owner_name"],
                "category": plugin["category"],
                "capabilities": plugin["capabilities"],
                "websiteURL": market["homepage"],
                "privacyPolicyURL": market["privacy_policy_url"],
                "termsOfServiceURL": market["terms_of_service_url"],
                "defaultPrompt": plugin["default_prompts"],
                "brandColor": plugin["brand_color"],
                "screenshots": [],
            },
        })
        outputs[root / ".claude-plugin" / "plugin.json"] = dumps({
            "$schema": CLAUDE_PLUGIN_SCHEMA,
            "displayName": plugin["display_name"],
            **shared,
        })

    outputs[ROOT / ".agents" / "plugins" / "marketplace.json"] = dumps({
        "name": market["name"],
        "interface": {"displayName": market["display_name"]},
        "plugins": [
            {
                "name": p["name"],
                "source": {"source": "local", "path": f"./{p['path']}"},
                "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
                "category": p["category"],
            }
            for p in catalog["plugins"]
        ],
    })
    outputs[ROOT / ".claude-plugin" / "marketplace.json"] = dumps({
        "$schema": CLAUDE_MARKETPLACE_SCHEMA,
        "name": market["name"],
        "version": "1.0.0",
        "description": market["description"],
        "owner": {"name": market["owner_name"], "url": market["owner_url"]},
        "plugins": [
            {
                "name": p["name"],
                "description": p["description"],
                "version": p["version"],
                "author": {"name": market["owner_name"], "url": market["owner_url"]},
                "source": f"./{p['path']}",
                "category": p["claude_category"],
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
    print("manifest drift check: PASS" if args.check else "manifest rendering: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
