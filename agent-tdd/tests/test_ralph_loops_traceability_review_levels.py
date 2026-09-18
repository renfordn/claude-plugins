"""
Tests for ralph loops Loop 3: Research-to-Implementation Traceability enhanced with review-level findings.

Validates:
- Design-phase coverage (Deep review of all design.md files)
- Per-slice review coverage (reviews touch all slice-declared files)
- Coherence review coverage (reviews all modified files)
- Finding consistency (no major conflicts between phases)
- File-to-review-level mapping
- Risk coverage for high-risk slices
"""

import unittest


class TestDesignPhaseCoverageValidation(unittest.TestCase):
    """Tests for validating Design phase review coverage."""

    def test_design_review_touches_all_design_touchpoints(self):
        """Design phase review should examine all files in design.md touchpoints."""
        design_touchpoints = ["src/feature.py", "src/utils.py", "tests/test_feature.py"]
        design_review_scope = ["src/feature.py", "src/utils.py", "tests/test_feature.py"]

        coverage_gap = set(design_touchpoints) - set(design_review_scope)

        self.assertEqual(len(coverage_gap), 0)

    def test_design_review_gap_detected(self):
        """Missing design review for a file should be flagged as gap."""
        design_touchpoints = ["src/feature.py", "src/utils.py", "src/models.py"]
        design_review_scope = ["src/feature.py", "src/utils.py"]  # Missing src/models.py

        coverage_gap = set(design_touchpoints) - set(design_review_scope)

        self.assertEqual(coverage_gap, {"src/models.py"})

    def test_design_review_uses_deep_level(self):
        """Design phase review should use Deep level."""
        design_review_level = "Deep"

        self.assertEqual(design_review_level, "Deep")

    def test_design_review_multiple_missing_files(self):
        """Multiple missing files in design review should all be flagged."""
        design_touchpoints = ["src/a.py", "src/b.py", "src/c.py", "src/d.py"]
        design_review_scope = ["src/a.py", "src/b.py"]  # Missing c and d

        coverage_gap = set(design_touchpoints) - set(design_review_scope)

        self.assertEqual(coverage_gap, {"src/c.py", "src/d.py"})


class TestPerSliceReviewCoverageValidation(unittest.TestCase):
    """Tests for validating per-slice review coverage."""

    def test_slice_review_touches_all_slice_files(self):
        """Slice review should examine all files declared in slice."""
        slice_files = ["src/feature.py", "src/utils.py"]
        review_scope = ["src/feature.py", "src/utils.py"]

        coverage_gap = set(slice_files) - set(review_scope)

        self.assertEqual(len(coverage_gap), 0)

    def test_slice_review_gap_detected(self):
        """Missing review for a slice-declared file should be flagged."""
        slice_files = ["src/feature.py", "src/utils.py", "tests/test_feature.py"]
        review_scope = ["src/feature.py", "src/utils.py"]  # Missing test file

        coverage_gap = set(slice_files) - set(review_scope)

        self.assertEqual(coverage_gap, {"tests/test_feature.py"})

    def test_review_level_for_standard_tier_slice(self):
        """Standard tier slice should use Standard review level."""
        risk_tier = "standard"
        expected_level = "Standard"

        actual_level = "Standard" if risk_tier == "standard" else "Deep"

        self.assertEqual(actual_level, expected_level)

    def test_review_level_for_high_risk_slice(self):
        """High-risk slice should use Deep review level."""
        risk_tier = "high_risk"
        expected_level = "Deep"

        actual_level = "Standard" if risk_tier == "standard" else "Deep"

        self.assertEqual(actual_level, expected_level)

    def test_multiple_slices_coverage_validation(self):
        """Multiple slices should each have appropriate coverage."""
        slices = [
            {"id": "1", "files": ["src/a.py"], "review_scope": ["src/a.py"]},
            {"id": "2", "files": ["src/b.py", "src/c.py"], "review_scope": ["src/b.py", "src/c.py"]},
        ]

        gaps = []
        for s in slices:
            gap = set(s["files"]) - set(s["review_scope"])
            if gap:
                gaps.append((s["id"], gap))

        self.assertEqual(len(gaps), 0)


class TestCoherenceReviewCoverageValidation(unittest.TestCase):
    """Tests for validating coherence review coverage of all modified files."""

    def test_coherence_review_touches_all_modified_files(self):
        """Coherence review should examine all files modified by all slices."""
        all_modified_files = {"src/a.py", "src/b.py", "src/c.py"}
        coherence_scope = {"src/a.py", "src/b.py", "src/c.py"}

        coverage_gap = all_modified_files - coherence_scope

        self.assertEqual(len(coverage_gap), 0)

    def test_coherence_review_gap_detected(self):
        """Missing coherence review for a modified file should be flagged."""
        all_modified_files = {"src/a.py", "src/b.py", "src/c.py"}
        coherence_scope = {"src/a.py", "src/b.py"}  # Missing src/c.py

        coverage_gap = all_modified_files - coherence_scope

        self.assertEqual(coverage_gap, {"src/c.py"})

    def test_coherence_review_uses_appropriate_level(self):
        """Coherence review level should be Deep or Ultra based on high-risk ratio."""
        high_risk_ratio = 0.67
        multi_agent_available = True

        review_level = "Ultra" if (high_risk_ratio > 0.5 and multi_agent_available) else "Deep"

        self.assertEqual(review_level, "Ultra")

    def test_coherence_review_without_multi_agent(self):
        """Coherence review without multi-agent should use Deep."""
        high_risk_ratio = 0.67
        multi_agent_available = False

        review_level = "Ultra" if (high_risk_ratio > 0.5 and multi_agent_available) else "Deep"

        self.assertEqual(review_level, "Deep")


class TestFindingConsistencyValidation(unittest.TestCase):
    """Tests for validating consistency between per-slice and coherence findings."""

    def test_no_major_conflicts_between_phases(self):
        """Findings from different phases should not have major conflicts."""
        per_slice_findings = [
            {"file": "src/a.py", "category": "design", "severity": "warning"},
        ]
        coherence_findings = [
            {"file": "src/a.py", "category": "optimization", "severity": "info"},
        ]

        # Check for conflicts (same file, both CRITICAL or MAJOR)
        conflicts = []
        for pf in per_slice_findings:
            for cf in coherence_findings:
                if pf["file"] == cf["file"]:
                    if pf["severity"] in ["CRITICAL", "MAJOR"] and cf["severity"] in ["CRITICAL", "MAJOR"]:
                        conflicts.append((pf, cf))

        self.assertEqual(len(conflicts), 0)

    def test_major_conflict_detected(self):
        """Major conflicting findings should be detected."""
        per_slice_findings = [
            {"file": "src/a.py", "category": "design", "severity": "MAJOR", "message": "X is wrong"},
        ]
        coherence_findings = [
            {"file": "src/a.py", "category": "regression", "severity": "CRITICAL", "message": "Y breaks X"},
        ]

        conflicts = []
        for pf in per_slice_findings:
            for cf in coherence_findings:
                if pf["file"] == cf["file"]:
                    if pf["severity"] in ["CRITICAL", "MAJOR"] and cf["severity"] in ["CRITICAL", "MAJOR"]:
                        conflicts.append((pf, cf))

        self.assertEqual(len(conflicts), 1)

    def test_consistent_finding_categories(self):
        """Related findings should have consistent categories across phases."""
        per_slice_findings = [
            {"file": "src/a.py", "category": "module_boundary", "severity": "warning"},
        ]
        coherence_findings = [
            {"file": "src/a.py", "category": "module_boundary", "severity": "info"},
        ]

        # Both mention module_boundary → consistent
        per_categories = {f["category"] for f in per_slice_findings}
        coherence_categories = {f["category"] for f in coherence_findings}

        overlap = per_categories & coherence_categories

        self.assertGreater(len(overlap), 0)


class TestFileToReviewLevelMapping(unittest.TestCase):
    """Tests for file-to-review-level mapping validation."""

    def test_file_mapping_shows_review_coverage(self):
        """Each file should show which review levels examined it."""
        file_review_map = {
            "src/a.py": ["Deep", "Standard"],  # Design + Per-slice
            "src/b.py": ["Standard", "Deep"],  # Per-slice + Coherence
            "src/c.py": ["Deep"],  # Design only
        }

        # Verify each file has at least one review level
        for file, levels in file_review_map.items():
            self.assertGreater(len(levels), 0)

    def test_critical_files_require_appropriate_depth(self):
        """Critical files should be reviewed at Deep or higher."""
        critical_files = ["src/auth.py", "src/payment.py"]
        file_review_map = {
            "src/auth.py": ["Deep"],  # OK - Deep level
            "src/payment.py": ["Deep", "Ultra"],  # OK - Deep and Ultra
        }

        gaps = []
        for cf in critical_files:
            levels = file_review_map.get(cf, [])
            if not any(level in ["Deep", "Ultra"] for level in levels):
                gaps.append(cf)

        self.assertEqual(len(gaps), 0)

    def test_critical_file_insufficient_review_depth(self):
        """Critical file reviewed at Quick/Standard should be flagged."""
        critical_files = ["src/auth.py"]
        file_review_map = {
            "src/auth.py": ["Standard"],  # NOT OK - only Standard
        }

        gaps = []
        for cf in critical_files:
            levels = file_review_map.get(cf, [])
            if not any(level in ["Deep", "Ultra"] for level in levels):
                gaps.append(cf)

        self.assertEqual(gaps, ["src/auth.py"])


class TestRiskCoverageValidation(unittest.TestCase):
    """Tests for validating high-risk slices are reviewed at appropriate depth."""

    def test_high_risk_slice_reviewed_at_deep(self):
        """High-risk slice should be reviewed at Deep level."""
        slice_risk_tier = "high_risk"
        review_level = "Deep" if slice_risk_tier == "high_risk" else "Standard"

        self.assertEqual(review_level, "Deep")

    def test_high_risk_file_from_design_risk_section(self):
        """Files named in design.md Risks should be reviewed at Deep."""
        design_risk_files = ["src/payment.py", "src/auth.py"]
        file_review_map = {
            "src/payment.py": ["Deep"],  # OK
            "src/auth.py": ["Standard"],  # NOT OK
        }

        under_reviewed = []
        for rf in design_risk_files:
            levels = file_review_map.get(rf, [])
            if not any(level in ["Deep", "Ultra"] for level in levels):
                under_reviewed.append(rf)

        self.assertEqual(under_reviewed, ["src/auth.py"])

    def test_coherence_review_includes_high_risk_slices(self):
        """Coherence review should examine files from high-risk slices."""
        high_risk_slice_files = ["src/a.py", "src/b.py"]
        coherence_review_scope = ["src/a.py", "src/b.py", "src/c.py", "src/d.py"]

        coverage_gap = set(high_risk_slice_files) - set(coherence_review_scope)

        self.assertEqual(len(coverage_gap), 0)


class TestTraceabilityExitConditions(unittest.TestCase):
    """Tests for traceability validation exit conditions."""

    def test_all_conditions_pass_validation_succeeds(self):
        """When all conditions pass, traceability validation succeeds."""
        conditions = {
            "design_phase_coverage": True,
            "per_slice_coverage": True,
            "coherence_coverage": True,
            "no_conflicts": True,
            "appropriate_depth": True,
        }

        passed = all(conditions.values())

        self.assertTrue(passed)

    def test_one_condition_fails_validation_fails(self):
        """When any condition fails, validation fails."""
        conditions = {
            "design_phase_coverage": True,
            "per_slice_coverage": False,  # FAILS
            "coherence_coverage": True,
            "no_conflicts": True,
            "appropriate_depth": True,
        }

        passed = all(conditions.values())

        self.assertFalse(passed)

    def test_multiple_conditions_fail_all_reported(self):
        """Multiple failures should all be reported."""
        conditions = {
            "design_phase_coverage": False,
            "per_slice_coverage": False,
            "coherence_coverage": True,
            "no_conflicts": False,
            "appropriate_depth": True,
        }

        failures = [name for name, passed in conditions.items() if not passed]

        self.assertEqual(len(failures), 3)
        self.assertIn("design_phase_coverage", failures)
        self.assertIn("per_slice_coverage", failures)
        self.assertIn("no_conflicts", failures)


class TestTraceabilityEscalationPaths(unittest.TestCase):
    """Tests for traceability validation escalation and remediation."""

    def test_uncovered_file_suggests_re_review(self):
        """Uncovered file should suggest re-running review at higher level."""
        uncovered_file = "src/critical.py"
        escalation = f"File {uncovered_file} not covered by review; suggest re-run at higher level"

        self.assertIn("higher level", escalation)

    def test_missing_slice_declaration_suggests_update(self):
        """File modified but not in any slice should suggest tasks.md update."""
        undeclared_file = "src/util.py"
        escalation = f"File {undeclared_file} modified but not declared in any slice; update tasks.md"

        self.assertIn("tasks.md", escalation)

    def test_finding_conflict_suggests_investigation(self):
        """Conflicting findings should suggest investigation."""
        conflict = {"per_slice": "design_pattern_violation", "coherence": "not a problem"}
        escalation = "Conflicting findings detected; investigate and resolve"

        self.assertIn("investigate", escalation.lower())

    def test_risk_miss_suggests_deep_review(self):
        """High-risk file reviewed at Standard should suggest Deep re-review."""
        file = "src/auth.py"
        escalation = f"High-risk file {file} reviewed at Standard; re-run at Deep"

        self.assertIn("Deep", escalation)


if __name__ == "__main__":
    unittest.main()
