"""SubagentStop hook: coverage/bypass tokens, OUTCOME and BLOCKED markers (release 3, slice 1C)."""
import datetime
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOOK = ROOT / "hooks" / "tdd_subagent_stop.py"
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "hooks"))
import tdd_check  # noqa: E402
from tdd_state import progress_path  # noqa: E402

HEAD = "<!--AGENT-TDD-REPORT-->\n<!--AGENT-TDD-PHASE:green_pause-->\n"
BLOCKED_HEAD = "<!--AGENT-TDD-REPORT-->\n"  # a BLOCKED report carries no phase marker
WARN = "Red→Green was not verified"
COV_ONLY = "<!--AGENT-TDD-OUTCOME: coverage-only-->\n"


class OutcomeTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = self._tmp.name
        subprocess.run(["git", "init", "-q"], cwd=self.repo, check=True)

    def tearDown(self):
        self._tmp.cleanup()

    def _log(self, phase, confirmed=True, **extra):
        entry = {"phase": phase, "token": os.urandom(4).hex(), "at": datetime.datetime.now().isoformat(timespec="seconds"),
                 "worktree": os.path.realpath(self.repo), "slice": "Slice 1C: t", "confirmed": confirmed}
        entry.update(extra)
        self.assertTrue(tdd_check._append(entry, self.repo))
        return entry["token"]

    def _cov(self, confirmed=True):
        return self._log("coverage", confirmed, cmd="pytest t", mutant="sed m", exit=0,
                         mutant_exit=1 if confirmed else 0, note="" if confirmed else "mutant survived")

    def _rg(self):
        r = self._log("red", cmd="pytest t", exit=1, note="")
        g = self._log("green", cmd="pytest t", exit=0, note="")
        return f"TDD-EVIDENCE red {r} exit=1 CONFIRMED\nTDD-EVIDENCE green {g} exit=0 CONFIRMED\n"

    def _hook(self, report):
        r = subprocess.run([sys.executable, str(HOOK)], cwd=self.repo, capture_output=True, text=True,
                           input=json.dumps({"cwd": self.repo, "last_assistant_message": report}))
        return json.loads(r.stdout)["systemMessage"]

    def _slices(self):
        with open(progress_path(self.repo)) as fh:
            return json.load(fh)["slices"]

    def test_coverage_only_with_verified_token_does_not_warn(self):
        t = self._cov()
        msg = self._hook(HEAD + COV_ONLY + f"**Plan**\nPin it\nTDD-EVIDENCE coverage {t} exit=0 CONFIRMED\n")
        self.assertIn("coverage=verified", msg)
        self.assertIn("red=", msg)
        self.assertNotIn(WARN, msg)

    def test_coverage_token_without_outcome_marker_still_warns(self):
        t = self._cov()
        msg = self._hook(HEAD + f"**Plan**\nPin it\nTDD-EVIDENCE coverage {t} exit=0 CONFIRMED\n")
        self.assertIn("coverage=verified", msg)
        self.assertIn(WARN, msg)

    def test_coverage_only_with_unconfirmed_coverage_warns(self):
        t = self._cov(confirmed=False)
        msg = self._hook(HEAD + COV_ONLY + f"**Plan**\nPin it\nTDD-EVIDENCE coverage {t} exit=0 NOT CONFIRMED (x)\n")
        self.assertIn("coverage=not confirmed", msg)
        self.assertIn(WARN, msg)

    def test_bare_token_line_is_still_looked_up(self):
        t = self._cov()
        msg = self._hook(HEAD + COV_ONLY + f"**Plan**\nPin it\nTDD-EVIDENCE coverage {t}\n")
        self.assertIn("coverage=verified", msg)
        self.assertNotIn(WARN, msg)

    def test_bypass_shows_logged_reason_and_alone_still_warns(self):
        t = self._log("bypass", reason="docs only")
        msg = self._hook(HEAD + f"**Plan**\nDocs\nTDD-EVIDENCE bypass {t} CONFIRMED\n")
        self.assertIn("bypass=docs only", msg)
        self.assertIn(WARN, msg)

    def test_bypass_with_verified_red_green_does_not_warn(self):
        t = self._log("bypass", reason="docs only")
        msg = self._hook(HEAD + f"**Plan**\nDocs\n{self._rg()}TDD-EVIDENCE bypass {t} CONFIRMED\n")
        self.assertIn("bypass=docs only", msg)
        self.assertNotIn(WARN, msg)

    def test_blocked_shows_reason_suppresses_warning_and_is_not_green_pending_review(self):
        msg = self._hook(BLOCKED_HEAD + '**Plan**\nX\n<!--AGENT-TDD-BLOCKED: reason="needs product call"-->\n')
        self.assertIn("blocked: needs product call", msg)
        self.assertIn("[blocked]", msg)
        self.assertNotIn(WARN, msg)
        self.assertEqual(self._slices()[-1]["status"], "blocked")

    def test_blocked_marker_without_reason_still_blocks(self):
        msg = self._hook(BLOCKED_HEAD + "**Plan**\nX\n<!--AGENT-TDD-BLOCKED-->\n")
        self.assertIn("blocked:", msg)
        self.assertEqual(self._slices()[-1]["status"], "blocked")

    def test_retried_unnumbered_blocked_slice_updates_its_row(self):
        self._hook(BLOCKED_HEAD + '**Plan**\nSame work\n<!--AGENT-TDD-BLOCKED: reason="r"-->\n')
        self._hook(HEAD + "**Plan**\nSame work\n")
        slices = self._slices()
        self.assertEqual(len(slices), 1)
        self.assertEqual(slices[0]["status"], "green_pending_review")


if __name__ == "__main__":
    unittest.main()
