"""Slice-keyed, concurrency-safe tdd-progress.json writes from hooks/tdd_subagent_stop.py."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor

HOOKS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "hooks")
HOOK = os.path.join(HOOKS_DIR, "tdd_subagent_stop.py")
sys.path.insert(0, HOOKS_DIR)
import tdd_state  # noqa: E402


def _report(n, plan="does a thing", phase="green_pause"):
    return ("<!--AGENT-TDD-REPORT-->\n<!--AGENT-TDD-PHASE:%s-->\n\n**Plan**\nSlice %s: %s\n\n"
            "**Acceptance Criteria**\nmet\n" % (phase, n, plan))


def _git(cwd, *args):
    env = {k: v for k, v in os.environ.items() if k not in ("GIT_DIR", "GIT_WORK_TREE")}
    subprocess.run(["git", "-C", cwd, "-c", "user.email=t@t", "-c", "user.name=t", *args],
                   check=True, capture_output=True, env=env)


class SliceKeyedProgressTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = os.path.realpath(self._tmp.name)
        self.env = dict(os.environ, CLAUDE_PLUGIN_DATA=os.path.join(self.tmp, "data"))
        self.env.pop("CLAUDE_PLUGIN_OPTION_SHARED_MEMORY_ROOT", None)
        # keep the hook off the real ~/.claude/settings.json pluginConfigs shared root
        self.env["HOME"] = self.tmp
        self.env["CLAUDE_CONFIG_DIR"] = os.path.join(self.tmp, "cfg")
        self.cwd = os.path.join(self.tmp, "proj")
        os.makedirs(self.cwd)

    def _run(self, text, cwd=None):
        payload = {"cwd": cwd or self.cwd, "last_assistant_message": text}
        return subprocess.run([sys.executable, HOOK], input=json.dumps(payload),
                              capture_output=True, text=True, env=self.env)

    def _path(self, cwd=None):
        base = os.path.join(self.tmp, "data", "agent-tdd-state")
        slug = tdd_state.project_slug(cwd or self.cwd)
        return os.path.join(base, slug, "tdd-progress.json")

    def _slices(self, cwd=None):
        with open(self._path(cwd)) as fh:
            return json.load(fh)["slices"]

    def test_concurrent_slices_all_recorded(self):
        with ThreadPoolExecutor(6) as ex:
            results = list(ex.map(lambda n: self._run(_report(n, "plan %d" % n)), range(1, 7)))
        self.assertTrue(all(r.returncode == 0 for r in results))
        sl = self._slices()
        self.assertEqual(sorted(s["slice"] for s in sl), [str(n) for n in range(1, 7)])
        self.assertEqual(len({s["id"] for s in sl}), 6)

    def test_same_slice_id_updates_one_entry(self):
        self._run(_report(2, "first wording"))
        self._run(_report(2, "second wording", phase="refactor_complete"))
        sl = self._slices()
        self.assertEqual(len(sl), 1)
        self.assertEqual(sl[0]["slice"], "2")
        self.assertIn("second wording", sl[0]["description"])
        self.assertEqual(sl[0]["status"], "refactor_complete")

    def test_no_slice_id_matches_by_description_as_before(self):
        text = ("<!--AGENT-TDD-REPORT-->\n<!--AGENT-TDD-PHASE:green_pause-->\n\n"
                "**Plan**\nAdd a widget\n")
        self._run(text)
        self._run(text)
        sl = self._slices()
        self.assertEqual(len(sl), 1)
        self.assertNotIn("slice", sl[0])
        self.assertEqual(sl[0]["id"], 1)

    def test_worktree_cwd_lands_in_main_checkout_file(self):
        main = os.path.join(self.tmp, "main")
        os.makedirs(main)
        _git(main, "init", "-q")
        _git(main, "commit", "-q", "--allow-empty", "-m", "init")
        wt = os.path.join(self.tmp, "wt")
        _git(main, "worktree", "add", "-q", wt, "-b", "wtbranch")
        self._run(_report(3), cwd=wt)
        self.assertEqual([s["slice"] for s in self._slices(main)], ["3"])
        self.assertFalse(os.path.exists(self._path(wt)))

    def test_ids_unique_after_deletion(self):
        for n in (1, 2, 3):
            self._run(_report(n))
        p = self._path()
        with open(p) as fh:
            data = json.load(fh)
        data["slices"] = [s for s in data["slices"] if s["slice"] != "1"]
        with open(p, "w") as fh:
            json.dump(data, fh)
        self._run(_report(4))
        ids = [s["id"] for s in self._slices()]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(max(ids), 4)

    def test_prose_slice_mention_stays_on_description_path(self):
        text = ("<!--AGENT-TDD-REPORT-->\n<!--AGENT-TDD-PHASE:green_pause-->\n\n"
                "**Plan**\nAdd a widget\n\nReusing the helper from Slice 1.\n")
        self._run(text)
        self._run(text)
        sl = self._slices()
        self.assertEqual(len(sl), 1)
        self.assertNotIn("slice", sl[0])

    def test_slice_id_reused_after_refactor_complete_appends(self):
        self._run(_report(1, "old", phase="refactor_complete"))
        self._run(_report(1, "new"))
        sl = self._slices()
        self.assertEqual(len(sl), 2)
        self.assertEqual(len({s["id"] for s in sl}), 2)

    def test_same_slice_id_in_different_features_does_not_collapse(self):
        self._run("Feature: alpha\n" + _report(1, "a"))
        self._run("Feature: beta\n" + _report(1, "b"))
        self.assertEqual(sorted(s["feature"] for s in self._slices()), ["alpha", "beta"])

    def test_explicit_slice_id_marker_wins(self):
        self._run("<!--SLICE-ID: 7-->\n<!--AGENT-TDD-REPORT-->\n**Plan**\nno title here\n")
        self.assertEqual(self._slices()[0]["slice"], "7")


if __name__ == "__main__":
    unittest.main()
