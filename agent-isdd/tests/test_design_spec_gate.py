"""Tests for hooks/design_spec_gate.py.

New PreToolUse read-only gate (2026-09-16, isdd<->tdd Handoff Reimplementation, design.md
touchpoint 5): denies spawning agent-tdd:agent-TDD unless the active feature's
requirements.md and design.md both have `State: Approved` on disk. Modeled on
slice_spec_gate.py's allow()/deny()/no_decision() shape.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "hooks"))
import approval

import hook_test_utils as h


def _write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)


REQ = "# Requirements\n\n- State: Approved\n"
DES = "# Design\n\n- State: Approved\n"


def _approved_feature(home, repo, **state):
    fd = h.feature_spec_dir(home, repo)
    state.setdefault("implementation_requested", "Yes")
    sp = h.seed_state_file(fd, title="My Feature", workflow_status="In Progress", **state)
    _write(os.path.join(fd, "requirements", "requirements.md"), REQ)
    _write(os.path.join(fd, "design", "design.md"), DES)
    return fd, sp


def _fields(sp):
    import sdd_state
    return sdd_state.parse_state(sp)


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
            h.seed_state_file(feature_dir, title="My Feature", workflow_status="In Progress",
                              implementation_requested="Yes",
                              approval_hash=approval.approval_hash(REQ, DES))
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

    def test_implementation_not_requested_is_denied(self):
        with h.temp_git_repo() as repo, h.temp_home() as home:
            _approved_feature(home, repo, implementation_requested="No")
            decision, rc = self._call(repo, home)
            self.assertEqual(decision["permissionDecision"], "deny")
            self.assertIn("Implementation Requested", decision["permissionDecisionReason"])

    def test_pending_freezes_hash_and_allows(self):
        with h.temp_git_repo() as repo, h.temp_home() as home:
            fd, sp = _approved_feature(home, repo, approval_pending="yes")
            decision, rc = self._call(repo, home)
            self.assertIsNone(decision)
            self.assertEqual(_fields(sp)["approval hash"], approval.approval_hash(REQ, DES))

    def test_mismatch_is_denied_with_reapprove_guidance(self):
        with h.temp_git_repo() as repo, h.temp_home() as home:
            fd, sp = _approved_feature(home, repo, approval_hash="deadbeef")
            decision, rc = self._call(repo, home)
            self.assertEqual(decision["permissionDecision"], "deny")
            reason = decision["permissionDecisionReason"]
            self.assertIn("AskUserQuestion", reason)
            self.assertIn("approval.py", reason)
            self.assertIn("refreeze", reason)

    def test_edit_after_freeze_is_denied(self):
        with h.temp_git_repo() as repo, h.temp_home() as home:
            fd, sp = _approved_feature(home, repo, approval_pending="yes")
            self.assertIsNone(self._call(repo, home)[0])
            _write(os.path.join(fd, "design", "design.md"), DES + "\nNew scope\n")
            decision, rc = self._call(repo, home)
            self.assertEqual(decision["permissionDecision"], "deny")

    def test_legacy_allows_once_and_records_hash(self):
        with h.temp_git_repo() as repo, h.temp_home() as home:
            fd, sp = _approved_feature(home, repo)
            self.assertIsNone(self._call(repo, home)[0])
            self.assertEqual(_fields(sp)["approval hash"], approval.approval_hash(REQ, DES))

    def test_blank_hash_without_pending_is_denied(self):
        with h.temp_git_repo() as repo, h.temp_home() as home:
            _approved_feature(home, repo, approval_hash="")
            decision, rc = self._call(repo, home)
            self.assertEqual(decision["permissionDecision"], "deny")
            self.assertIn("refreeze", decision["permissionDecisionReason"])

    def test_placeholder_hash_is_not_a_mismatch_freezes_when_pending(self):
        with h.temp_git_repo() as repo, h.temp_home() as home:
            fd, sp = _approved_feature(home, repo, approval_hash="None", approval_pending="yes")
            self.assertIsNone(self._call(repo, home)[0])

    def test_json_only_hash_is_denied(self):
        import json
        with h.temp_git_repo() as repo, h.temp_home() as home:
            fd, sp = _approved_feature(home, repo)
            with open(os.path.join(fd, "workflow-state.json"), "w") as fh:
                json.dump({"approval_hash": approval.approval_hash(REQ, DES)}, fh)
            decision, rc = self._call(repo, home)
            self.assertEqual(decision["permissionDecision"], "deny")

    def test_not_requested_deny_names_approve_command(self):
        with h.temp_git_repo() as repo, h.temp_home() as home:
            _approved_feature(home, repo, implementation_requested="No")
            reason = self._call(repo, home)[0]["permissionDecisionReason"]
            self.assertIn("AskUserQuestion", reason)
            self.assertIn("approval.py", reason)

    def test_deny_text_has_real_absolute_script_path(self):
        import re
        for kw in ({"approval_hash": "deadbeef"}, {"implementation_requested": "No"}):
            with h.temp_git_repo() as repo, h.temp_home() as home:
                _approved_feature(home, repo, **kw)
                reason = self._call(repo, home)[0]["permissionDecisionReason"]
                self.assertNotIn("CLAUDE_PLUGIN_ROOT", reason)
                self.assertIn('CLAUDE_PLUGIN_DATA="', reason)
                path = re.search(r'python3 "([^"]+approval\.py)"', reason).group(1)
                self.assertTrue(os.path.isabs(path) and os.path.isfile(path), path)

    def test_track_fast_spawn_is_also_gated(self):
        with h.temp_git_repo() as repo, h.temp_home() as home:
            _approved_feature(home, repo, track="Fast", approval_hash="deadbeef")
            decision, rc = self._call(repo, home)
            self.assertEqual(decision["permissionDecision"], "deny")


if __name__ == "__main__":
    unittest.main()
