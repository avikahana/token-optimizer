#!/usr/bin/env python3
"""Sync the root plugin files into the marketplace mirror package.

The marketplace copy under marketplace/plugins/token-optimizer must stay
byte-identical to the root files (enforced by
tests/test_plugin_manifest.py::test_repo_local_marketplace_package_matches_root_plugin_files).
Run this after editing any mirrored file instead of copying by hand.
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

MIRROR_ROOT = Path("marketplace/plugins/token-optimizer")

# Keep in sync with `mirrored_files` in tests/test_plugin_manifest.py.
MIRRORED_FILES = (
    ".codex-plugin/plugin.json",
    ".mcp.json",
    "mcp/server.mjs",
    "mcp/hook-control-widget.html",
    "mcp/context-gauges-widget.html",
    "skills/token-optimizer/SKILL.md",
    "assets/icon.png",
    "assets/logo.png",
    "assets/logo-dark.png",
    "assets/screenshot-dashboard.png",
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="report drift without writing; exit 1 if any mirror differs",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    drifted: list[str] = []
    for relative_path in MIRRORED_FILES:
        source = repo_root / relative_path
        target = repo_root / MIRROR_ROOT / relative_path
        if not source.is_file():
            print(f"missing source file: {relative_path}", file=sys.stderr)
            return 2
        if target.is_file() and target.read_bytes() == source.read_bytes():
            continue
        drifted.append(relative_path)
        if not args.check:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)

    if not drifted:
        print("mirrors in sync")
        return 0
    verb = "out of sync" if args.check else "synced"
    for relative_path in drifted:
        print(f"{verb}: {relative_path}")
    return 1 if args.check else 0


if __name__ == "__main__":
    raise SystemExit(main())
