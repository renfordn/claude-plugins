"""Tests for scripts/clean_local_plugin_copies.py (stdlib unittest, mirrors test_check_account_plugins.py)."""
import io
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout

from clean_local_plugin_copies import find_copies, main

REMOTE = "https://github.com/renfordn/claude-plugins"


def _write(path, text="x"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(text)


def _git_clone_stub(path, remote):
    os.makedirs(path)
    subprocess.run(["git", "init", "-q", path], check=True)
    subprocess.run(["git", "-C", path, "remote", "add", "origin", remote], check=True)


class CleanLocalPluginCopiesTests(unittest.TestCase):
    def setUp(self):
        base = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, base)
        self.repo = os.path.join(base, "repo")
        self.home = os.path.join(base, "home")
        for name in ("agent-nelly", "agent-isdd"):
            _write(os.path.join(self.repo, name, ".claude-plugin", "plugin.json"),
                   json.dumps({"name": name, "version": "1.0.0"}))
        _write(os.path.join(self.repo, "agent-isdd", "skills", "plan-reviewer", "SKILL.md"), "same")
        _write(os.path.join(self.repo, "agent-isdd", "agents", "tier1.md"), "same")

    def _kinds(self, plugins=None):
        return sorted((c["kind"], os.path.relpath(c["path"], self.home))
                      for c in find_copies(self.repo, self.home, plugins, remote=REMOTE))

    def test_keeps_account_copies(self):
        # @inline / @synced data and the synced/ tree are the account copies — never touched.
        _write(os.path.join(self.home, "plugins", "data", "agent-nelly-inline", "m.md"))
        _write(os.path.join(self.home, "plugins", "data", "agent-nelly-synced", "m.md"))
        _write(os.path.join(self.home, "plugins", "synced", "acct", "agent-nelly", "p.json"))
        self.assertEqual(self._kinds(), [])

    def test_finds_marketplace_cache_and_data(self):
        _write(os.path.join(self.home, "plugins", "cache", "mkt", "agent-nelly", "0.4.0", "f"))
        _write(os.path.join(self.home, "plugins", "data", "agent-nelly-mkt", "f"))
        self.assertEqual(self._kinds(), [
            ("marketplace-cache", "plugins/cache/mkt/agent-nelly"),
            ("marketplace-data", "plugins/data/agent-nelly-mkt"),
        ])

    def test_finds_repo_clones_only_for_this_remote(self):
        _git_clone_stub(os.path.join(self.home, "plugins", "claude-plugins"), REMOTE + ".git")
        _git_clone_stub(os.path.join(self.home, "plugins", "data", "harness-inline", "claude-plugins"), REMOTE)
        _git_clone_stub(os.path.join(self.home, "plugins", "other"), "https://github.com/x/y")
        self.assertEqual(self._kinds(), [
            ("repo-clone", "plugins/claude-plugins"),
            ("repo-clone", "plugins/data/harness-inline/claude-plugins"),
        ])

    def test_finds_identical_user_level_skills_and_agents_only(self):
        _write(os.path.join(self.home, "skills", "plan-reviewer", "SKILL.md"), "same")
        _write(os.path.join(self.home, "agents", "tier1.md"), "same")
        _write(os.path.join(self.home, "skills", "plan-reviewer-fork", "SKILL.md"), "same")
        _write(os.path.join(self.home, "agents", "tier2.md"), "different")
        self.assertEqual(self._kinds(), [
            ("user-agent", "agents/tier1.md"),
            ("user-skill", "skills/plan-reviewer"),
        ])

    def test_modified_user_level_skill_is_kept(self):
        _write(os.path.join(self.home, "skills", "plan-reviewer", "SKILL.md"), "edited locally")
        self.assertEqual(self._kinds(), [])

    def test_plugins_filter_and_retired_names(self):
        _write(os.path.join(self.home, "plugins", "cache", "mkt", "agent-nelly", "f"))
        _write(os.path.join(self.home, "plugins", "cache", "mkt", "agent-ux", "f"))
        _write(os.path.join(self.home, "plugins", "data", "agent-ux-inline", "f"))
        # agent-ux is retired (not in the repo) — still cleanable when named explicitly,
        # including its now-orphaned @inline data.
        self.assertEqual(self._kinds(["agent-ux"]), [
            ("marketplace-cache", "plugins/cache/mkt/agent-ux"),
            ("retired-data", "plugins/data/agent-ux-inline"),
        ])

    def test_dry_run_by_default_then_delete(self):
        target = os.path.join(self.home, "plugins", "cache", "mkt", "agent-nelly")
        _write(os.path.join(target, "f"))
        with redirect_stdout(io.StringIO()):
            self.assertEqual(main(["--repo", self.repo, "--home", self.home, "--remote", REMOTE]), 1)
        self.assertTrue(os.path.exists(target))
        with redirect_stdout(io.StringIO()):
            self.assertEqual(main(["--repo", self.repo, "--home", self.home, "--remote", REMOTE, "--delete"]), 0)
        self.assertFalse(os.path.exists(target))
        with redirect_stdout(io.StringIO()):
            self.assertEqual(main(["--repo", self.repo, "--home", self.home, "--remote", REMOTE]), 0)

    def test_reports_marketplace_installs_without_deleting(self):
        _write(os.path.join(self.home, "plugins", "installed_plugins.json"),
               json.dumps({"plugins": {"agent-nelly@renfordn-plugins": [{}], "other@x": [{}]}}))
        self.assertEqual(self._kinds(), [("marketplace-install", "plugins/installed_plugins.json")])
        out = io.StringIO()
        with redirect_stdout(out):
            main(["--repo", self.repo, "--home", self.home, "--remote", REMOTE, "--delete"])
        self.assertIn("claude plugin uninstall agent-nelly@renfordn-plugins", out.getvalue())
        self.assertTrue(os.path.exists(os.path.join(self.home, "plugins", "installed_plugins.json")))


if __name__ == "__main__":
    unittest.main()
