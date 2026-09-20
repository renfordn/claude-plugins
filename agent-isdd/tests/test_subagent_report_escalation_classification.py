"""Tests for subagent_report.py's _classify_escalation_outcome -- see design.md's Success
Criteria: succeeded only when validation evidence present AND no further escalation/blocker/
rollback marker; a further marker present dominates and forces failed regardless of evidence.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hooks"))

import subagent_report as sr  # noqa: E402

PENDING = {"reason": "context limit", "from_model": "haiku", "to_model": "sonnet",
           "detected_at": "2026-09-19T00:00:00"}


class ClassifyEscalationOutcomeTests(unittest.TestCase):
    def test_evidence_and_no_further_marker_is_succeeded(self):
        report = (
            "<!--AGENT-TDD-REPORT-->\n<!--AGENT-TDD-PHASE:all_slices_complete-->\n"
            "All tests passing. Feature complete."
        )
        self.assertEqual(sr._classify_escalation_outcome(report, PENDING), "succeeded")

    def test_evidence_with_rollback_marker_is_failed(self):
        report = (
            "<!--AGENT-TDD-REPORT-->\n<!--AGENT-TDD-PHASE:green_pause-->\n"
            "All tests passing.\n"
            '<!--SDD-ROLLBACK-REQUEST: target=Design reason="interface wrong"-->\n'
        )
        self.assertEqual(sr._classify_escalation_outcome(report, PENDING), "failed")

    def test_evidence_with_fresh_model_escalate_marker_is_failed(self):
        report = (
            "<!--AGENT-TDD-REPORT-->\n<!--AGENT-TDD-PHASE:green_pause-->\n"
            "All tests passing so far.\n"
            '<!--AGENT-TDD-MODEL-ESCALATE: reason="still too hard" from_model="Sonnet" '
            'to_model="Opus"-->\n'
        )
        self.assertEqual(sr._classify_escalation_outcome(report, PENDING), "failed")

    def test_no_evidence_no_further_marker_is_ambiguous(self):
        report = (
            "<!--AGENT-TDD-REPORT-->\n<!--AGENT-TDD-PHASE:green_pause-->\n"
            "Implemented the change, ran some tests locally."
        )
        self.assertEqual(sr._classify_escalation_outcome(report, PENDING), "ambiguous")

    def test_no_evidence_with_further_marker_is_failed(self):
        report = (
            "<!--AGENT-TDD-REPORT-->\n<!--AGENT-TDD-PHASE:green_pause-->\n"
            '<!--AGENT-TDD-PLAN-FLAG:reason="contradicts existing behavior"-->\n'
            "Ran into a conflict."
        )
        self.assertEqual(sr._classify_escalation_outcome(report, PENDING), "failed")


if __name__ == "__main__":
    unittest.main()
