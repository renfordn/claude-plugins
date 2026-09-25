"""Tests for hooks/review_gate.py: agent-TDD can't be resumed past Green without a review.

Payload shapes match what Claude Code 2.1.282 sends (captured live): SubagentStop carries
agent_id / agent_type / last_assistant_message; SendMessage's tool_input.to is the agent_id.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

HOOK = os.path.join(os.path.dirname(__file__), "..", "hooks", "review_gate.py")
TDD_ID = "a1b2c3d4e5f60718"
GREEN = "<!--AGENT-TDD-REPORT-->\n<!--AGENT-TDD-PHASE:green_pause-->\n**Plan**\nslice 1"
REFACTORED = "<!--AGENT-TDD-REPORT-->\n<!--AGENT-TDD-PHASE:refactor_complete-->\n**Plan**\nslice 1"
REVIEW = "<!--CODE-REVIEWER-REPORT-->\n**Verdict**: clear"


class ReviewGateTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.cwd = os.path.join(self._tmp.name, "project")
        os.makedirs(self.cwd)
        self.env = dict(os.environ, CLAUDE_PLUGIN_DATA=os.path.join(self._tmp.name, "data"))

    def tearDown(self):
        self._tmp.cleanup()

    def _run(self, payload):
        payload.setdefault("cwd", self.cwd)
        result = subprocess.run([sys.executable, HOOK], input=json.dumps(payload),
                                capture_output=True, text=True, env=self.env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("[review_gate]", result.stderr)
        return json.loads(result.stdout) if result.stdout.strip() else None

    def _stop(self, text, agent_id=TDD_ID, agent_type="agent-tdd:agent-TDD"):
        return self._run({"hook_event_name": "SubagentStop", "agent_id": agent_id,
                          "agent_type": agent_type, "last_assistant_message": text})

    def _send(self, message, to=TDD_ID):
        out = self._run({"hook_event_name": "PreToolUse", "tool_name": "SendMessage",
                         "tool_input": {"to": to, "message": message}})
        return (out or {}).get("hookSpecificOutput", {}).get("permissionDecision", "allow")

    def _bash(self, command, output):
        return self._run({"hook_event_name": "PostToolUse", "tool_name": "Bash",
                          "tool_input": {"command": command},
                          "tool_response": {"stdout": output, "stderr": ""}})

    def test_resume_without_review_is_denied(self):
        self._stop(GREEN)
        self.assertEqual(self._send("cleared, proceed to Refactor"), "deny")

    def test_other_agents_are_not_gated(self):
        self._stop(GREEN)
        self.assertEqual(self._send("hello", to="someoneelse"), "allow")
        self.assertEqual(self._send("hello"), "deny")

    def test_reviewer_agent_report_clears_gate(self):
        self._stop(GREEN)
        self._stop(REVIEW, agent_id="rev1", agent_type="code-reviewer:code-reviewer")
        self.assertEqual(self._send("cleared, proceed to Refactor"), "allow")

    def test_marker_from_a_non_reviewer_agent_does_not_clear(self):
        self._stop(GREEN)
        self._stop(f"The reviewer's report starts with {REVIEW}", agent_id="x", agent_type="Explore")
        self.assertEqual(self._send("proceed"), "deny")

    def test_headless_reviewer_output_clears_gate(self):
        self._stop(GREEN)
        self._bash('code-reviewer/scripts/review_headless.sh "mode: review-improve"', REVIEW)
        self.assertEqual(self._send("proceed"), "allow")

    def test_cat_of_agent_file_or_verifier_run_does_not_clear(self):
        self._stop(GREEN)
        self._bash("cat code-reviewer/agents/code-reviewer.md", REVIEW)
        self._bash("code-reviewer/scripts/review_headless.sh --agent finding-verifier x", REVIEW)
        self.assertEqual(self._send("proceed"), "deny")

    def test_explicit_labels_allow_a_recorded_bypass(self):
        self._stop(GREEN)
        for label in ("self-reviewed (no independent reviewer available: Agent blocked)",
                      "Review skipped per Slice Spec", "reviewed by: Dana (human)"):
            self.assertEqual(self._send(f"proceed. {label}"), "allow", label)

    def test_later_report_from_same_agent_closes_gate(self):
        self._stop(GREEN)
        self._stop(REFACTORED)
        self.assertEqual(self._send("next slice"), "allow")

    def test_new_pause_after_review_needs_a_new_review(self):
        self._stop(GREEN)
        self._stop(REVIEW, agent_id="rev1", agent_type="code-reviewer:code-reviewer")
        self._stop(GREEN)
        self.assertEqual(self._send("proceed"), "deny")

    def test_denial_reason_names_the_way_forward(self):
        self._stop(GREEN)
        out = self._run({"hook_event_name": "PreToolUse", "tool_name": "SendMessage",
                         "tool_input": {"to": TDD_ID, "message": "go"}})
        reason = out["hookSpecificOutput"]["permissionDecisionReason"]
        self.assertIn("code-reviewer:code-reviewer", reason)
        self.assertIn("self-reviewed", reason)


if __name__ == "__main__":
    unittest.main()
