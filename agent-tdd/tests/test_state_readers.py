"""Readers (tdd_stop, tdd_session_start) see state written from a linked worktree."""
import json
import os
import subprocess
import sys
import tempfile
import unittest

HOOKS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "hooks")
sys.path.insert(0, HOOKS_DIR)
import tdd_state  # noqa: E402


def _git(cwd, *args):
    env = {k: v for k, v in os.environ.items() if k not in ("GIT_DIR", "GIT_WORK_TREE")}
    subprocess.run(["git", "-C", cwd, "-c", "user.email=t@t", "-c", "user.name=t", *args],
                   check=True, capture_output=True, env=env)


class StateReaderTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = os.path.realpath(self._tmp.name)
        self.env = dict(os.environ, CLAUDE_PLUGIN_DATA=os.path.join(self.tmp, "data"),
                        HOME=self.tmp, CLAUDE_CONFIG_DIR=os.path.join(self.tmp, "cfg"))
        self.env.pop("CLAUDE_PLUGIN_OPTION_SHARED_MEMORY_ROOT", None)
        self.main = os.path.join(self.tmp, "main")
        os.makedirs(self.main)
        _git(self.main, "init", "-q")
        _git(self.main, "commit", "-q", "--allow-empty", "-m", "init")
        self.wt = os.path.join(self.tmp, "wt")
        _git(self.main, "worktree", "add", "-q", self.wt, "-b", "feat")

    def _write(self, cwd):
        """Write a pending slice the way the writers do: under the main-checkout state dir."""
        path = os.path.join(self.tmp, "data", "agent-tdd-state",
                            tdd_state.project_slug(tdd_state.state_cwd(cwd)), "tdd-progress.json")
        tdd_state.update_json(path, lambda d: {"slices": [
            {"id": "s1", "description": "pending thing", "status": "green_pending_review"}]})
        return path

    def _run(self, script, cwd):
        return subprocess.run([sys.executable, os.path.join(HOOKS_DIR, script)],
                              input=json.dumps({"cwd": cwd}), capture_output=True,
                              text=True, env=self.env)

    def test_progress_path_shared_across_worktrees(self):
        old = dict(os.environ)
        os.environ.update(self.env)
        try:
            self.assertEqual(tdd_state.progress_path(self.wt), tdd_state.progress_path(self.main))
        finally:
            os.environ.clear()
            os.environ.update(old)

    def test_hooks_list_slice_from_main_and_worktree(self):
        self._write(self.wt)
        for cwd in (self.main, self.wt):
            for script in ("tdd_stop.py", "tdd_session_start.py"):
                r = self._run(script, cwd)
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertIn("pending thing", r.stdout, (script, cwd))

    def test_legacy_per_worktree_file_merged_read_only(self):
        self._write(self.wt)
        legacy = os.path.join(tdd_state.tdd_memory_dir(self.wt), "tdd-progress.json")
        legacy_data = {"slices": [
            {"id": "old1", "description": "legacy thing", "status": "green_pending_review"},
            {"id": "s1", "description": "dup", "status": "green_pending_review"}]}
        tdd_state.update_json(legacy, lambda d: legacy_data)
        ids = [s["id"] for s in tdd_state.read_tdd_progress(self.wt)["slices"]]
        self.assertEqual(sorted(ids), ["old1", "s1"])
        self.assertTrue(os.path.exists(legacy))
        with open(legacy) as fh:
            self.assertEqual(json.load(fh), legacy_data)

    def test_plain_repo_unchanged(self):
        plain = os.path.join(self.tmp, "plain")
        os.makedirs(plain)
        self._write(plain)
        for script in ("tdd_stop.py", "tdd_session_start.py"):
            self.assertIn("pending thing", self._run(script, plain).stdout)


if __name__ == "__main__":
    unittest.main()
