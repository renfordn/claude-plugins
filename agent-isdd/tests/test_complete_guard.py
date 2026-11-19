import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hooks"))

import complete_guard

TASKS = """# Tasks

## Slice 1: a
**Risk Tier:** high-risk

## Slice 2: b
**Risk Tier:** standard

## Slice 3: c
**Risk Tier:** high-risk
"""
STATE = "- Workflow Status: Active\n- Risk: {risk}\n- Review Fallback: {fb}\n- Recap: x\n"


def feature(tmp, tasks=TASKS, risk="standard", fb="None", reviewed=None):
    os.makedirs(os.path.join(tmp, "tasks"))
    if tasks is not None:
        with open(os.path.join(tmp, "tasks", "tasks.md"), "w") as fh:
            fh.write(tasks)
    sp = os.path.join(tmp, "workflow-state.md")
    with open(sp, "w") as fh:
        fh.write(STATE.format(risk=risk, fb=fb))
    if reviewed is not None:
        with open(os.path.join(tmp, "workflow-state.json"), "w") as fh:
            json.dump({"reviewed": {k: True for k in reviewed}}, fh)
    return sp


def edit(path, new="- Workflow Status: Complete"):
    return {"tool_name": "Edit", "tool_input": {
        "file_path": path, "old_string": "- Workflow Status: Active", "new_string": new}}


class CompleteGuardTests(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.tmp = os.path.realpath(self._t.name)
        self.addCleanup(self._t.cleanup)

    def test_denies_names_unreviewed_slices_and_both_ways_out(self):
        sp = feature(self.tmp, reviewed=["1"])
        r = complete_guard.evaluate(edit(sp), state_path=sp)
        self.assertIn("3", r)
        self.assertNotIn("slice 1", r.lower().replace("slice=", ""))
        self.assertIn("Review scope: slice=", r)
        self.assertIn("AskUserQuestion", r)

    def test_allows_when_all_reviewed(self):
        sp = feature(self.tmp, reviewed=["1", "3"])
        self.assertIsNone(complete_guard.evaluate(edit(sp), state_path=sp))

    def test_allows_with_review_fallback_form(self):
        sp = feature(self.tmp, fb="Accepted via AskUserQuestion: 1, 3: user waived")
        self.assertIsNone(complete_guard.evaluate(edit(sp), state_path=sp))

    def test_bare_fallback_text_does_not_count(self):
        sp = feature(self.tmp, fb="skipped, fine")
        self.assertTrue(complete_guard.evaluate(edit(sp), state_path=sp))

    def test_no_high_risk_allowed(self):
        sp = feature(self.tmp, tasks="## Slice 1: a\n**Risk Tier:** standard\n")
        self.assertIsNone(complete_guard.evaluate(edit(sp), state_path=sp))

    def test_feature_risk_high_without_evidence_denied(self):
        sp = feature(self.tmp, tasks=None, risk="high")
        self.assertTrue(complete_guard.evaluate(edit(sp), state_path=sp))

    def test_feature_risk_high_with_review_allowed(self):
        sp = feature(self.tmp, tasks=None, risk="high", reviewed=["1"])
        self.assertIsNone(complete_guard.evaluate(edit(sp), state_path=sp))

    def test_feature_risk_high_with_fallback_allowed(self):
        sp = feature(self.tmp, tasks=None, risk="high", fb="Accepted via AskUserQuestion: all: ok")
        self.assertIsNone(complete_guard.evaluate(edit(sp), state_path=sp))

    def test_feature_risk_high_partial_fallback_denied(self):
        sp = feature(self.tmp, risk="high", fb="Accepted via AskUserQuestion: 1: ok")
        r = complete_guard.evaluate(edit(sp), state_path=sp)
        self.assertIn("2", r)

    def test_feature_risk_high_unknown_id_fallback_denied(self):
        sp = feature(self.tmp, tasks=None, risk="high", fb="Accepted via AskUserQuestion: 99: ok")
        self.assertTrue(complete_guard.evaluate(edit(sp), state_path=sp))

    def test_feature_risk_high_needs_every_slice_reviewed(self):
        sp = feature(self.tmp, risk="high", reviewed=["1", "3"])
        self.assertIn("2", complete_guard.evaluate(edit(sp), state_path=sp))

    def test_feature_risk_high_all_slices_reviewed_allowed(self):
        sp = feature(self.tmp, risk="high", reviewed=["1", "2", "3"])
        self.assertIsNone(complete_guard.evaluate(edit(sp), state_path=sp))

    def test_feature_risk_high_reviewed_ids_not_in_tasks_dont_count(self):
        sp = feature(self.tmp, risk="high", reviewed=["1", "3", "77"])
        self.assertIn("2", complete_guard.evaluate(edit(sp), state_path=sp))

    def test_feature_unreviewed_function(self):
        sp = feature(self.tmp, risk="high", reviewed=["1"])
        fields = complete_guard._fields_from_text(open(sp).read())
        self.assertEqual(complete_guard.feature_unreviewed(self.tmp, fields), ["2", "3"])
        self.assertEqual(complete_guard.feature_unreviewed(self.tmp, {"risk": "standard"}), [])

    def test_already_complete_not_denied(self):
        sp = feature(self.tmp)
        with open(sp, "w") as fh:
            fh.write("- Workflow Status: Complete\n- Recap: x\n")
        p = {"tool_name": "Edit", "tool_input": {
            "file_path": sp, "old_string": "- Recap: x", "new_string": "- Recap: y"}}
        self.assertIsNone(complete_guard.evaluate(p, state_path=sp))

    def test_single_write_adds_fallback_and_completes(self):
        sp = feature(self.tmp)
        p = {"tool_name": "Edit", "tool_input": {
            "file_path": sp,
            "old_string": "- Workflow Status: Active\n- Risk: standard\n- Review Fallback: None",
            "new_string": "- Workflow Status: Complete\n- Risk: standard\n"
                          "- Review Fallback: Accepted via AskUserQuestion: all: ok"}}
        self.assertIsNone(complete_guard.evaluate(p, state_path=sp))

    def test_non_complete_write_allowed(self):
        sp = feature(self.tmp)
        self.assertIsNone(complete_guard.evaluate(edit(sp, "- Workflow Status: Paused"), state_path=sp))

    def test_write_tool_full_content_denied(self):
        sp = feature(self.tmp)
        p = {"tool_name": "Write", "tool_input": {
            "file_path": sp, "content": "- Workflow Status: Complete\n"}}
        self.assertTrue(complete_guard.evaluate(p, state_path=sp))

    def test_multiedit_denied(self):
        sp = feature(self.tmp)
        p = {"tool_name": "MultiEdit", "tool_input": {"file_path": sp, "edits": [
            {"old_string": "- Recap: x", "new_string": "- Recap: y"},
            {"old_string": "- Workflow Status: Active", "new_string": "- Workflow Status: complete"}]}}
        self.assertTrue(complete_guard.evaluate(p, state_path=sp))

    def test_other_file_ignored(self):
        sp = feature(self.tmp)
        other = os.path.join(self.tmp, "notes.md")
        with open(other, "w") as fh:
            fh.write("- Workflow Status: Active\n")
        self.assertIsNone(complete_guard.evaluate(edit(other), state_path=sp))

    def test_symlink_path_identity(self):
        sp = feature(self.tmp)
        link = os.path.join(self.tmp, "link.md")
        os.symlink(sp, link)
        self.assertTrue(complete_guard.evaluate(edit(link), state_path=sp))

    def test_no_state_path_or_garbage_fails_open(self):
        self.assertIsNone(complete_guard.evaluate({}, state_path=None))
        self.assertIsNone(complete_guard.evaluate({"tool_input": None}, state_path="/nope"))


if __name__ == "__main__":
    unittest.main()
