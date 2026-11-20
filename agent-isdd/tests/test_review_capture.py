"""Review capture: scope lists, the prompt's `Review scope:` line as a fallback, and a warning
when a code-reviewer stop records nothing (so a missed scope is never silent)."""
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hooks"))

import high_risk_reviewer
import isdd_markers as markers
import review_tracking

TASKS = """# Tasks

## Slice 2: tokens
**Risk Tier:** high-risk

## Slice 3: gate
**Risk Tier:** high-risk

## Slice 7: client
**Risk Tier:** standard

## Slice 11: server
**Risk Tier:** high-risk
"""

REPORT = "<!--CODE-REVIEWER-REPORT-->\nverdict: clear"
CR = "code-reviewer:code-reviewer"


def make_feature(tmp):
    os.makedirs(os.path.join(tmp, "tasks"))
    with open(os.path.join(tmp, "tasks", "tasks.md"), "w") as fh:
        fh.write(TASKS)
    with open(os.path.join(tmp, "workflow-state.md"), "w") as fh:
        fh.write("- Workflow Status: In Progress\n- Review Fallback: None\n")
    return os.path.join(tmp, "workflow-state.json")


def transcript(tmp, prompt, report, prompt_as_blocks=False):
    """A subagent transcript: the caller's prompt as the first user message, the report last."""
    content = [{"type": "text", "text": prompt}] if prompt_as_blocks else prompt
    path = os.path.join(tmp, "agent.jsonl")
    with open(path, "w") as fh:
        fh.write(json.dumps({"type": "user", "message": {"role": "user", "content": content}}) + "\n")
        fh.write(json.dumps({"type": "assistant", "message": {
            "role": "assistant", "content": [{"type": "text", "text": report}]}}) + "\n")
    return path


def reviewed(js):
    if not os.path.exists(js):
        return {}
    with open(js) as fh:
        return json.load(fh).get("reviewed", {})


class ScopeParsing(unittest.TestCase):
    def test_list_and_repeated_markers(self):
        self.assertEqual(markers.parse_review_scopes("<!--REVIEW-SCOPE: slice=2, 3,11b-->"), ["2", "3", "11B"])
        text = "<!--REVIEW-SCOPE: slice=2-->\nx\n<!-- REVIEW-SCOPE: slice=3 -->"
        self.assertEqual(markers.parse_review_scopes(text), ["2", "3"])
        self.assertEqual(markers.parse_review_scopes("no marker, Slice 3 in prose"), [])

    def test_single_parser_unchanged(self):
        self.assertEqual(markers.parse_review_scope("<!--REVIEW-SCOPE: slice=4-->"), "4")
        self.assertIsNone(markers.parse_review_scope("<!--REVIEW-SCOPE: slice=2,3-->"))

    def test_prompt_scope_lines(self):
        self.assertEqual(markers.parse_prompt_review_scopes("Gate.\nReview scope: slice=2,3\nFocus: x"), ["2", "3"])
        self.assertEqual(markers.parse_prompt_review_scopes("Review scope: slice=9\nReview scope: slice=10"), ["9", "10"])
        self.assertEqual(markers.parse_prompt_review_scopes("Review Slice 3 (gate) deeply"), [])
        self.assertEqual(markers.parse_prompt_review_scopes("see `Review scope: slice=4` in docs"), [])


class Capture(unittest.TestCase):
    def test_report_list_records_every_slice(self):
        with tempfile.TemporaryDirectory() as tmp:
            js = make_feature(tmp)
            msg = "<!--REVIEW-SCOPE: slice=2,3-->\n" + REPORT
            got = review_tracking.record_from_payload({"agent_type": CR, "last_assistant_message": msg}, js)
            self.assertEqual(got, ["2", "3"])
            self.assertEqual(reviewed(js), {"2": True, "3": True})

    def test_prompt_scope_is_the_fallback_when_the_report_has_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            js = make_feature(tmp)
            tp = transcript(tmp, "Gate: green pause.\nReview scope: slice=11\nScope: server.py", REPORT,
                            prompt_as_blocks=True)
            got = review_tracking.record_from_payload({"agent_type": CR, "agent_transcript_path": tp}, js)
            self.assertEqual(got, ["11"])
            self.assertEqual(reviewed(js), {"11": True})

    def test_report_scope_wins_over_prompt(self):
        with tempfile.TemporaryDirectory() as tmp:
            js = make_feature(tmp)
            tp = transcript(tmp, "Review scope: slice=2,3", "<!--REVIEW-SCOPE: slice=2-->\n" + REPORT)
            review_tracking.record_from_payload({"agent_type": CR, "agent_transcript_path": tp}, js)
            self.assertEqual(reviewed(js), {"2": True})

    def test_prose_slice_names_never_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            js = make_feature(tmp)
            tp = transcript(tmp, "Deep review of Slice 3 (gate) and Slice 2.", REPORT)
            self.assertEqual(review_tracking.record_from_payload({"agent_type": CR, "agent_transcript_path": tp}, js), [])
            self.assertEqual(reviewed(js), {})

    def test_other_agents_never_record_from_prompt(self):
        with tempfile.TemporaryDirectory() as tmp:
            js = make_feature(tmp)
            tp = transcript(tmp, "Review scope: slice=2", REPORT)
            review_tracking.record_from_payload({"agent_type": "agent-tdd:agent-TDD", "agent_transcript_path": tp}, js)
            self.assertEqual(reviewed(js), {})


class Warning(unittest.TestCase):
    def _evaluate(self, tmp, payload):
        md = os.path.join(tmp, "workflow-state.md")
        with mock.patch.object(review_tracking.sdd_state, "active_state_file", return_value=md):
            return review_tracking.evaluate(payload)

    def test_unscoped_review_warns_with_the_missing_slices(self):
        with tempfile.TemporaryDirectory() as tmp:
            make_feature(tmp)
            note = self._evaluate(tmp, {"agent_type": CR, "last_assistant_message": REPORT})
            self.assertIn("recorded no slice", note)
            self.assertIn("Review scope: slice=", note)
            for sid in ("2", "3", "11"):
                self.assertIn(sid, note)

    def test_scoped_review_and_pre_push_are_quiet(self):
        with tempfile.TemporaryDirectory() as tmp:
            make_feature(tmp)
            scoped = "<!--REVIEW-SCOPE: slice=2-->\n" + REPORT
            self.assertIsNone(self._evaluate(tmp, {"agent_type": CR, "last_assistant_message": scoped}))
            pre_push = "<!--PRE-PUSH-REVIEW-->\n" + REPORT
            self.assertIsNone(self._evaluate(tmp, {"agent_type": CR, "last_assistant_message": pre_push}))
            self.assertIsNone(self._evaluate(tmp, {"agent_type": "agent-tdd:agent-TDD", "last_assistant_message": REPORT}))

    def test_quiet_when_nothing_is_left_to_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            js = make_feature(tmp)
            for sid in ("2", "3", "11"):
                review_tracking.record_review(js, sid)
            self.assertIsNone(self._evaluate(tmp, {"agent_type": CR, "last_assistant_message": REPORT}))

    def test_high_risk_reviewer_surfaces_the_warning(self):
        with tempfile.TemporaryDirectory() as tmp:
            make_feature(tmp)
            md = os.path.join(tmp, "workflow-state.md")
            with mock.patch.object(review_tracking.sdd_state, "active_state_file", return_value=md), \
                    mock.patch.object(high_risk_reviewer, "active_state_file", return_value=md):
                msg = high_risk_reviewer.main({"agent_type": CR, "last_assistant_message": REPORT, "cwd": tmp})
            self.assertIn("recorded no slice", msg or "")


if __name__ == "__main__":
    unittest.main()
