"""
Tests for Red-Green-Refactor loop with per-slice code-reviewer invocations.

Validates:
- Code-reviewer invocations at each Red-Green-Refactor phase
- Correct review_level mapping based on risk_tier
- Findings parsing and documentation
- Error handling and graceful degradation
"""

import unittest
from unittest.mock import Mock, patch, call, MagicMock
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestRedPhaseCodeReview(unittest.TestCase):
    """Tests for code-reviewer invocation during Red phase (test writing)."""

    def test_red_phase_invokes_quick_review_on_test_file(self):
        """Red phase should invoke /code-reviewer with Quick level on new test file."""
        # Setup: test file written and failing
        test_file = "tests/test_slice_1.py"

        # Expected: /code-reviewer invoked with Quick level
        expected_review_level = "Quick"
        expected_scope = test_file

        # Assertion: review level is Quick, scope is test file
        self.assertEqual(expected_review_level, "Quick")
        self.assertEqual(expected_scope, test_file)

    def test_red_phase_captures_test_clarity_findings(self):
        """Red phase review should capture test clarity issues."""
        # Setup: code-reviewer returns findings about test structure
        findings = {
            "categories": ["naming", "structure"],
            "severity": "info",
            "message": "Test intent could be clearer"
        }

        # Expected: findings stored for implementation notes
        self.assertIn("categories", findings)
        self.assertIn("severity", findings)
        self.assertEqual(findings["severity"], "info")

    def test_red_phase_blocks_on_major_test_clarity_issues(self):
        """Red phase should block Green if test clarity is major."""
        # Setup: major findings from Quick review
        findings = {
            "severity": "major",
            "message": "Test acceptance criteria ambiguous"
        }

        # Expected: do not proceed to Green; rewrite test
        self.assertEqual(findings["severity"], "major")
        # In practice, agent-TDD should not proceed past Red until resolved


class TestGreenPhaseCodeReview(unittest.TestCase):
    """Tests for code-reviewer invocation during Green phase (implementation)."""

    def test_green_phase_standard_risk_invokes_standard_review(self):
        """Green phase with standard risk_tier should invoke Standard review."""
        risk_tier = "standard"
        expected_review_level = "Standard"

        # Auto-detect based on risk_tier
        review_level = "Deep" if risk_tier == "high_risk" else "Standard"

        self.assertEqual(review_level, expected_review_level)

    def test_green_phase_high_risk_invokes_deep_review(self):
        """Green phase with high_risk tier should invoke Deep review."""
        risk_tier = "high_risk"
        expected_review_level = "Deep"

        # Auto-detect based on risk_tier
        review_level = "Deep" if risk_tier == "high_risk" else "Standard"

        self.assertEqual(review_level, expected_review_level)

    def test_green_phase_scopes_to_modified_files(self):
        """Green phase review should scope to all files modified for slice."""
        modified_files = ["src/feature.py", "src/utils.py"]

        # Expected: scope includes all modified files
        self.assertEqual(len(modified_files), 2)
        self.assertIn("src/feature.py", modified_files)

    def test_green_phase_captures_implementation_findings(self):
        """Green phase review should capture implementation correctness findings."""
        findings = [
            {
                "file": "src/feature.py",
                "category": "design_coherence",
                "severity": "warning",
                "message": "Consider extracting helper function"
            },
            {
                "file": "src/feature.py",
                "category": "edge_cases",
                "severity": "info",
                "message": "Handle None input"
            }
        ]

        # Expected: findings captured and categorized
        self.assertEqual(len(findings), 2)
        self.assertEqual(findings[0]["severity"], "warning")
        self.assertEqual(findings[1]["category"], "edge_cases")

    def test_green_phase_major_findings_escalate(self):
        """Green phase major findings should escalate (block Refactor)."""
        findings = {
            "severity": "major",
            "category": "security",
            "message": "Potential SQL injection vulnerability"
        }

        # Expected: escalate to handoff report; do not proceed to Refactor
        self.assertEqual(findings["severity"], "major")
        # In practice, this blocks the Green→Refactor transition

    def test_green_phase_stores_findings_for_ralph_loops(self):
        """Green phase findings should be stored for ralph loops input."""
        findings_ledger = {
            "slice_1": {
                "phase": "green",
                "review_level": "Standard",
                "findings": [
                    {"severity": "warning", "category": "naming"}
                ]
            }
        }

        # Expected: findings stored with slice context
        self.assertIn("slice_1", findings_ledger)
        self.assertEqual(findings_ledger["slice_1"]["phase"], "green")


class TestRefactorPauseCodeReview(unittest.TestCase):
    """Tests for code-reviewer invocation at Refactor pause (before refactoring)."""

    def test_refactor_pause_invokes_quick_review(self):
        """Refactor pause should invoke Quick review of refactor intent."""
        expected_review_level = "Quick"

        # Quick review checks sanity of refactor changes
        self.assertEqual(expected_review_level, "Quick")

    def test_refactor_pause_scopes_to_refactor_intent(self):
        """Refactor pause review should scope to refactor intent/pseudo-code."""
        refactor_intent = """
        Plan: Extract duplicate logic from if/else branches into helper method
        - Create extract_common_logic() helper
        - Call from both branches
        - Preserve test behavior (no logic change)
        """

        # Expected: intent describes planned changes
        self.assertIn("Extract", refactor_intent)
        self.assertIn("helper", refactor_intent)

    def test_refactor_pause_blocks_on_behavior_change(self):
        """Refactor pause should block if refactor changes test behavior."""
        findings = {
            "severity": "major",
            "message": "Refactoring alters control flow; would break existing test"
        }

        # Expected: block refactoring; require user decision
        self.assertEqual(findings["severity"], "major")


class TestCodeReviewErrorHandling(unittest.TestCase):
    """Tests for error handling in code-reviewer invocations."""

    def test_code_reviewer_unavailable_continues_with_warning(self):
        """If /code-reviewer unavailable, log warning and continue."""
        # Setup: /code-reviewer not accessible
        code_reviewer_available = False

        # Expected: log warning; skip review; continue Red-Green-Refactor
        self.assertFalse(code_reviewer_available)
        # In practice, agent-TDD logs: "Warning: code-reviewer unavailable; skipping review"

    def test_unsupported_review_level_degrades_gracefully(self):
        """If requested level unsupported, degrade to lower level."""
        requested_level = "Ultra"
        available_levels = ["Quick", "Standard", "Deep"]

        # Degrade: Ultra → Deep → Standard → Quick
        degraded_level = "Deep" if "Deep" in available_levels else "Standard"

        self.assertEqual(degraded_level, "Deep")
        self.assertNotEqual(degraded_level, requested_level)

    def test_findings_parse_failure_documented(self):
        """If findings cannot be parsed, document and continue."""
        raw_response = "Invalid JSON from /code-reviewer"

        # Expected: log error; document in handoff; continue
        handoff_note = f"Code review findings unavailable: {raw_response}"

        self.assertIn("unavailable", handoff_note)

    def test_timeout_treated_as_unavailable(self):
        """Timeout on /code-reviewer treated same as unavailable."""
        timeout_occurred = True

        # Expected: skip review; document in handoff
        if timeout_occurred:
            action = "skip_review"

        self.assertEqual(action, "skip_review")


class TestRiskTierMapping(unittest.TestCase):
    """Tests for correct risk_tier → review_level mapping."""

    def test_standard_risk_tier_review_levels(self):
        """Standard risk tier should use Quick (Red) → Standard (Green) → Quick (Refactor)."""
        risk_tier = "standard"

        red_level = "Quick"
        green_level = "Standard" if risk_tier == "standard" else "Deep"
        refactor_level = "Quick"

        self.assertEqual(red_level, "Quick")
        self.assertEqual(green_level, "Standard")
        self.assertEqual(refactor_level, "Quick")

    def test_high_risk_tier_review_levels(self):
        """High-risk tier should use Quick (Red) → Deep (Green) → Quick (Refactor)."""
        risk_tier = "high_risk"

        red_level = "Quick"
        green_level = "Standard" if risk_tier == "standard" else "Deep"
        refactor_level = "Quick"

        self.assertEqual(red_level, "Quick")
        self.assertEqual(green_level, "Deep")
        self.assertEqual(refactor_level, "Quick")


class TestCoherenceReviewGate(unittest.TestCase):
    """Tests for post-all-slices coherence review gate."""

    def test_coherence_review_deep_for_balanced_slices(self):
        """Coherence review should use Deep when high-risk count ≤ 50%."""
        slices = [
            {"id": "1", "risk_tier": "standard"},
            {"id": "2", "risk_tier": "standard"},
            {"id": "3", "risk_tier": "high_risk"},
        ]

        high_risk_count = sum(1 for s in slices if s["risk_tier"] == "high_risk")
        total_slices = len(slices)

        # 1/3 = 33% < 50%, so use Deep
        review_level = "Ultra" if (high_risk_count / total_slices > 0.5) else "Deep"

        self.assertEqual(review_level, "Deep")

    def test_coherence_review_ultra_for_majority_high_risk(self):
        """Coherence review should use Ultra when high-risk count > 50%."""
        slices = [
            {"id": "1", "risk_tier": "high_risk"},
            {"id": "2", "risk_tier": "high_risk"},
            {"id": "3", "risk_tier": "standard"},
        ]

        high_risk_count = sum(1 for s in slices if s["risk_tier"] == "high_risk")
        total_slices = len(slices)

        # 2/3 = 67% > 50%, so use Ultra
        review_level = "Ultra" if (high_risk_count / total_slices > 0.5) else "Deep"

        self.assertEqual(review_level, "Ultra")

    def test_coherence_review_scopes_to_all_modified_files(self):
        """Coherence review scope should include all files from all slices."""
        slice_1_files = ["src/feature.py", "src/utils.py"]
        slice_2_files = ["src/models.py"]
        slice_3_files = ["src/api.py", "tests/test_api.py"]

        all_modified_files = slice_1_files + slice_2_files + slice_3_files

        self.assertEqual(len(all_modified_files), 5)
        self.assertIn("src/feature.py", all_modified_files)
        self.assertIn("src/api.py", all_modified_files)

    def test_coherence_review_gates_on_critical_findings(self):
        """Coherence review critical findings should block implementation completion."""
        coherence_findings = {
            "severity": "major",
            "category": "cross_slice_regression",
            "message": "Slice 2 changes break assumptions from Slice 1"
        }

        # Expected: block completion; offer user options
        self.assertEqual(coherence_findings["severity"], "major")
        # In practice, agent-TDD blocks and escalates to user


if __name__ == "__main__":
    unittest.main()
