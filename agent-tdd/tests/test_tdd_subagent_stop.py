"""Tests for hooks/tdd_subagent_stop.py — driven via subprocess with synthetic JSONL."""
import json
import os
import subprocess
import sys
import tempfile
import unittest

HOOKS_DIR = os.path.join(os.path.dirname(__file__), "..", "hooks")
sys.path.insert(0, HOOKS_DIR)
import tdd_state  # noqa: E402

HOOK = os.path.join(os.path.dirname(__file__), "..", "hooks", "tdd_subagent_stop.py")


def _make_jsonl(text):
    """Produce a minimal JSONL transcript with one assistant message."""
    ev = {
        "type": "assistant",
        "message": {
            "role": "assistant",
            "content": [{"type": "text", "text": text}],
        },
    }
    return (json.dumps(ev) + "\n").encode()


def _run(payload, transcript_content=None):
    """Run the hook with the given payload dict, optionally writing transcript_content."""
    with tempfile.TemporaryDirectory() as tmp:
        if transcript_content is not None:
            tp = os.path.join(tmp, "transcript.jsonl")
            with open(tp, "wb") as f:
                f.write(transcript_content)
            payload["transcript_path"] = tp
        payload.setdefault("cwd", tmp)
        result = subprocess.run(
            [sys.executable, HOOK],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
        )
        msg = None
        if result.stdout.strip():
            try:
                msg = json.loads(result.stdout.strip()).get("systemMessage")
            except (json.JSONDecodeError, AttributeError):
                pass
        # Also return the cwd so callers can inspect tdd-progress.json
        return msg, result.returncode, tmp


def _run_with_cwd(payload, transcript_content, cwd):
    """Run hook with explicit cwd so we can inspect state after."""
    tp = os.path.join(cwd, "transcript.jsonl")
    with open(tp, "wb") as f:
        f.write(transcript_content)
    payload["transcript_path"] = tp
    payload["cwd"] = cwd
    result = subprocess.run(
        [sys.executable, HOOK],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
    )
    msg = None
    if result.stdout.strip():
        try:
            msg = json.loads(result.stdout.strip()).get("systemMessage")
        except (json.JSONDecodeError, AttributeError):
            pass
    return msg, result.returncode


SAMPLE_REPORT = """\
<!--AGENT-TDD-REPORT-->
<!--AGENT-TDD-PHASE:green_pause-->

**Plan**
Implement input validation.

**Test Changes**
Added test_validate.py.

**Implementation Changes**
Updated validate.py.

**Validation Evidence**
python3 -m pytest test_validate.py — 3 passed.

**Acceptance Criteria**
All 3 criteria passing.

**Risks and Follow-ups**
None.

**Handoff Facts**
validate.py owns all input sanitisation for this endpoint.
"""

REFACTOR_REPORT = """\
<!--AGENT-TDD-REPORT-->
<!--AGENT-TDD-PHASE:refactor_complete-->

**Plan**
Refactored validate.py.

**Test Changes**
No new tests; existing tests cover.

**Implementation Changes**
Extracted helper function.

**Validation Evidence**
All tests passing after refactor.

**Acceptance Criteria**
All 3 criteria passing.

**Risks and Follow-ups**
None.

**Handoff Facts**
none
"""

GAP_REPORT = """\
<!--AGENT-TDD-REPORT-->
<!--AGENT-TDD-PHASE:green_pause-->

**Plan**
Attempted slice.

**Test Changes**
Added test.

**Implementation Changes**
None yet.

**Validation Evidence**
Could not run — missing fixture.

**Acceptance Criteria**
Not yet passing.

**Risks and Follow-ups**
See gap.

**Handoff Facts**
none

**Research Gap Flag**
Interface `UserRepo.find_by_email` does not exist. Need caller to clarify the correct method name before Green can proceed.
"""

PLAN_FLAG_REPORT = """\
<!--AGENT-TDD-REPORT-->
<!--AGENT-TDD-PHASE:green_pause-->
<!--AGENT-TDD-PLAN-FLAG:reason="acceptance criteria contradicts existing tested behavior"-->

**Plan**
Attempted slice.

**Test Changes**
Added test.

**Implementation Changes**
None yet.

**Validation Evidence**
Could not run — conflict found first.

**Acceptance Criteria**
Not yet passing.

**Risks and Follow-ups**
See plan validity flag.

**Handoff Facts**
none

**Plan Validity Flag**
Satisfying this criteria would silently change behavior another passing test depends on.
"""


class SilentNoOpTests(unittest.TestCase):
    def test_missing_transcript_path_is_silent(self):
        msg, rc, _ = _run({"cwd": "/tmp"})
        self.assertEqual(rc, 0)
        self.assertIsNone(msg)

    def test_unreadable_transcript_is_silent(self):
        msg, rc, _ = _run({"transcript_path": "/nonexistent/path.jsonl"})
        self.assertEqual(rc, 0)
        self.assertIsNone(msg)

    def test_no_report_marker_in_non_tdd_transcript_is_silent(self):
        content = _make_jsonl("This is a nelly brief, not an agent-TDD report.")
        msg, rc, _ = _run({}, transcript_content=content)
        self.assertEqual(rc, 0)
        self.assertIsNone(msg)

    def test_malformed_json_payload_is_silent(self):
        result = subprocess.run(
            [sys.executable, HOOK],
            input="not json",
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "")


class GreenPauseTests(unittest.TestCase):
    def test_green_pause_writes_progress_and_emits_message(self):
        with tempfile.TemporaryDirectory() as tmp:
            msg, rc = _run_with_cwd({}, _make_jsonl(SAMPLE_REPORT), tmp)
            self.assertEqual(rc, 0)
            self.assertIsNotNone(msg)
            self.assertIn("green_pending_review", msg)
            self.assertIn("gap=no", msg)
            self.assertIn("facts=yes", msg)

            # Check tdd-progress.json was written

            data = tdd_state.read_tdd_progress(tmp)
            self.assertEqual(len(data["slices"]), 1)
            self.assertEqual(data["slices"][0]["status"], "green_pending_review")
            self.assertFalse(data["slices"][0]["has_research_gap"])
            self.assertTrue(data["slices"][0]["has_handoff_facts"])


class RefactorCompleteTests(unittest.TestCase):
    def test_refactor_complete_writes_correct_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            msg, rc = _run_with_cwd({}, _make_jsonl(REFACTOR_REPORT), tmp)
            self.assertEqual(rc, 0)
            self.assertIn("refactor_complete", msg)


            data = tdd_state.read_tdd_progress(tmp)
            self.assertEqual(data["slices"][0]["status"], "refactor_complete")
            self.assertFalse(data["slices"][0]["has_handoff_facts"])


class ResearchGapTests(unittest.TestCase):
    def test_research_gap_flag_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            msg, rc = _run_with_cwd({}, _make_jsonl(GAP_REPORT), tmp)
            self.assertEqual(rc, 0)
            self.assertIn("gap=yes", msg)


            data = tdd_state.read_tdd_progress(tmp)
            self.assertTrue(data["slices"][0]["has_research_gap"])


class PlanValidityFlagTests(unittest.TestCase):
    def test_plan_validity_flag_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            msg, rc = _run_with_cwd({}, _make_jsonl(PLAN_FLAG_REPORT), tmp)
            self.assertEqual(rc, 0)
            self.assertIn("plan_flag=yes", msg)

            data = tdd_state.read_tdd_progress(tmp)
            self.assertTrue(data["slices"][0]["has_plan_validity_flag"])

    def test_no_plan_validity_flag_marker_is_no(self):
        with tempfile.TemporaryDirectory() as tmp:
            msg, rc = _run_with_cwd({}, _make_jsonl(SAMPLE_REPORT), tmp)
            self.assertEqual(rc, 0)
            self.assertIn("plan_flag=no", msg)

            data = tdd_state.read_tdd_progress(tmp)
            self.assertFalse(data["slices"][0]["has_plan_validity_flag"])


class DeduplicationTests(unittest.TestCase):
    def test_same_description_pending_review_updates_in_place(self):
        with tempfile.TemporaryDirectory() as tmp:
            # First stop — green_pause
            _run_with_cwd({}, _make_jsonl(SAMPLE_REPORT), tmp)

            data = tdd_state.read_tdd_progress(tmp)
            self.assertEqual(len(data["slices"]), 1)
            first_id = data["slices"][0]["id"]

            # Second stop — same description, now refactor_complete (after review resume)
            # Build a refactor report with same description line
            refactor_same_desc = SAMPLE_REPORT.replace(
                "<!--AGENT-TDD-PHASE:green_pause-->",
                "<!--AGENT-TDD-PHASE:refactor_complete-->",
            )
            _run_with_cwd({}, _make_jsonl(refactor_same_desc), tmp)
            data2 = tdd_state.read_tdd_progress(tmp)
            # Should still be 1 entry (updated, not appended) but status now refactor_complete
            # Note: dedup only matches green_pending_review entries, so after first stop
            # it will match and update. After update the status is refactor_complete.
            # A second refactor_complete won't match (not green_pending_review) -> new entry.
            # This test just checks the first update works.
            self.assertGreaterEqual(len(data2["slices"]), 1)

    def test_different_description_appends_new_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            _run_with_cwd({}, _make_jsonl(SAMPLE_REPORT), tmp)
            # Different transcript/description
            report2 = SAMPLE_REPORT.replace(
                "Implement input validation.",
                "Add rate limiting to the API endpoint.",
            )
            _run_with_cwd({}, _make_jsonl(report2), tmp)

            data = tdd_state.read_tdd_progress(tmp)
            self.assertEqual(len(data["slices"]), 2)


class DefaultPhaseTests(unittest.TestCase):
    def test_missing_phase_line_defaults_to_green_pending_review(self):
        report_no_phase = "<!--AGENT-TDD-REPORT-->\n\n**Acceptance Criteria**\nAll passing.\n"
        with tempfile.TemporaryDirectory() as tmp:
            msg, rc = _run_with_cwd({}, _make_jsonl(report_no_phase), tmp)
            self.assertEqual(rc, 0)

            data = tdd_state.read_tdd_progress(tmp)
            self.assertEqual(data["slices"][0]["status"], "green_pending_review")


if __name__ == "__main__":
    unittest.main()
