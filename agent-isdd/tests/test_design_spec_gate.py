"""Tests for hooks/design_spec_gate.py.

New PreToolUse read-only gate (2026-09-16, isdd<->tdd Handoff Reimplementation, design.md
touchpoint 5): denies spawning agent-tdd:agent-TDD unless the active feature's
requirements.md and design.md both have `State: Approved` on disk. Modeled on
slice_spec_gate.py's allow()/deny()/no_decision() shape.
"""
import os
import unittest

import hook_test_utils as h


def _write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)


class DesignSpecGateTests(unittest.TestCase):
    def _call(self, repo, home):
        return h.run_hook(
            "design_spec_gate.py",
            {"cwd": repo, "tool_input": {"subagent_type": "agent-tdd:agent-TDD"}},
            env_extra={"HOME": home},
        )

    def test_unrelated_subagent_type_is_noop(self):
        with h.temp_git_repo() as repo, h.temp_home() as home:
            decision, rc = h.run_hook(
                "design_spec_gate.py",
                {"cwd": repo, "tool_input": {"subagent_type": "agent-isdd:spec-reviewer"}},
                env_extra={"HOME": home},
            )
            self.assertEqual(rc, 0)
            self.assertIsNone(decision)

    def test_no_active_workflow_is_noop(self):
        with h.temp_git_repo() as repo, h.temp_home() as home:
            decision, rc = self._call(repo, home)
            self.assertEqual(rc, 0)
            self.assertIsNone(decision)

    def test_both_approved_is_noop(self):
        with h.temp_git_repo() as repo, h.temp_home() as home:
            feature_dir = h.feature_spec_dir(home, repo)
            h.seed_state_file(feature_dir, title="My Feature", workflow_status="In Progress")
            _write(
                os.path.join(feature_dir, "requirements", "requirements.md"),
                "# Requirements\n\n- State: Approved\n",
            )
            _write(
                os.path.join(feature_dir, "design", "design.md"),
                "# Design\n\n- State: Approved\n",
            )
            decision, rc = self._call(repo, home)
            self.assertEqual(rc, 0)
            self.assertIsNone(decision)

    def test_missing_design_md_is_denied(self):
        with h.temp_git_repo() as repo, h.temp_home() as home:
            feature_dir = h.feature_spec_dir(home, repo)
            h.seed_state_file(feature_dir, title="My Feature", workflow_status="In Progress")
            _write(
                os.path.join(feature_dir, "requirements", "requirements.md"),
                "# Requirements\n\n- State: Approved\n",
            )
            decision, rc = self._call(repo, home)
            self.assertEqual(rc, 0)
            self.assertIsNotNone(decision)
            self.assertEqual(decision["permissionDecision"], "deny")
            self.assertIn("design.md", decision["permissionDecisionReason"])

    def test_design_not_approved_is_denied(self):
        with h.temp_git_repo() as repo, h.temp_home() as home:
            feature_dir = h.feature_spec_dir(home, repo)
            h.seed_state_file(feature_dir, title="My Feature", workflow_status="In Progress")
            _write(
                os.path.join(feature_dir, "requirements", "requirements.md"),
                "# Requirements\n\n- State: Approved\n",
            )
            _write(
                os.path.join(feature_dir, "design", "design.md"),
                "# Design\n\n- State: Draft\n",
            )
            decision, rc = self._call(repo, home)
            self.assertEqual(rc, 0)
            self.assertIsNotNone(decision)
            self.assertEqual(decision["permissionDecision"], "deny")
            self.assertIn("design.md", decision["permissionDecisionReason"])


if __name__ == "__main__":
    unittest.main()
