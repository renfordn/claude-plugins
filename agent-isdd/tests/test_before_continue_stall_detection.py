"""Tests for hooks/before_continue.py's mid-workflow stall detection.

Reproduces the production scenario: the orchestrator finishes a phase (its artifact is
`State: Approved`), provides guidance at the phase boundary, and ends its turn instead of
continuing into the next phase skill in the same turn. `/sdd-continue` (before_continue.py)
should surface that and explain that resuming will auto-advance.

Workflow Status stays `In Progress` for this case -- per workflow-manager's own contract
(skills/workflow-manager/SKILL.md's `complete`/`handoff` rows), `Workflow Status: Complete`
is reserved for the whole feature's final completion/handoff, never set for an individual
phase finishing. The per-phase completion signal is the phase artifact's own `State: Approved`
field (see references/artifact-templates.md).
"""
import os
import unittest

import hook_test_utils as h


class BeforeContinueStallDetectionTests(unittest.TestCase):
    def _seed_approved_design(self, feature_dir):
        design_dir = os.path.join(feature_dir, "design")
        os.makedirs(design_dir, exist_ok=True)
        with open(os.path.join(design_dir, "design.md"), "w", encoding="utf-8") as fh:
            fh.write("# Design\n\n- State: Approved\n")

    def test_design_approved_with_no_tasks_file_surfaces_stall(self):
        with h.temp_git_repo() as repo, h.temp_home() as home:
            feature_dir = h.feature_spec_dir(home, repo)
            h.seed_state_file(
                feature_dir,
                title="My Feature",
                current_phase="Design",
                workflow_status="In Progress",
            )
            self._seed_approved_design(feature_dir)
            msg, rc = h.run_hook_message(
                "before_continue.py", {"cwd": repo}, env_extra={"HOME": home}
            )
            self.assertEqual(rc, 0)
            self.assertIsNotNone(msg, "expected a stall message, got none")
            self.assertIn("Stall", msg)
            self.assertIn("Tasks", msg)

    def test_design_approved_with_tasks_file_present_is_not_a_stall(self):
        with h.temp_git_repo() as repo, h.temp_home() as home:
            feature_dir = h.feature_spec_dir(home, repo)
            h.seed_state_file(
                feature_dir,
                title="My Feature",
                current_phase="Design",
                workflow_status="In Progress",
            )
            self._seed_approved_design(feature_dir)
            tasks_dir = os.path.join(feature_dir, "tasks")
            os.makedirs(tasks_dir, exist_ok=True)
            with open(os.path.join(tasks_dir, "tasks.md"), "w", encoding="utf-8") as fh:
                fh.write("# Tasks\n")
            msg, rc = h.run_hook_message(
                "before_continue.py", {"cwd": repo}, env_extra={"HOME": home}
            )
            self.assertEqual(rc, 0)
            self.assertIsNone(msg)


if __name__ == "__main__":
    unittest.main()
