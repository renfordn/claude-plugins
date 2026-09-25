#!/usr/bin/env python3
"""
E2E integration test: subagent_report + before_continue rollback roundtrip.

Rewritten 2026-09-25 -- the previous version of this file asserted against escalation marker
names (AGENT-TDD-DESIGN-CONTRADICTION, AGENT-TDD-RESEARCH-VALIDATION-FAILED,
AGENT-TDD-SLICING-REQUIRES-DECISION, AGENT-TDD-PLAN-VALIDITY-FLAGGED) and a "reads recap.md"
detection path that never existed in the actual codebase, and every test asserted a self-built
dict/string against itself rather than exercising a real hook, so it could never fail regardless
of real hook behavior.

Current architecture (see hooks/subagent_report.py and hooks/before_continue.py):
1. agent-tdd emits one of two markers when it needs agent-isdd to roll back a phase:
   - Automatic: `<!--AGENT-TDD-PLAN-FLAG: reason="..."-->` -- agent-tdd doesn't know agent-isdd's
     phase vocabulary, so the target always defaults to "Requirements", the most conservative
     choice (see subagent_report.py's PLAN_FLAG_MARKER comment).
   - Human-relay: `<!--SDD-ROLLBACK-REQUEST: target=(Requirements|Design|Tasks) reason="..."-->`
     -- a human names the target explicitly.
2. subagent_report.py's SubagentStop hook detects either marker in the transcript and writes
   `rollback_pending` = {target, reason, source} into workflow-state.json via
   sdd_state.write_rollback_pending() -- it never reads or writes recap.md for this.
3. On the next /isdd-continue, before_continue.py reads `rollback_pending` from
   workflow-state.json and surfaces a "Rollback Pending" systemMessage suggesting
   `/isdd-rewind <target>`.

Tests run both hooks as real subprocesses via hook_test_utils, the same way production invokes
them (see hooks.json), rather than reimplementing their logic against inline fixtures.
"""
import json
import os
import unittest

import hook_test_utils as h


def _assistant_line(content):
    return json.dumps({"type": "assistant", "message": {"role": "assistant", "content": content}})


class BeforeContinueAgentTddRollbackRoundtripTests(unittest.TestCase):
    def _state_json_path(self, feature_dir):
        return os.path.join(feature_dir, "workflow-state.json")

    def test_plan_flag_marker_sets_rollback_pending_defaulting_to_requirements(self):
        with h.temp_git_repo() as repo, h.temp_home() as home:
            feature_dir = h.feature_spec_dir(home, repo)
            h.seed_state_file(feature_dir, title="User Email Validation", workflow_status="Implementing")

            transcript = os.path.join(home, "transcript.jsonl")
            with open(transcript, "w", encoding="utf-8") as fh:
                fh.write(_assistant_line(
                    '<!--AGENT-TDD-PLAN-FLAG: reason="Ralph Loops exceeded iteration limit '
                    'on task slicing"-->\nPausing task slicing; architectural decision needed.'
                ) + "\n")

            msg, rc = h.run_hook_message(
                "subagent_report.py",
                {"cwd": repo, "transcript_path": transcript},
                env_extra={"HOME": home},
            )
            self.assertEqual(rc, 0)
            self.assertIsNotNone(msg)
            self.assertIn("rollback request was received", msg)
            self.assertIn("target=Requirements", msg)

            with open(self._state_json_path(feature_dir)) as fh:
                state = json.load(fh)
            rollback = state.get("rollback_pending")
            self.assertIsNotNone(rollback)
            self.assertEqual(rollback["target"], "Requirements")
            self.assertEqual(rollback["source"], "agent-tdd")
            self.assertIn("Ralph Loops exceeded iteration limit", rollback["reason"])

    def test_rollback_pending_surfaces_on_next_continue(self):
        """Full roundtrip: subagent_report.py sets rollback_pending during the SubagentStop that
        ends agent-tdd's turn, then a *separate* before_continue.py invocation -- as would run on
        the user's next /isdd-continue -- surfaces it with the suggested /isdd-rewind command."""
        with h.temp_git_repo() as repo, h.temp_home() as home:
            feature_dir = h.feature_spec_dir(home, repo)
            h.seed_state_file(feature_dir, title="User Email Validation", workflow_status="Implementing")

            transcript = os.path.join(home, "transcript.jsonl")
            with open(transcript, "w", encoding="utf-8") as fh:
                fh.write(_assistant_line(
                    '<!--AGENT-TDD-PLAN-FLAG: reason="Design assumes User model is immutable; '
                    'research found email property is mutable"-->\nPausing for design contradiction.'
                ) + "\n")

            _, rc = h.run_hook_message(
                "subagent_report.py",
                {"cwd": repo, "transcript_path": transcript},
                env_extra={"HOME": home},
            )
            self.assertEqual(rc, 0)

            msg, rc = h.run_hook_message(
                "before_continue.py",
                {"cwd": repo},
                env_extra={"HOME": home},
            )
            self.assertEqual(rc, 0)
            self.assertIsNotNone(msg)
            self.assertIn("Rollback Pending", msg)
            self.assertIn("/isdd-rewind Requirements", msg)
            self.assertIn("Design assumes User model is immutable", msg)

    def test_human_relay_marker_uses_explicit_target(self):
        with h.temp_git_repo() as repo, h.temp_home() as home:
            feature_dir = h.feature_spec_dir(home, repo)
            h.seed_state_file(feature_dir, title="User Email Validation", workflow_status="Implementing")

            transcript = os.path.join(home, "transcript.jsonl")
            with open(transcript, "w", encoding="utf-8") as fh:
                fh.write(_assistant_line(
                    '<!--SDD-ROLLBACK-REQUEST: target=Design reason="code-reviewer flagged a '
                    'design gap in the email uniqueness check"-->'
                ) + "\n")

            h.run_hook_message(
                "subagent_report.py",
                {"cwd": repo, "transcript_path": transcript},
                env_extra={"HOME": home},
            )

            msg, rc = h.run_hook_message(
                "before_continue.py",
                {"cwd": repo},
                env_extra={"HOME": home},
            )
            self.assertEqual(rc, 0)
            self.assertIn("/isdd-rewind Design", msg)
            self.assertIn("code-reviewer flagged a design gap", msg)

    def test_no_marker_leaves_no_rollback_pending(self):
        with h.temp_git_repo() as repo, h.temp_home() as home:
            feature_dir = h.feature_spec_dir(home, repo)
            h.seed_state_file(feature_dir, title="User Email Validation", workflow_status="Implementing")

            transcript = os.path.join(home, "transcript.jsonl")
            with open(transcript, "w", encoding="utf-8") as fh:
                fh.write(_assistant_line(
                    "Task slicing complete. All slices passed tests, full regression green."
                ) + "\n")

            h.run_hook_message(
                "subagent_report.py",
                {"cwd": repo, "transcript_path": transcript},
                env_extra={"HOME": home},
            )

            state_path = self._state_json_path(feature_dir)
            if os.path.exists(state_path):
                with open(state_path) as fh:
                    state = json.load(fh)
                self.assertNotIn("rollback_pending", state)

            msg, rc = h.run_hook_message(
                "before_continue.py",
                {"cwd": repo},
                env_extra={"HOME": home},
            )
            self.assertEqual(rc, 0)
            self.assertIsNone(msg)


if __name__ == "__main__":
    unittest.main()
