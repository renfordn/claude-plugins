"""Tests for scripts/bump_version.py: moves CHANGELOG.md's Unreleased section
under a new version heading and updates plugin.json's version to match, so
the two files stay in the sync test_version_sync.py checks for.
"""

import importlib.util
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "scripts" / "bump_version.py"


def _load_bump_version_module():
    spec = importlib.util.spec_from_file_location("bump_version", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestBumpVersion(unittest.TestCase):
    def setUp(self):
        self.module = _load_bump_version_module()
        self.tmpdir = TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)

        tmp_root = Path(self.tmpdir.name)
        (tmp_root / ".claude-plugin").mkdir()
        self.changelog_path = tmp_root / "CHANGELOG.md"
        self.plugin_json_path = tmp_root / ".claude-plugin" / "plugin.json"

        self.module.CHANGELOG_PATH = self.changelog_path
        self.module.PLUGIN_JSON_PATH = self.plugin_json_path

    def _write(self, changelog_text, version="0.1.1"):
        self.changelog_path.write_text(changelog_text, encoding="utf-8")
        self.plugin_json_path.write_text(
            json.dumps({"name": "agent-tdd", "version": version}, indent=2) + "\n",
            encoding="utf-8",
        )

    def test_moves_unreleased_entries_under_new_heading(self):
        self._write(
            "# Changelog\n\n"
            "## [Unreleased]\n\n"
            "- Added a new thing.\n\n"
            "## [0.1.1] - 2026-08-11\n\n"
            "- Old entry.\n"
        )

        self.module.bump("0.2.0", "2026-08-12")

        text = self.changelog_path.read_text(encoding="utf-8")
        self.assertIn("## [Unreleased]", text)
        self.assertIn("## [0.2.0] - 2026-08-12", text)
        self.assertIn("- Added a new thing.", text)
        # Unreleased section itself is now empty.
        unreleased_start = text.index("## [Unreleased]")
        new_heading_start = text.index("## [0.2.0]")
        between = text[unreleased_start:new_heading_start]
        self.assertNotIn("Added a new thing", between)

    def test_updates_plugin_json_version(self):
        self._write(
            "## [Unreleased]\n\n- Something.\n\n## [0.1.1] - 2026-08-11\n\n- Old.\n"
        )

        self.module.bump("0.2.0", "2026-08-12")

        plugin_data = json.loads(self.plugin_json_path.read_text(encoding="utf-8"))
        self.assertEqual(plugin_data["version"], "0.2.0")

    def test_raises_when_unreleased_section_is_empty(self):
        self._write("## [Unreleased]\n\n## [0.1.1] - 2026-08-11\n\n- Old.\n")

        with self.assertRaises(ValueError):
            self.module.bump("0.2.0", "2026-08-12")

    def test_raises_when_unreleased_heading_missing(self):
        self._write("## [0.1.1] - 2026-08-11\n\n- Old.\n")

        with self.assertRaises(ValueError):
            self.module.bump("0.2.0", "2026-08-12")

    def test_rejects_non_semver_version(self):
        self._write("## [Unreleased]\n\n- Something.\n")

        with self.assertRaises(ValueError):
            self.module.bump("not-a-version", "2026-08-12")


if __name__ == "__main__":
    unittest.main()
