"""Smoke tests for agent-ux plugin.

Validates structural integrity without executing any plugin logic:
  - plugin.json schema (required fields, non-empty values, semver)
  - marketplace.json schema (when present)
  - Declared agent files exist on disk
  - Required top-level files present (LICENSE, README.md, INTEROP.md)
  - Reference files present (ux-conventions.md)
"""
import json
import os
import re
import unittest

PLUGIN_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLUGIN_JSON = os.path.join(PLUGIN_ROOT, ".claude-plugin", "plugin.json")
MARKETPLACE_JSON = os.path.join(PLUGIN_ROOT, ".claude-plugin", "marketplace.json")

SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")


def _load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


class TestPluginJsonSchema(unittest.TestCase):
    """plugin.json must be valid JSON with all required fields populated."""

    def setUp(self):
        self.data = _load_json(PLUGIN_JSON)

    def test_is_valid_json(self):
        self.assertIsInstance(self.data, dict)

    def test_name_present_and_non_empty(self):
        self.assertIn("name", self.data)
        self.assertIsInstance(self.data["name"], str)
        self.assertTrue(self.data["name"].strip(), "name must not be blank")

    def test_version_present_and_semver(self):
        self.assertIn("version", self.data)
        v = self.data["version"]
        self.assertRegex(v, SEMVER_RE,
                         f"version must be semver (X.Y.Z); got {v!r}")

    def test_description_present_and_non_empty(self):
        self.assertIn("description", self.data)
        self.assertTrue(self.data["description"].strip(),
                        "description must not be blank")

    def test_author_name_present(self):
        self.assertIn("author", self.data)
        self.assertIn("name", self.data["author"],
                      "author.name must be present")
        self.assertTrue(self.data["author"]["name"].strip(),
                        "author.name must not be blank")

    def test_license_field_present(self):
        self.assertIn("license", self.data)
        self.assertTrue(self.data["license"].strip(),
                        "license field must not be blank")

    def test_name_matches_directory(self):
        """Plugin name must match the directory name (kebab-case convention)."""
        dir_name = os.path.basename(PLUGIN_ROOT)
        self.assertEqual(self.data["name"], dir_name,
                         f"plugin.json name {self.data['name']!r} must match "
                         f"directory {dir_name!r}")


class TestMarketplaceJsonSchema(unittest.TestCase):
    """marketplace.json (when present) must be valid JSON with required fields."""

    def setUp(self):
        if not os.path.exists(MARKETPLACE_JSON):
            self.skipTest("marketplace.json not present")
        self.data = _load_json(MARKETPLACE_JSON)

    def test_is_valid_json(self):
        self.assertIsInstance(self.data, dict)

    def test_name_present(self):
        self.assertIn("name", self.data)
        self.assertTrue(self.data["name"].strip())

    def test_plugins_list_present(self):
        self.assertIn("plugins", self.data)
        self.assertIsInstance(self.data["plugins"], list)
        self.assertGreater(len(self.data["plugins"]), 0,
                           "plugins list must have at least one entry")

    def test_each_plugin_entry_has_name_and_source(self):
        for entry in self.data["plugins"]:
            self.assertIn("name", entry, f"plugin entry missing name: {entry}")
            self.assertIn("source", entry, f"plugin entry missing source: {entry}")


class TestAgentFilesExist(unittest.TestCase):
    """Every agent declared in agents/ must have a corresponding .md file."""

    def test_agents_directory_exists(self):
        agents_dir = os.path.join(PLUGIN_ROOT, "agents")
        self.assertTrue(os.path.isdir(agents_dir),
                        "agents/ directory must exist")

    def test_ux_agent_skill_file_present(self):
        skill_path = os.path.join(PLUGIN_ROOT, "agents", "ux-agent.md")
        self.assertTrue(os.path.isfile(skill_path),
                        f"agents/ux-agent.md must exist at {skill_path}")

    def test_ux_agent_skill_file_non_empty(self):
        skill_path = os.path.join(PLUGIN_ROOT, "agents", "ux-agent.md")
        self.assertGreater(os.path.getsize(skill_path), 0,
                           "agents/ux-agent.md must not be empty")

    def test_no_dangling_agent_md_files(self):
        """Every .md file in agents/ should be a real skill document (has content)."""
        agents_dir = os.path.join(PLUGIN_ROOT, "agents")
        for fname in os.listdir(agents_dir):
            if fname.endswith(".md"):
                fpath = os.path.join(agents_dir, fname)
                self.assertGreater(os.path.getsize(fpath), 0,
                                   f"agents/{fname} is empty — likely a stub")


class TestRequiredTopLevelFiles(unittest.TestCase):
    """Plugin root must contain LICENSE, README.md, and INTEROP.md."""

    def _assert_file(self, rel_path):
        full = os.path.join(PLUGIN_ROOT, rel_path)
        self.assertTrue(os.path.isfile(full),
                        f"{rel_path} must exist in plugin root")
        self.assertGreater(os.path.getsize(full), 0,
                           f"{rel_path} must not be empty")

    def test_license_exists(self):
        self._assert_file("LICENSE")

    def test_readme_exists(self):
        self._assert_file("README.md")

    def test_interop_md_exists(self):
        self._assert_file("INTEROP.md")


class TestReferenceFilesPresent(unittest.TestCase):
    """references/ directory must contain the UX conventions document."""

    def test_references_directory_exists(self):
        refs_dir = os.path.join(PLUGIN_ROOT, "references")
        self.assertTrue(os.path.isdir(refs_dir),
                        "references/ directory must exist")

    def test_ux_conventions_present(self):
        f = os.path.join(PLUGIN_ROOT, "references", "ux-conventions.md")
        self.assertTrue(os.path.isfile(f),
                        "references/ux-conventions.md must exist")
        self.assertGreater(os.path.getsize(f), 0,
                           "references/ux-conventions.md must not be empty")

    def test_example_envelopes_directory_present(self):
        env_dir = os.path.join(PLUGIN_ROOT, "references", "example-envelopes")
        self.assertTrue(os.path.isdir(env_dir),
                        "references/example-envelopes/ must exist")

    def test_example_envelopes_non_empty(self):
        env_dir = os.path.join(PLUGIN_ROOT, "references", "example-envelopes")
        md_files = [f for f in os.listdir(env_dir) if f.endswith(".md")]
        self.assertGreater(len(md_files), 0,
                           "references/example-envelopes/ must contain at least one .md file")


if __name__ == "__main__":
    unittest.main()
