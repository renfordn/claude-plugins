"""Tests for scripts/tdd_check.py and the evidence check in hooks/tdd_subagent_stop.py.

Red must fail, Green must pass after a confirmed Red for the same slice, every run is logged in
<git dir>/agent-tdd/evidence.jsonl, and the SubagentStop hook reports whether a handoff report's
TDD-EVIDENCE tokens are real log entries rather than typed-out claims.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "tdd_check.py"
HOOK = ROOT / "hooks" / "tdd_subagent_stop.py"
sys.path.insert(0, str(ROOT / "scripts"))
import tdd_check  # noqa: E402

PASS = [sys.executable, "-c", "import sys; sys.exit(0)"]
FAIL = [sys.executable, "-c", "import sys; print('AssertionError: expected 3'); sys.exit(1)"]


def _check(repo, phase, slice_title, cmd):
    r = subprocess.run([sys.executable, str(SCRIPT), phase, "--slice", slice_title, "--", *cmd],
                       cwd=repo, capture_output=True, text=True)
    token_line = [l for l in r.stdout.splitlines() if l.startswith("TDD-EVIDENCE")][-1]
    return r.returncode, token_line


def _token(line):
    return line.split()[2]


class TddCheckTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = self._tmp.name
        subprocess.run(["git", "init", "-q"], cwd=self.repo, check=True)

    def tearDown(self):
        self._tmp.cleanup()

    def test_red_confirms_only_a_failing_test(self):
        rc, line = _check(self.repo, "red", "adds totals", FAIL)
        self.assertEqual(rc, 0)
        self.assertIn("red", line)
        self.assertTrue(line.endswith("CONFIRMED") and "NOT" not in line)
        rc, line = _check(self.repo, "red", "adds totals", PASS)
        self.assertEqual(rc, 1)
        self.assertIn("NOT CONFIRMED (test passed before implementation)", line)

    def test_green_needs_a_prior_confirmed_red_for_the_same_slice(self):
        rc, line = _check(self.repo, "green", "adds totals", PASS)
        self.assertEqual(rc, 1)
        self.assertIn("no verified red", line)
        _check(self.repo, "red", "adds totals", FAIL)
        rc, line = _check(self.repo, "green", "other slice", PASS)
        self.assertEqual(rc, 1)
        rc, line = _check(self.repo, "green", "adds totals", PASS)
        self.assertEqual(rc, 0)
        self.assertIn("CONFIRMED", line)

    def test_green_still_failing_is_not_confirmed(self):
        _check(self.repo, "red", "s", FAIL)
        rc, line = _check(self.repo, "green", "s", FAIL)
        self.assertEqual(rc, 1)
        self.assertIn("tests still fail", line)

    def test_every_run_is_logged_with_its_token(self):
        _, line = _check(self.repo, "red", "s", FAIL)
        entries = tdd_check.read_log(self.repo)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["token"], _token(line))
        self.assertEqual(entries[0]["exit"], 1)
        self.assertTrue(os.path.isfile(os.path.join(self.repo, ".git", "agent-tdd", "evidence.jsonl")))

    def test_outside_git_runs_but_says_unrecorded(self):
        with tempfile.TemporaryDirectory() as plain:
            rc, line = _check(plain, "red", "s", FAIL)
            self.assertEqual(rc, 0)
            self.assertIn("[unrecorded: not a git repo]", line)

    def _hook(self, report):
        r = subprocess.run([sys.executable, str(HOOK)], cwd=self.repo, capture_output=True, text=True,
                           input=json.dumps({"cwd": self.repo, "last_assistant_message": report}))
        return json.loads(r.stdout)["systemMessage"]

    def test_hook_marks_real_tokens_verified(self):
        _, red = _check(self.repo, "red", "s", FAIL)
        _, green = _check(self.repo, "green", "s", PASS)
        report = (f"<!--AGENT-TDD-REPORT-->\n<!--AGENT-TDD-PHASE:green_pause-->\n**Plan**\nAdd totals\n"
                  f"**Validation Evidence**\n{red}\n{green}\n")
        msg = self._hook(report)
        self.assertIn("red=verified green=verified", msg)
        self.assertNotIn("⚠", msg)

    def test_hook_flags_missing_and_invented_tokens(self):
        report = ("<!--AGENT-TDD-REPORT-->\n<!--AGENT-TDD-PHASE:green_pause-->\n**Plan**\nAdd totals\n"
                  "**Validation Evidence**\nTDD-EVIDENCE red deadbeef exit=1 CONFIRMED\n")
        msg = self._hook(report)
        self.assertIn("red=unrecorded green=missing", msg)
        self.assertIn("⚠ Red→Green was not verified", msg)


class AgentDocTests(unittest.TestCase):
    def test_agent_uses_the_checker_and_stays_small(self):
        doc = (ROOT / "agents" / "agent-TDD.md").read_text()
        self.assertIn("tdd_check.py\" red", doc)
        self.assertIn("tdd_check.py\" green", doc)
        self.assertIn("TDD-EVIDENCE", doc)
        self.assertLess(len(doc.splitlines()), 300, "agent-TDD.md is loaded on every spawn; keep it lean")

    def test_report_markers_the_hooks_parse_are_documented(self):
        doc = (ROOT / "agents" / "agent-TDD.md").read_text()
        for marker in ("<!--AGENT-TDD-REPORT-->", "<!--AGENT-TDD-PHASE:green_pause-->",
                       "refactor_complete", "slicing_complete", "all_slices_complete",
                       "<!--AGENT-TDD-PLAN-FLAG:reason=", "<!--AGENT-TDD-MODEL-ESCALATE:reason="):
            self.assertIn(marker, doc)

    def test_tdd_command_drives_the_review_pause(self):
        cmd = (ROOT / "commands" / "tdd.md").read_text()
        for needle in ("agent-tdd:slice-spec", "agent-tdd:agent-TDD", "Independent review", "SendMessage",
                       "red=… green=…"):
            self.assertIn(needle, cmd)


if __name__ == "__main__":
    unittest.main()
