import json
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hooks"))

import review_tracking

TASKS = """# Tasks

## Slice 1: a
**Risk Tier:** high-risk
**Files:** `a.py`

## Slice 2F2: b
**Risk Tier:** standard

## Slice 3b: c
**Risk Tier:** high-risk

## Phase 4: legacy
### Risk Tier
- `high-risk`
"""


def make_feature(tmp, fallback="None"):
    os.makedirs(os.path.join(tmp, "tasks"))
    with open(os.path.join(tmp, "tasks", "tasks.md"), "w") as fh:
        fh.write(TASKS)
    with open(os.path.join(tmp, "workflow-state.md"), "w") as fh:
        fh.write("- Review Fallback: %s\n" % fallback)
    return os.path.join(tmp, "workflow-state.json")


class ReviewTrackingTests(unittest.TestCase):
    def test_high_risk_slices_alnum_ids(self):
        self.assertEqual(review_tracking.high_risk_slices(TASKS), ["1", "3B", "4"])

    def test_high_risk_slices_empty(self):
        self.assertEqual(review_tracking.high_risk_slices(""), [])

    def test_code_reviewer_filter_requires_type_and_report_marker(self):
        f = review_tracking.is_code_reviewer_stop
        m = {"last_assistant_message": "<!--CODE-REVIEWER-REPORT-->\nok"}
        self.assertTrue(f(dict(m, agent_type="code-reviewer:code-reviewer")))
        self.assertTrue(f(dict(m, agent_type="code-reviewer")))
        self.assertTrue(f(dict(m, agent_type="x:Code-Reviewer")))
        self.assertFalse(f(dict(m, agent_type="agent-tdd:agent-TDD")))
        self.assertFalse(f(dict(m, agent_type="x:not-code-reviewer")))
        self.assertFalse(f({"agent_type": "code-reviewer", "last_assistant_message": "<!--REVIEW-SCOPE: slice=1-->"}))
        self.assertFalse(f({}))

    def test_risk_tier_case_insensitive_and_h3_headings(self):
        text = "### Slice 5: x\n**Risk Tier:** High-risk\n\n## Slice 6: y\n**Risk Tier:** HIGH-RISK\n"
        self.assertEqual(review_tracking.high_risk_slices(text), ["5", "6"])

    def test_record_and_unreviewed(self):
        with tempfile.TemporaryDirectory() as tmp:
            js = make_feature(tmp)
            self.assertEqual(review_tracking.unreviewed_high_risk(tmp), ["1", "3B", "4"])
            review_tracking.record_review(js, "3b")
            with open(js) as fh:
                self.assertTrue(json.load(fh)["reviewed"]["3B"])
            self.assertEqual(review_tracking.unreviewed_high_risk(tmp), ["1", "4"])

    def test_review_fallback_explicit_all(self):
        with tempfile.TemporaryDirectory() as tmp:
            make_feature(tmp, fallback="Accepted via AskUserQuestion: all: no reviewer available")
            self.assertEqual(review_tracking.unreviewed_high_risk(tmp), [])

    def test_review_fallback_named_slices_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            make_feature(tmp, fallback="Accepted via AskUserQuestion: 1, 3b: reviewer down")
            self.assertEqual(review_tracking.unreviewed_high_risk(tmp), ["4"])

    def test_review_fallback_other_text_clears_nothing(self):
        for text in ("None.", "No", "None (reviewer ran)", "<None | reason a high-risk slice shipped>",
                     "user accepted: no reviewer", "Accepted via AskUserQuestion: all:", "Accepted via AskUserQuestion: all"):
            with self.subTest(text=text), tempfile.TemporaryDirectory() as tmp:
                make_feature(tmp, fallback=text)
                self.assertEqual(review_tracking.unreviewed_high_risk(tmp), ["1", "3B", "4"])

    def test_lowercase_reviewed_key_counts_as_reviewed(self):
        with tempfile.TemporaryDirectory() as tmp:
            js = make_feature(tmp)
            with open(js, "w") as fh:
                json.dump({"reviewed": {"3b": True, "1": False}}, fh)
            self.assertEqual(review_tracking.unreviewed_high_risk(tmp), ["1", "4"])

    def test_evaluate_writes_to_active_feature(self):
        with tempfile.TemporaryDirectory() as tmp:
            js = make_feature(tmp)
            md = os.path.join(tmp, "workflow-state.md")
            good = {"cwd": tmp, "agent_type": "code-reviewer:code-reviewer",
                    "last_assistant_message": "<!--CODE-REVIEWER-REPORT-->\n<!--REVIEW-SCOPE: slice=4-->"}
            other = dict(good, agent_type="agent-tdd:agent-TDD")
            with mock.patch.object(review_tracking.sdd_state, "active_state_file", return_value=md):
                review_tracking.evaluate(other)
                self.assertFalse(os.path.exists(js))
                review_tracking.evaluate(good)
            with open(js) as fh:
                self.assertEqual(json.load(fh)["reviewed"], {"4": True})

    def test_record_from_payload_filters_subagent_type(self):
        with tempfile.TemporaryDirectory() as tmp:
            js = make_feature(tmp)
            msg = "<!--CODE-REVIEWER-REPORT-->\n<!--REVIEW-SCOPE: slice=1-->\nreview done"
            review_tracking.record_from_payload(
                {"agent_type": "agent-tdd:agent-TDD", "last_assistant_message": msg}, js)
            self.assertFalse(os.path.exists(js))
            review_tracking.record_from_payload(
                {"agent_type": "code-reviewer:code-reviewer", "last_assistant_message": msg}, js)
            with open(js) as fh:
                self.assertTrue(json.load(fh)["reviewed"]["1"])


    def test_unreviewed_tier_rule_and_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            make_feature(tmp)
            self.assertEqual(review_tracking.unreviewed(tmp, {"risk": "low"}), ["1", "3B", "4"])
            fb = {"review fallback": "Accepted via AskUserQuestion: 1: x"}
            self.assertEqual(review_tracking.unreviewed(tmp, fb), ["3B", "4"])
            fb = {"review fallback": "Accepted via AskUserQuestion: all: x", "risk": "high"}
            self.assertEqual(review_tracking.unreviewed(tmp, fb), [])

    def test_unreviewed_feature_high_covers_every_slice(self):
        with tempfile.TemporaryDirectory() as tmp:
            js = make_feature(tmp)
            for sid in ("1", "3b", "4"):
                review_tracking.record_review(js, sid)
            self.assertEqual(review_tracking.unreviewed(tmp, {"risk": "standard"}), [])
            self.assertEqual(review_tracking.unreviewed(tmp, {"risk": "High (auth)"}), ["2F2"])
            fb = {"risk": "high", "review fallback": "Accepted via AskUserQuestion: 2f2: x"}
            self.assertEqual(review_tracking.unreviewed(tmp, fb), [])

    def test_unreviewed_feature_high_without_tasks(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "workflow-state.md"), "w") as fh:
                fh.write("- Risk: high\n")
            self.assertEqual(review_tracking.unreviewed(tmp, {"risk": "high"}), ["(feature)"])
            review_tracking.record_review(os.path.join(tmp, "workflow-state.json"), "1")
            self.assertEqual(review_tracking.unreviewed(tmp, {"risk": "high"}), [])

    def test_unreviewed_reads_fields_from_state_when_omitted(self):
        with tempfile.TemporaryDirectory() as tmp:
            make_feature(tmp, fallback="Accepted via AskUserQuestion: all: x")
            self.assertEqual(review_tracking.unreviewed(tmp), [])

    def test_record_from_payload_uses_agent_transcript_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            js = make_feature(tmp)
            tp = os.path.join(tmp, "t.jsonl")
            msg = "<!--CODE-REVIEWER-REPORT-->\n<!--REVIEW-SCOPE: slice=1-->\ndone"
            with open(tp, "w") as fh:
                fh.write(json.dumps({"type": "assistant", "message": {
                    "role": "assistant", "content": [{"type": "text", "text": msg}]}}) + "\n")
            review_tracking.record_from_payload(
                {"agent_type": "code-reviewer:code-reviewer", "agent_transcript_path": tp}, js)
            with open(js) as fh:
                self.assertTrue(json.load(fh)["reviewed"]["1"])

    def test_unreviewed_high_risk_stays_tier_only_when_risk_high(self):
        with tempfile.TemporaryDirectory() as tmp:
            make_feature(tmp)
            with open(os.path.join(tmp, "workflow-state.md"), "w") as fh:
                fh.write("- Risk: high\n- Review Fallback: None\n")
            self.assertEqual(review_tracking.unreviewed_high_risk(tmp), ["1", "3B", "4"])
            self.assertEqual(review_tracking.unreviewed(tmp), ["1", "3B", "4", "2F2"])

    def test_parent_transcript_path_is_never_used(self):
        with tempfile.TemporaryDirectory() as tmp:
            js = make_feature(tmp)
            tp = os.path.join(tmp, "parent.jsonl")
            msg = "<!--CODE-REVIEWER-REPORT-->\n<!--REVIEW-SCOPE: slice=1-->\ndone"
            with open(tp, "w") as fh:
                fh.write(json.dumps({"type": "assistant", "message": {
                    "role": "assistant", "content": [{"type": "text", "text": msg}]}}) + "\n")
            review_tracking.record_from_payload(
                {"agent_type": "code-reviewer:code-reviewer", "transcript_path": tp}, js)
            self.assertFalse(os.path.exists(js))

    def test_read_text_is_public(self):
        self.assertEqual(review_tracking.read_text("/nonexistent/x"), "")


if __name__ == "__main__":
    unittest.main()
