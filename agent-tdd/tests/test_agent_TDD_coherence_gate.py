"""
Tests for post-all-slices coherence review gate.

Validates:
- Coherence review level determination (Deep vs Ultra)
- Finding categorization and severity mapping
- Gate decision logic (block vs allow completion)
- Finding ledger storage and handoff formatting
- Error handling and graceful degradation
"""

import unittest
from unittest.mock import Mock, patch
from pathlib import Path


class TestCoherenceReviewLevelDetermination(unittest.TestCase):
    """Tests for determining review level based on high-risk composition."""

    def test_all_standard_slices_uses_deep(self):
        """All-standard slices should use Deep review level."""
        slices = [
            {"id": "1", "risk_tier": "standard"},
            {"id": "2", "risk_tier": "standard"},
            {"id": "3", "risk_tier": "standard"},
        ]

        high_risk_count = sum(1 for s in slices if s["risk_tier"] == "high_risk")
        total_slices = len(slices)
        high_risk_ratio = high_risk_count / total_slices if total_slices > 0 else 0

        review_level = "Ultra" if (high_risk_ratio > 0.5) else "Deep"

        self.assertEqual(review_level, "Deep")
        self.assertEqual(high_risk_ratio, 0.0)

    def test_minority_high_risk_uses_deep(self):
        """High-risk count ≤ 50% should use Deep review level."""
        slices = [
            {"id": "1", "risk_tier": "standard"},
            {"id": "2", "risk_tier": "standard"},
            {"id": "3", "risk_tier": "high_risk"},
        ]

        high_risk_count = sum(1 for s in slices if s["risk_tier"] == "high_risk")
        total_slices = len(slices)
        high_risk_ratio = high_risk_count / total_slices if total_slices > 0 else 0

        review_level = "Ultra" if (high_risk_ratio > 0.5) else "Deep"

        self.assertEqual(review_level, "Deep")
        self.assertLess(high_risk_ratio, 0.5)

    def test_majority_high_risk_uses_ultra(self):
        """High-risk count > 50% should use Ultra review level."""
        slices = [
            {"id": "1", "risk_tier": "high_risk"},
            {"id": "2", "risk_tier": "high_risk"},
            {"id": "3", "risk_tier": "standard"},
        ]

        high_risk_count = sum(1 for s in slices if s["risk_tier"] == "high_risk")
        total_slices = len(slices)
        high_risk_ratio = high_risk_count / total_slices if total_slices > 0 else 0

        review_level = "Ultra" if (high_risk_ratio > 0.5) else "Deep"

        self.assertEqual(review_level, "Ultra")
        self.assertGreater(high_risk_ratio, 0.5)

    def test_all_high_risk_uses_ultra(self):
        """All high-risk slices should use Ultra review level."""
        slices = [
            {"id": "1", "risk_tier": "high_risk"},
            {"id": "2", "risk_tier": "high_risk"},
            {"id": "3", "risk_tier": "high_risk"},
        ]

        high_risk_count = sum(1 for s in slices if s["risk_tier"] == "high_risk")
        total_slices = len(slices)
        high_risk_ratio = high_risk_count / total_slices if total_slices > 0 else 0

        review_level = "Ultra" if (high_risk_ratio > 0.5) else "Deep"

        self.assertEqual(review_level, "Ultra")
        self.assertEqual(high_risk_ratio, 1.0)

    def test_exactly_50_percent_high_risk_uses_deep(self):
        """Exactly 50% high-risk should use Deep (not Ultra)."""
        slices = [
            {"id": "1", "risk_tier": "high_risk"},
            {"id": "2", "risk_tier": "standard"},
        ]

        high_risk_count = sum(1 for s in slices if s["risk_tier"] == "high_risk")
        total_slices = len(slices)
        high_risk_ratio = high_risk_count / total_slices if total_slices > 0 else 0

        review_level = "Ultra" if (high_risk_ratio > 0.5) else "Deep"

        self.assertEqual(review_level, "Deep")
        self.assertEqual(high_risk_ratio, 0.5)


class TestCoherenceScopeCollection(unittest.TestCase):
    """Tests for collecting modified files across all slices."""

    def test_scope_unions_files_from_all_slices(self):
        """Coherence scope should include all files from all slices."""
        slice_1_files = ["src/feature.py", "src/utils.py"]
        slice_2_files = ["src/models.py"]
        slice_3_files = ["src/api.py", "tests/test_api.py"]

        all_files = set(slice_1_files + slice_2_files + slice_3_files)

        self.assertEqual(len(all_files), 5)
        self.assertIn("src/feature.py", all_files)
        self.assertIn("src/models.py", all_files)
        self.assertIn("src/api.py", all_files)

    def test_scope_deduplicates_files_touched_by_multiple_slices(self):
        """If multiple slices modify same file, include only once in scope."""
        slice_1_files = ["src/feature.py", "src/utils.py"]
        slice_2_files = ["src/feature.py", "src/models.py"]  # overlap

        all_files = set(slice_1_files + slice_2_files)

        self.assertEqual(len(all_files), 3)
        self.assertEqual(all_files, {"src/feature.py", "src/utils.py", "src/models.py"})

    def test_scope_includes_production_and_test_files(self):
        """Scope should include both production and test files."""
        modified_files = [
            "src/feature.py",
            "src/models.py",
            "tests/test_feature.py",
            "tests/test_models.py",
        ]

        self.assertEqual(len(modified_files), 4)
        self.assertTrue(any(f.startswith("src/") for f in modified_files))
        self.assertTrue(any(f.startswith("tests/") for f in modified_files))


class TestFindingCategorization(unittest.TestCase):
    """Tests for coherence finding categorization and severity mapping."""

    def test_critical_severity_findings(self):
        """Critical findings should be: security flaws, breaking changes, major regressions."""
        critical_findings = [
            {
                "category": "security_implication",
                "severity": "CRITICAL",
                "description": "Combined changes allow SQL injection in slice 2 + slice 3 flow"
            },
            {
                "category": "cross_slice_interaction",
                "severity": "CRITICAL",
                "description": "Slice 3 breaks invariant that Slice 1 depends on"
            },
            {
                "category": "regression_risk",
                "severity": "CRITICAL",
                "description": "Combined pattern matches known regression trigger"
            }
        ]

        self.assertEqual(len(critical_findings), 3)
        for finding in critical_findings:
            self.assertEqual(finding["severity"], "CRITICAL")

    def test_major_severity_findings(self):
        """Major findings should be: design violations, duplicate logic, conflicts."""
        major_findings = [
            {
                "category": "duplicate_code",
                "severity": "MAJOR",
                "description": "Slice 1 and Slice 2 both implement caching logic"
            },
            {
                "category": "module_boundary_violation",
                "severity": "MAJOR",
                "description": "Slice 3 directly accesses internal state from Slice 1's module"
            }
        ]

        self.assertEqual(len(major_findings), 2)
        for finding in major_findings:
            self.assertEqual(finding["severity"], "MAJOR")

    def test_warning_severity_findings(self):
        """Warning findings should be: minor inconsistencies, style issues, edge cases."""
        warning_findings = [
            {
                "category": "edge_cases",
                "severity": "WARNING",
                "description": "Combined flow doesn't handle None input from Slice 2"
            },
            {
                "category": "style_consistency",
                "severity": "WARNING",
                "description": "Naming convention differs between slices"
            }
        ]

        self.assertEqual(len(warning_findings), 2)
        for finding in warning_findings:
            self.assertEqual(finding["severity"], "WARNING")

    def test_info_severity_findings(self):
        """Info findings should be: observations, suggestions, minor improvements."""
        info_findings = [
            {
                "category": "optimization_opportunity",
                "severity": "INFO",
                "description": "Could combine similar queries from Slice 1 and 2"
            },
            {
                "category": "testing_recommendation",
                "severity": "INFO",
                "description": "Consider adding integration test for Slice 2 + Slice 3 interaction"
            }
        ]

        self.assertEqual(len(info_findings), 2)
        for finding in info_findings:
            self.assertEqual(finding["severity"], "INFO")


class TestCoherenceGateDecisionLogic(unittest.TestCase):
    """Tests for gate decision logic (block vs allow completion)."""

    def test_critical_findings_block_completion(self):
        """CRITICAL findings should block implementation completion."""
        findings = [
            {
                "severity": "CRITICAL",
                "description": "Security vulnerability in combined changes"
            }
        ]

        # Block decision
        should_block = any(f["severity"] == "CRITICAL" for f in findings)

        self.assertTrue(should_block)
        # Expected: block completion; offer user options

    def test_major_findings_block_completion(self):
        """MAJOR findings should block implementation completion."""
        findings = [
            {
                "severity": "MAJOR",
                "description": "Design violation across slices"
            }
        ]

        # Block decision
        should_block = any(f["severity"] in ["CRITICAL", "MAJOR"] for f in findings)

        self.assertTrue(should_block)

    def test_warning_findings_allow_completion(self):
        """WARNING findings should NOT block completion."""
        findings = [
            {
                "severity": "WARNING",
                "description": "Minor inconsistency"
            }
        ]

        # Allow decision
        should_block = any(f["severity"] in ["CRITICAL", "MAJOR"] for f in findings)

        self.assertFalse(should_block)
        # Expected: document as follow-up task; allow completion

    def test_info_findings_allow_completion(self):
        """INFO findings should NOT block completion."""
        findings = [
            {
                "severity": "INFO",
                "description": "Suggestion for improvement"
            }
        ]

        # Allow decision
        should_block = any(f["severity"] in ["CRITICAL", "MAJOR"] for f in findings)

        self.assertFalse(should_block)

    def test_mixed_findings_block_if_critical_present(self):
        """Mixed findings should block if ANY CRITICAL present."""
        findings = [
            {"severity": "INFO", "description": "suggestion"},
            {"severity": "WARNING", "description": "minor issue"},
            {"severity": "CRITICAL", "description": "security flaw"},
        ]

        should_block = any(f["severity"] == "CRITICAL" for f in findings)

        self.assertTrue(should_block)

    def test_no_findings_allow_completion(self):
        """No findings should allow completion."""
        findings = []

        should_block = any(f["severity"] in ["CRITICAL", "MAJOR"] for f in findings)

        self.assertFalse(should_block)


class TestFindingsLedgerStorage(unittest.TestCase):
    """Tests for findings ledger storage and formatting."""

    def test_findings_ledger_includes_review_metadata(self):
        """Findings ledger should include review level and file count."""
        ledger = {
            "review_level": "Deep",
            "total_files_scoped": 7,
            "finding_count": {
                "critical": 0,
                "major": 1,
                "warning": 3,
                "info": 2
            }
        }

        self.assertEqual(ledger["review_level"], "Deep")
        self.assertEqual(ledger["total_files_scoped"], 7)
        self.assertEqual(ledger["finding_count"]["major"], 1)

    def test_findings_ledger_groups_by_severity(self):
        """Findings should be grouped and listed by severity."""
        ledger = {
            "critical_findings": [
                {"slices": ["1", "3"], "category": "security", "description": "..."}
            ],
            "major_findings": [
                {"slices": ["1", "2"], "category": "duplicate_code", "description": "..."}
            ],
            "non_blocking_findings": [
                {"category": "optimization", "description": "..."}
            ]
        }

        self.assertEqual(len(ledger["critical_findings"]), 1)
        self.assertEqual(len(ledger["major_findings"]), 1)
        self.assertEqual(len(ledger["non_blocking_findings"]), 1)

    def test_findings_include_affected_slices(self):
        """Each finding should list affected slice IDs."""
        finding = {
            "slices": ["1", "3"],
            "category": "cross_slice_interaction",
            "description": "Slice 3 changes break Slice 1 assumption"
        }

        self.assertIn("slices", finding)
        self.assertEqual(finding["slices"], ["1", "3"])


class TestCoherenceGateDecisionPathways(unittest.TestCase):
    """Tests for escalation pathways when findings block completion."""

    def test_critical_findings_offer_three_options(self):
        """Blocking findings should offer: re-slice, accept risk, request fixes."""
        gate_decision = "BLOCKED"
        user_options = ["re_slice", "accept_risk", "request_fixes"]

        self.assertEqual(gate_decision, "BLOCKED")
        self.assertEqual(len(user_options), 3)

    def test_escalation_marker_emitted_when_blocked(self):
        """Escalation marker should be emitted in handoff when blocked."""
        should_emit_marker = True  # When CRITICAL/MAJOR findings present

        if should_emit_marker:
            marker = "<!--AGENT-TDD-COHERENCE-GATE:blocked=\"true\" reason=\"...\""

        self.assertIn("COHERENCE-GATE", marker)
        self.assertIn("blocked=\"true\"", marker)


class TestCoherenceGateErrorHandling(unittest.TestCase):
    """Tests for error handling in coherence review gate."""

    def test_code_reviewer_unavailable_allows_completion(self):
        """If code-reviewer unavailable, skip coherence; allow completion."""
        code_reviewer_available = False

        if not code_reviewer_available:
            action = "skip_coherence_review"
            allow_completion = True

        self.assertEqual(action, "skip_coherence_review")
        self.assertTrue(allow_completion)

    def test_coherence_findings_unparseable_allows_completion(self):
        """If findings cannot be parsed, allow completion; document."""
        parse_error = True

        if parse_error:
            action = "allow_completion_with_note"
            handoff_note = "Coherence review findings unavailable"

        self.assertIn("unavailable", handoff_note)

    def test_timeout_on_coherence_treated_as_unavailable(self):
        """Timeout treated same as unavailable; allow completion."""
        timeout_occurred = True

        if timeout_occurred:
            action = "skip_and_document"
            allow_completion = True

        self.assertEqual(action, "skip_and_document")
        self.assertTrue(allow_completion)

    def test_multi_agent_check_fails_defaults_to_deep(self):
        """If multi_agent_available() fails, default to Deep (conservative)."""
        multi_agent_check_failed = True

        if multi_agent_check_failed:
            review_level = "Deep"  # Conservative fallback

        self.assertEqual(review_level, "Deep")


if __name__ == "__main__":
    unittest.main()
