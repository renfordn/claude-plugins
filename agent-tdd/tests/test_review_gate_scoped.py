"""Scoped review gates: a review scoped to slice N clears only slice N's gate."""
import json
import os
import subprocess
import sys
import tempfile
import unittest

HOOK = os.path.join(os.path.dirname(__file__), "..", "hooks", "review_gate.py")
A3, A4 = "agent3aaaaaaaaaaaa", "agent4bbbbbbbbbbbb"


def green(n):
    return ("<!--AGENT-TDD-REPORT-->\n<!--AGENT-TDD-PHASE:green_pause-->\n"
            f"**Plan**\nSlice {n}: do thing")


def review(scope=None):
    marker = f"<!--REVIEW-SCOPE: slice={scope}-->\n" if scope else ""
    return f"<!--CODE-REVIEWER-REPORT-->\n{marker}**Verdict**: clear"


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


class ScopedGateTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.cwd = os.path.join(self._tmp.name, "project")
        os.makedirs(self.cwd)
        self.env = {k: v for k, v in os.environ.items()
                    if k != "CLAUDE_PLUGIN_OPTION_SHARED_MEMORY_ROOT"}
        self.env.update(CLAUDE_PLUGIN_DATA=os.path.join(self._tmp.name, "data"),
                        CLAUDE_CONFIG_DIR=os.path.join(self._tmp.name, "cfg"))

    def tearDown(self):
        self._tmp.cleanup()

    def _run(self, payload, cwd=None):
        payload.setdefault("cwd", cwd or self.cwd)
        r = subprocess.run([sys.executable, HOOK], input=json.dumps(payload),
                           capture_output=True, text=True, env=self.env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("[review_gate]", r.stderr)
        return json.loads(r.stdout) if r.stdout.strip() else None

    def _stop(self, text, agent_id, agent_type="agent-tdd:agent-TDD", cwd=None):
        return self._run({"hook_event_name": "SubagentStop", "agent_id": agent_id,
                          "agent_type": agent_type, "last_assistant_message": text}, cwd)

    def _reviewer(self, text):
        return self._stop(text, "rev", "code-reviewer:code-reviewer")

    def _send(self, to, cwd=None):
        out = self._run({"hook_event_name": "PreToolUse", "tool_name": "SendMessage",
                         "tool_input": {"to": to, "message": "proceed"}}, cwd)
        return (out or {}).get("hookSpecificOutput", {}).get("permissionDecision", "allow")

    def _open_two(self):
        self._stop(green(3), A3)
        self._stop(green(4), A4)

    def test_scoped_reviewer_report_clears_only_its_slice(self):
        self._open_two()
        self._reviewer(review(3))
        self.assertEqual(self._send(A3), "allow")
        self.assertEqual(self._send(A4), "deny")

    def test_scoped_headless_output_clears_only_its_slice(self):
        self._open_two()
        self._run({"hook_event_name": "PostToolUse", "tool_name": "Bash",
                   "tool_input": {"command": "code-reviewer/scripts/review_headless.sh x"},
                   "tool_response": {"stdout": review(4), "stderr": ""}})
        self.assertEqual(self._send(A4), "allow")
        self.assertEqual(self._send(A3), "deny")

    def test_unscoped_with_two_open_gates_clears_none_and_warns(self):
        self._open_two()
        out = self._reviewer(review())
        self.assertIn("unscoped", json.dumps(out).lower())
        self.assertEqual(self._send(A3), "deny")
        self.assertEqual(self._send(A4), "deny")

    def test_unscoped_with_one_open_gate_clears_it(self):
        self._stop(green(3), A3)
        self._reviewer(review())
        self.assertEqual(self._send(A3), "allow")

    def test_gate_from_worktree_visible_from_main_checkout(self):
        main = os.path.join(self._tmp.name, "repo")
        os.makedirs(main)
        _git(main, "init", "-q")
        _git(main, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q",
             "--allow-empty", "-m", "i")
        wt = os.path.join(self._tmp.name, "wt")
        _git(main, "worktree", "add", "-q", wt, "-b", "wtb")
        self._stop(green(3), A3, cwd=wt)
        self.assertEqual(self._send(A3, cwd=main), "deny")

    def test_prose_slice_mention_is_not_recorded_as_the_slice(self):
        text = ("<!--AGENT-TDD-REPORT-->\n<!--AGENT-TDD-PHASE:green_pause-->\n"
                "**Plan** Reuses Slice 1 helpers. Slice 2: y")
        self._stop(text, A3)
        out = self._reviewer(review(1))
        self.assertEqual(self._send(A3), "deny")
        self.assertIn("slice", json.dumps(out).lower())

    def test_explicit_slice_id_marker_is_recorded(self):
        text = ("<!--AGENT-TDD-REPORT-->\n<!--AGENT-TDD-PHASE:green_pause-->\n"
                "<!--SLICE-ID: 7-->\n**Plan** Reuses Slice 1 helpers.")
        self._stop(text, A3)
        self._reviewer(review(7))
        self.assertEqual(self._send(A3), "allow")

    def test_title_line_slice_is_recorded(self):
        text = ("<!--AGENT-TDD-REPORT-->\n<!--AGENT-TDD-PHASE:green_pause-->\n"
                "## Slice 5: thing\nSee Slice 1.")
        self._stop(text, A3)
        self._reviewer(review(5))
        self.assertEqual(self._send(A3), "allow")

    def test_scoped_review_matching_no_gate_lists_open_slices(self):
        self._open_two()
        out = self._reviewer(review(9))
        msg = json.dumps(out)
        self.assertIn("3", msg)
        self.assertIn("4", msg)
        self.assertEqual(self._send(A3), "deny")

    def test_scoped_review_with_null_slice_gate_warns_and_keeps_gate(self):
        self._stop("<!--AGENT-TDD-REPORT-->\n<!--AGENT-TDD-PHASE:green_pause-->\nno id", A3)
        out = self._reviewer(review(3))
        self.assertIn("none", json.dumps(out).lower())
        self.assertEqual(self._send(A3), "deny")

    def test_headless_string_tool_response_scope_is_read(self):
        self._open_two()
        self._run({"hook_event_name": "PostToolUse", "tool_name": "Bash",
                   "tool_input": {"command": "code-reviewer/scripts/review_headless.sh x"},
                   "tool_response": review(3)})
        self.assertEqual(self._send(A3), "allow")
        self.assertEqual(self._send(A4), "deny")

    def test_headless_missing_tool_response_falls_back_to_raw_payload(self):
        self._open_two()
        self._run({"hook_event_name": "PostToolUse", "tool_name": "Bash",
                   "tool_input": {"command": "code-reviewer/scripts/review_headless.sh x"},
                   "output": review(4)})
        self.assertEqual(self._send(A4), "allow")
        self.assertEqual(self._send(A3), "deny")
