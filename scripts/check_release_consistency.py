#!/usr/bin/env python3
"""Checks release version consistency between README and docs/ROADMAP.

Rule enforced:
- Every semantic release tag listed in README tables (vX.Y or vX.Y.Z) must
  also appear in docs/ROADMAP.md.

This is intentionally one-way to avoid blocking on roadmap-only future plans.
"""

from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
ROADMAP = ROOT / "docs" / "ROADMAP.md"
TAG_RE = re.compile(r"\bv\d+\.\d+(?:\.\d+)?\b")


def extract_tags(path: pathlib.Path) -> set[str]:
    text = path.read_text(encoding="utf-8")
    tags = set(TAG_RE.findall(text))
    return tags


def main() -> int:
    if not README.exists() or not ROADMAP.exists():
        print("ERROR: Missing README.md or docs/ROADMAP.md")
        return 2

    readme_tags = extract_tags(README)
    roadmap_tags = extract_tags(ROADMAP)

    missing = sorted(readme_tags - roadmap_tags)

    if missing:
        print("Release consistency check failed.")
        print("Tags present in README.md but missing from docs/ROADMAP.md:")
        for tag in missing:
            print(f"  - {tag}")
        print("\nAction: update docs/ROADMAP.md to include these published versions.")
        return 1

    print("Release consistency check passed.")
    print(f"README tags: {len(readme_tags)} | ROADMAP tags: {len(roadmap_tags)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
