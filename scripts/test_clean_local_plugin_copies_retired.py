"""Tests for the --retired-skills mode of scripts/clean_local_plugin_copies.py (temp HOME only)."""
import io
import json
import os
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout

from clean_local_plugin_copies import find_copies, main


def _write(path, text="x"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(text)


class RetiredSkillsTests(unittest.TestCase):
    def setUp(self):
        base = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, base)
        self.repo = os.path.join(base, "repo")
        self.home = os.path.join(base, "home")
        _write(os.path.join(self.repo, "code-reviewer", ".claude-plugin", "plugin.json"), "{}")
        _write(os.path.join(self.repo, "code-reviewer", "skills", "feature-finder", "SKILL.md"), "new")
        self.skill = os.path.join(self.home, "skills", "feature-finder")
        _write(os.path.join(self.skill, "SKILL.md"), "old differing content")
        self.synced = os.path.join(self.home, "skills", "synced", "feature-finder", "SKILL.md")
        _write(self.synced, "account copy")

    def _run(self, *args):
        out = io.StringIO()
        with redirect_stdout(out):
            rc = main(["--repo", self.repo, "--home", self.home, "--remote", "none", *args])
        return rc, out.getvalue()

    def test_find_copies_lists_differing_retired_skill(self):
        copies = find_copies(self.repo, self.home, remote="none", retired_skills=["feature-finder"])
        self.assertIn(("retired-skill", self.skill), [(c["kind"], c["path"]) for c in copies])

    def test_without_option_differing_skill_is_kept(self):
        self.assertEqual(find_copies(self.repo, self.home, remote="none"), [])

    def test_retired_skill_with_no_repo_plugin(self):
        _write(os.path.join(self.home, "skills", "gone", "SKILL.md"))
        copies = find_copies(self.repo, self.home, remote="none", retired_skills=["gone"])
        self.assertEqual([c["kind"] for c in copies], ["retired-skill"])

    def test_dry_run_reports_and_reminds_then_delete_removes(self):
        rc, out = self._run("--retired-skills", "feature-finder")
        self.assertEqual(rc, 1)
        self.assertIn(self.skill, out)
        self.assertIn("Settings", out)
        self.assertTrue(os.path.isdir(self.skill))
        rc, out = self._run("--retired-skills", "feature-finder", "--delete")
        self.assertEqual(rc, 0)
        self.assertFalse(os.path.exists(self.skill))
        self.assertTrue(os.path.exists(self.synced))
        self.assertIn("Settings", out)

    def test_synced_is_never_listed_or_deleted(self):
        copies = find_copies(self.repo, self.home, remote="none", retired_skills=["synced"])
        self.assertEqual(copies, [])
        self._run("--retired-skills", "synced,feature-finder", "--delete")
        self.assertTrue(os.path.exists(self.synced))

    def test_json_output(self):
        rc, out = self._run("--retired-skills", "feature-finder", "--json")
        data = json.loads(out)
        self.assertEqual([(c["kind"], c["path"]) for c in data], [("retired-skill", self.skill)])
        self.assertTrue(os.path.isdir(self.skill))
        self.assertEqual(rc, 1)


if __name__ == "__main__":
    unittest.main()
