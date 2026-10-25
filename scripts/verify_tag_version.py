#!/usr/bin/env python3
"""Fail CI if git tag version does not match pyproject.toml [project].version."""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

def main() -> int:
    ref = os.environ.get("GITHUB_REF", "")
    match = re.match(r"refs/tags/v(.+)$", ref)
    if not match:
        print(f"Not a version tag ref: {ref!r}", file=sys.stderr)
        return 1
    tag_version = match.group(1)

    root = Path(__file__).resolve().parents[1]
    text = (root / "pyproject.toml").read_text(encoding="utf-8")
    version_match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    if not version_match:
        print("Could not parse version from pyproject.toml", file=sys.stderr)
        return 1
    project_version = version_match.group(1)
    if tag_version != project_version:
        print(
            f"Tag v{tag_version} does not match pyproject.toml version {project_version}",
            file=sys.stderr,
        )
        return 1
    print(f"Version OK: {project_version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
