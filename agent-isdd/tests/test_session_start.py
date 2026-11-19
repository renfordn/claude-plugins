"""Tests for hooks/session_start.py.

Ported from the live verification run during the Agent Responsibility Cleanup (Phase 1
integration proof) and Global Cross-Project Memory Tier (Phase 5) features.

Phase 3 of the Decouple Memory feature removed the PROJECT-MEMORY.md/GLOBAL-MEMORY.md
announcement block -- those central-memory files, and memory-orchestrator that owned them,
no longer exist; agent-nelly owns cross-feature memory now. This hook only announces
per-feature spec state and any active workflow.
"""
import json
import os
import subprocess
import unittest

import hook_test_utils as h


class SessionStartTests(unittest.TestCase):
    def test_does_not_surface_project_memory_file(self):
        """Phase 3: PROJECT-MEMORY.md is no longer read/announced by this hook."""
        with h.temp_home() as home:
            cwd = "/tmp"
            slug = h.project_slug_for(cwd)
            mem_dir = os.path.join(home, ".claude", "sdd-memory", slug)
            os.makedirs(mem_dir)
            with open(os.path.join(mem_dir, "PROJECT-MEMORY.md"), "w") as fh:
                fh.write("## Goal\n\n- test-feature: some goal text\n")

            decision, rc = h.run_hook(
                "session_start.py", {"cwd": cwd}, env_extra={"HOME": home}
            )
            self.assertEqual(rc, 0)
            self.assertIsNotNone(decision)
            ctx = decision["additionalContext"]
            self.assertNotIn("some goal text", ctx)

    def test_does_not_surface_global_memory_file(self):
        """Phase 3: GLOBAL-MEMORY.md is no longer read/announced by this hook."""
        with h.temp_home() as home:
            cwd = "/tmp"
            global_dir = os.path.join(home, ".claude", "sdd-memory", "global")
            os.makedirs(global_dir)
            with open(os.path.join(global_dir, "GLOBAL-MEMORY.md"), "w") as fh:
                fh.write(
                    "---\n"
                    "name: some-fact\n"
                    "description: a short description\n"
                    "metadata:\n  type: feedback\n"
                    "---\n\n"
                    "This is the FULL BODY that should never appear in session_start output.\n"
                )

            decision, rc = h.run_hook(
                "session_start.py", {"cwd": cwd}, env_extra={"HOME": home}
            )
            self.assertEqual(rc, 0)
            self.assertIsNotNone(decision)
            ctx = decision["additionalContext"]
            self.assertNotIn("some-fact", ctx)
            self.assertNotIn("FULL BODY", ctx)

    def test_surfaces_active_workflow_banner(self):
        with h.temp_home() as home:
            cwd = "/tmp"
            feature_dir = h.feature_spec_dir(home, cwd)
            h.seed_state_file(
                feature_dir,
                title="My Feature",
                current_phase="Design",
                workflow_status="In Progress",
                next_action="Do the thing",
            )

            decision, rc = h.run_hook(
                "session_start.py", {"cwd": cwd}, env_extra={"HOME": home}
            )
            self.assertEqual(rc, 0)
            self.assertIsNotNone(decision)
            ctx = decision["additionalContext"]
            self.assertIn("My Feature", ctx)
            self.assertIn("Design", ctx)

    def test_silent_sections_when_nothing_to_report(self):
        with h.temp_home() as home:
            decision, rc = h.run_hook(
                "session_start.py", {"cwd": "/tmp"}, env_extra={"HOME": home}
            )
            self.assertEqual(rc, 0)
            self.assertIsNotNone(decision)
            ctx = decision["additionalContext"]
            self.assertNotIn("Active spec-driven-development workflow", ctx)


class BaselineDiffTests(unittest.TestCase):
    def _setup(self, home, repo, baseline=True):
        fd = h.feature_spec_dir(home, repo)
        h.seed_state_file(fd, current_phase="Implementation", workflow_status="In Progress")
        if baseline:
            head = subprocess.run(["git", "-C", repo, "rev-parse", "HEAD"],
                                  capture_output=True, text=True).stdout.strip()
            branch = subprocess.run(["git", "-C", repo, "rev-parse", "--abbrev-ref", "HEAD"],
                                    capture_output=True, text=True).stdout.strip()
            with open(os.path.join(fd, "workflow-state.json"), "w") as fh:
                json.dump({"baseline": {"branch": branch, "head": head, "dirty_files": []}}, fh)
        return fd

    def test_reports_files_changed_since_baseline(self):
        with h.temp_home() as home, h.temp_git_repo() as repo:
            subprocess.run(["git", "-C", repo, "commit", "-q", "--allow-empty", "-m", "i"], check=True)
            self._setup(home, repo)
            for n in ("a.txt", "b.txt"):
                with open(os.path.join(repo, n), "w") as fh:
                    fh.write("x")
            decision, rc = h.run_hook("session_start.py", {"cwd": repo}, env_extra={"HOME": home})
            self.assertEqual(rc, 0)
            self.assertIn("2 files changed since baseline", decision["additionalContext"])

    def test_no_baseline_output_unchanged(self):
        with h.temp_home() as home, h.temp_git_repo() as repo:
            subprocess.run(["git", "-C", repo, "commit", "-q", "--allow-empty", "-m", "i"], check=True)
            self._setup(home, repo, baseline=False)
            with open(os.path.join(repo, "a.txt"), "w") as fh:
                fh.write("x")
            decision, rc = h.run_hook("session_start.py", {"cwd": repo}, env_extra={"HOME": home})
            self.assertEqual(rc, 0)
            self.assertNotIn("since baseline", decision["additionalContext"])

    def test_no_change_is_silent(self):
        with h.temp_home() as home, h.temp_git_repo() as repo:
            subprocess.run(["git", "-C", repo, "commit", "-q", "--allow-empty", "-m", "i"], check=True)
            self._setup(home, repo)
            decision, rc = h.run_hook("session_start.py", {"cwd": repo}, env_extra={"HOME": home})
            self.assertEqual(rc, 0)
            self.assertNotIn("since baseline", decision["additionalContext"])


    def test_head_moved_after_baseline(self):
        with h.temp_home() as home, h.temp_git_repo() as repo:
            subprocess.run(["git", "-C", repo, "commit", "-q", "--allow-empty", "-m", "i"], check=True)
            self._setup(home, repo)
            with open(os.path.join(repo, "a.txt"), "w") as fh:
                fh.write("x")
            subprocess.run(["git", "-C", repo, "add", "a.txt"], check=True)
            subprocess.run(["git", "-C", repo, "commit", "-q", "-m", "c"], check=True)
            decision, rc = h.run_hook("session_start.py", {"cwd": repo}, env_extra={"HOME": home})
            self.assertEqual(rc, 0)
            ctx = decision["additionalContext"]
            self.assertIn("1 file changed since baseline", ctx)
            self.assertIn("HEAD moved", ctx)

    def test_non_git_cwd_fails_open(self):
        with h.temp_home() as home:
            fd = h.feature_spec_dir(home, "/tmp")
            h.seed_state_file(fd, current_phase="Implementation", workflow_status="In Progress")
            with open(os.path.join(fd, "workflow-state.json"), "w") as fh:
                json.dump({"baseline": {"branch": "main", "head": "abc", "dirty_files": []}}, fh)
            decision, rc = h.run_hook("session_start.py", {"cwd": "/tmp"}, env_extra={"HOME": home})
            self.assertEqual(rc, 0)
            self.assertNotIn("since baseline", decision["additionalContext"])

    def test_note_swallows_diff_exception_and_respects_budget(self):
        import sys
        from unittest import mock
        hooks = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "hooks")
        sys.path.insert(0, hooks)
        try:
            import session_start as ss
        finally:
            sys.path.remove(hooks)
        with mock.patch.object(ss.baseline, "diff", side_effect=RuntimeError("boom")):
            self.assertEqual(ss._baseline_note("/x", "/y.json"), "")
        with mock.patch.object(ss.baseline, "diff") as d:
            self.assertEqual(ss._baseline_note("/x", "/y.json", deadline=0), "")
            d.assert_not_called()
        with mock.patch.object(ss.baseline, "diff",
                               return_value={"files_changed": ["a"], "incomplete": True}):
            note = ss._baseline_note("/x", "/y.json")
            self.assertIn("count may be low", note)


if __name__ == "__main__":
    unittest.main()
