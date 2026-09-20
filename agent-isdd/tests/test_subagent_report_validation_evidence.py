"""Tests for subagent_report.py's _has_validation_evidence -- conservative narrative-regex
detection of confirmed passing test-suite evidence (see design.md's Data Contracts And
Interfaces: no match => False, never assumed true).
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hooks"))

import subagent_report as sr  # noqa: E402


class HasValidationEvidenceTests(unittest.TestCase):
    def test_all_tests_passing(self):
        self.assertTrue(sr._has_validation_evidence("Ran the suite: all tests passing."))

    def test_n_of_n_tests_passing(self):
        self.assertTrue(sr._has_validation_evidence("331 tests passing after the refactor."))

    def test_fraction_pass(self):
        self.assertTrue(sr._has_validation_evidence("265/266 pass (one skipped, unrelated)."))

    def test_regression_all_pass(self):
        self.assertTrue(sr._has_validation_evidence("Regression: full suite, all pass."))

    def test_full_regression_green(self):
        self.assertTrue(sr._has_validation_evidence("Full regression green after the change."))

    def test_no_test_related_text_is_false(self):
        self.assertFalse(sr._has_validation_evidence("Implemented the feature and wrote docs."))

    def test_explicit_failure_phrasing_is_false(self):
        self.assertFalse(sr._has_validation_evidence("3 tests failing, need another pass."))

    def test_regression_suite_red_is_false(self):
        self.assertFalse(sr._has_validation_evidence("Regression suite red after the merge."))

    def test_ambiguous_phrasing_is_false(self):
        self.assertFalse(sr._has_validation_evidence("Ran some tests locally."))

    def test_empty_text_is_false(self):
        self.assertFalse(sr._has_validation_evidence(""))


if __name__ == "__main__":
    unittest.main()
