"""hook_state.active_state_dir()/workflow_state_path() must skip `Workflow Status: Complete` features.

Regression: discovery picked the newest-mtime workflow-state.md regardless of status, so a
finished feature stayed "active" forever and kept receiving workflow-state.json and telemetry
writes from unrelated sessions. Runs in a subprocess because BASE is resolved at import time.
"""
import os
import subprocess
import sys
import tempfile
import time
import unittest

HOOKS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hooks")


class ActiveStateDirSkipsCompleteTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.data = os.path.join(self._tmp.name, "data", "plugin-harness-mkt")
        self.cwd = os.path.join(self._tmp.name, "project")
        os.makedirs(self.cwd)
        self.spec = os.path.join(self.data, "sdd-memory", self._slug(self.cwd), "spec")

    def tearDown(self):
        self._tmp.cleanup()

    @staticmethod
    def _slug(cwd):
        import re
        return re.sub(r"[^A-Za-z0-9]+", "-", os.path.abspath(cwd)).strip("-").lower()

    def seed(self, name, status, mtime_offset=0):
        d = os.path.join(self.spec, name)
        os.makedirs(d, exist_ok=True)
        path = os.path.join(d, "workflow-state.md")
        with open(path, "w") as fh:
            fh.write(f"# Workflow State\n\n## Workflow Status\n- Workflow Status: {status}\n")
        t = time.time() + mtime_offset
        os.utime(path, (t, t))
        return d

    def resolve(self, fn):
        env = dict(os.environ, CLAUDE_PLUGIN_DATA=self.data)
        env.pop("CLAUDE_PLUGIN_OPTION_SHARED_MEMORY_ROOT", None)
        proc = subprocess.run(
            [sys.executable, "-c", f"import hook_state; print(hook_state.{fn}({self.cwd!r}))"],
            cwd=HOOKS, capture_output=True, text=True, env=env,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return proc.stdout.strip()

    def test_only_complete_feature_means_no_active_workflow(self):
        self.seed("done", "Complete")
        self.assertEqual(self.resolve("active_state_dir"), "None")
        self.assertEqual(self.resolve("workflow_state_path"), "None")

    def test_complete_status_is_case_insensitive(self):
        self.seed("done", "complete")
        self.assertEqual(self.resolve("active_state_dir"), "None")

    def test_newer_complete_feature_is_skipped_for_older_in_progress(self):
        in_progress = self.seed("wip", "In Progress", mtime_offset=-100)
        self.seed("done", "Complete")
        self.assertEqual(os.path.realpath(self.resolve("active_state_dir")), os.path.realpath(in_progress))

    def test_paused_and_in_progress_still_newest_first(self):
        self.seed("older", "In Progress", mtime_offset=-100)
        paused = self.seed("newer", "Awaiting Implementation Request")
        self.assertEqual(os.path.realpath(self.resolve("active_state_dir")), os.path.realpath(paused))
        self.assertEqual(
            os.path.realpath(self.resolve("workflow_state_path")),
            os.path.realpath(os.path.join(paused, "workflow-state.json")),
        )

    def test_missing_status_field_is_treated_as_active(self):
        d = os.path.join(self.spec, "legacy")
        os.makedirs(d)
        with open(os.path.join(d, "workflow-state.md"), "w") as fh:
            fh.write("- Title: Legacy\n")
        self.assertEqual(os.path.realpath(self.resolve("active_state_dir")), os.path.realpath(d))


if __name__ == "__main__":
    unittest.main()
