#!/usr/bin/env python3
"""Tests for the isolated MODEL-ESCALATE marker parsing/detection utility
(Task 7: Escalation Marker Detection & Parsing).

This module is deliberately independent of agent-isdd's before_continue hook
so it can be developed and tested without the hook integration (Task 8).
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "hooks"))

from model_escalate_marker import (  # noqa: E402
    parse_model_escalate_marker,
    detect_model_escalate_in_report,
)


class ParseModelEscalateMarkerTests(unittest.TestCase):
    def test_parses_reason_from_model_to_model(self):
        marker = (
            '<!--AGENT-TDD-MODEL-ESCALATE: reason="Complex async patterns" '
            'from_model="Haiku" to_model="Sonnet"-->'
        )
        result = parse_model_escalate_marker(marker)

        self.assertEqual(result["reason"], "Complex async patterns")
        self.assertEqual(result["from_model"], "Haiku")
        self.assertEqual(result["to_model"], "Sonnet")

    def test_includes_timestamp_field(self):
        marker = (
            '<!--AGENT-TDD-MODEL-ESCALATE: reason="test" '
            'from_model="Haiku" to_model="Sonnet"-->'
        )
        result = parse_model_escalate_marker(marker)

        self.assertIn("timestamp", result)
        self.assertIsNotNone(result["timestamp"])

    def test_missing_from_model_defaults_gracefully(self):
        marker = '<!--AGENT-TDD-MODEL-ESCALATE: reason="test" to_model="Sonnet"-->'
        result = parse_model_escalate_marker(marker)

        self.assertEqual(result["reason"], "test")
        self.assertEqual(result["to_model"], "Sonnet")
        self.assertIsNone(result.get("from_model"))

    def test_missing_to_model_returns_none_result(self):
        """A marker missing to_model is not a usable escalation instruction."""
        marker = '<!--AGENT-TDD-MODEL-ESCALATE: reason="test" from_model="Haiku"-->'
        result = parse_model_escalate_marker(marker)

        self.assertIsNone(result)

    def test_missing_reason_returns_none_result(self):
        marker = '<!--AGENT-TDD-MODEL-ESCALATE: from_model="Haiku" to_model="Sonnet"-->'
        result = parse_model_escalate_marker(marker)

        self.assertIsNone(result)

    def test_empty_reason_returns_none_result(self):
        marker = '<!--AGENT-TDD-MODEL-ESCALATE: reason="" from_model="Haiku" to_model="Sonnet"-->'
        result = parse_model_escalate_marker(marker)

        self.assertIsNone(result)

    def test_malformed_marker_does_not_raise(self):
        marker = "<!--AGENT-TDD-MODEL-ESCALATE: this is not key=value pairs-->"
        result = parse_model_escalate_marker(marker)

        self.assertIsNone(result)

    def test_no_marker_present_returns_none(self):
        result = parse_model_escalate_marker("Just a plain string, no marker here.")

        self.assertIsNone(result)

    def test_legacy_suggest_tier_field_maps_to_to_model(self):
        """Bridges the Task 2-documented marker vocabulary (attempted_at_haiku/
        suggest_tier) so both the escalation-paths.md example and Task 7/8's
        from_model/to_model contract resolve to the same parsed shape."""
        marker = (
            '<!--AGENT-TDD-MODEL-ESCALATE:reason="complex recursive pattern needs '
            'stronger reasoning"; attempted_at_haiku=true; suggest_tier="sonnet"-->'
        )
        result = parse_model_escalate_marker(marker)

        self.assertIsNotNone(result)
        self.assertEqual(result["reason"], "complex recursive pattern needs stronger reasoning")
        self.assertEqual(result["to_model"], "sonnet")
        self.assertEqual(result["from_model"], "haiku")


class DetectModelEscalateInReportTests(unittest.TestCase):
    def test_finds_marker_within_free_text_report(self):
        report = (
            "## Handoff Report\n\n"
            'Some prose before the marker.\n'
            '<!--AGENT-TDD-MODEL-ESCALATE: reason="deep recursion" '
            'from_model="Haiku" to_model="Sonnet"-->\n'
            "Some prose after the marker.\n"
        )
        result = detect_model_escalate_in_report(report)

        self.assertIsNotNone(result)
        self.assertEqual(result["to_model"], "Sonnet")

    def test_returns_none_when_no_marker_in_report(self):
        report = "## Handoff Report\n\nAll slices green, no escalation needed."
        result = detect_model_escalate_in_report(report)

        self.assertIsNone(result)

    def test_uses_first_marker_when_multiple_present(self):
        report = (
            '<!--AGENT-TDD-MODEL-ESCALATE: reason="first" from_model="Haiku" to_model="Sonnet"-->\n'
            '<!--AGENT-TDD-MODEL-ESCALATE: reason="second" from_model="Sonnet" to_model="Opus"-->\n'
        )
        result = detect_model_escalate_in_report(report)

        self.assertEqual(result["reason"], "first")
        self.assertEqual(result["to_model"], "Sonnet")

    def test_marker_inside_code_block_is_still_detected(self):
        report = (
            "Here is an example marker for documentation purposes:\n"
            "```\n"
            '<!--AGENT-TDD-MODEL-ESCALATE: reason="doc example" '
            'from_model="Haiku" to_model="Sonnet"-->\n'
            "```\n"
        )
        result = detect_model_escalate_in_report(report)

        self.assertIsNotNone(result)
        self.assertEqual(result["reason"], "doc example")

    def test_malformed_marker_in_report_does_not_raise(self):
        report = "Report text <!--AGENT-TDD-MODEL-ESCALATE: garbage--> more text"

        result = detect_model_escalate_in_report(report)

        self.assertIsNone(result)

    def test_empty_report_returns_none(self):
        self.assertIsNone(detect_model_escalate_in_report(""))
        self.assertIsNone(detect_model_escalate_in_report(None))


if __name__ == "__main__":
    unittest.main()
