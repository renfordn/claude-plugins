#!/usr/bin/env python3
"""Bump the plugin's version in lockstep across .claude-plugin/plugin.json and
CHANGELOG.md.

Moves the current '## [Unreleased]' entries under a new '## [X.Y.Z] - DATE'
heading and updates plugin.json's "version" field to match, so the two files
can never drift the way test_version_sync.py checks for.

Usage:
    python3 scripts/bump_version.py <new_version> [--date YYYY-MM-DD]
"""

import argparse
import datetime
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CHANGELOG_PATH = REPO_ROOT / "CHANGELOG.md"
PLUGIN_JSON_PATH = REPO_ROOT / ".claude-plugin" / "plugin.json"

UNRELEASED_HEADING = "## [Unreleased]"
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")
NEXT_HEADING_RE = re.compile(r"^## \[")


def bump(new_version, release_date):
    if not SEMVER_RE.match(new_version):
        raise ValueError(f"'{new_version}' is not a plain X.Y.Z semver string")

    changelog_lines = CHANGELOG_PATH.read_text(encoding="utf-8").splitlines(
        keepends=True
    )

    try:
        unreleased_idx = next(
            i
            for i, line in enumerate(changelog_lines)
            if line.strip() == UNRELEASED_HEADING
        )
    except StopIteration:
        raise ValueError(f"No '{UNRELEASED_HEADING}' heading found in CHANGELOG.md")

    # Find the extent of the Unreleased section: everything up to (not
    # including) the next '## [' heading, or end of file.
    next_heading_idx = len(changelog_lines)
    for i in range(unreleased_idx + 1, len(changelog_lines)):
        if NEXT_HEADING_RE.match(changelog_lines[i]):
            next_heading_idx = i
            break

    unreleased_body = changelog_lines[unreleased_idx + 1 : next_heading_idx]
    if not any(line.strip() for line in unreleased_body):
        raise ValueError(
            "'## [Unreleased]' section is empty — nothing to release. Add "
            "entries under it before bumping the version."
        )

    new_heading = f"## [{new_version}] - {release_date}\n"
    new_lines = (
        changelog_lines[: unreleased_idx + 1]
        + ["\n", new_heading]
        + unreleased_body
        + changelog_lines[next_heading_idx:]
    )
    CHANGELOG_PATH.write_text("".join(new_lines), encoding="utf-8")

    plugin_data = json.loads(PLUGIN_JSON_PATH.read_text(encoding="utf-8"))
    plugin_data["version"] = new_version
    PLUGIN_JSON_PATH.write_text(
        json.dumps(plugin_data, indent=2) + "\n", encoding="utf-8"
    )

    return new_version, release_date


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("new_version", help="New semver, e.g. 0.2.0")
    parser.add_argument(
        "--date",
        default=None,
        help="Release date (YYYY-MM-DD). Defaults to today.",
    )
    args = parser.parse_args(argv)

    release_date = args.date or datetime.date.today().isoformat()
    version, date = bump(args.new_version, release_date)
    print(f"Bumped to {version} ({date}) in plugin.json and CHANGELOG.md")


if __name__ == "__main__":
    try:
        main()
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)
