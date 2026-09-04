"""Tests that .claude-plugin/plugin.json's version stays in sync with
CHANGELOG.md's latest real (non-[Unreleased]) version heading.
"""

import json
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CHANGELOG_PATH = REPO_ROOT / "CHANGELOG.md"
PLUGIN_JSON_PATH = REPO_ROOT / ".claude-plugin" / "plugin.json"

VERSION_HEADING_RE = re.compile(r"^## \[(\d+\.\d+\.\d+)\]")


def find_latest_changelog_version():
    """Return the first semver found in a '## [X.Y.Z]' heading in
    CHANGELOG.md, skipping '## [Unreleased]' and any other non-semver
    bracket heading. Returns None if no such heading exists.
    """
    with open(CHANGELOG_PATH, encoding="utf-8") as f:
        for line in f:
            match = VERSION_HEADING_RE.match(line)
            if match:
                return match.group(1)
    return None


class TestVersionSync(unittest.TestCase):
    def test_changelog_has_a_version_heading(self):
        version = find_latest_changelog_version()
        self.assertIsNotNone(
            version,
            "No '## [X.Y.Z]' version heading found in CHANGELOG.md "
            "(only '## [Unreleased]' or no headings present).",
        )

    def test_plugin_json_version_matches_changelog(self):
        changelog_version = find_latest_changelog_version()
        with open(PLUGIN_JSON_PATH, encoding="utf-8") as f:
            plugin_data = json.load(f)
        plugin_version = plugin_data["version"]

        self.assertEqual(
            plugin_version,
            changelog_version,
            f"plugin.json version {plugin_version} does not match "
            f"CHANGELOG.md version {changelog_version}",
        )


if __name__ == "__main__":
    unittest.main()
