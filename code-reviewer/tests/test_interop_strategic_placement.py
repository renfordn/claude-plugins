"""
Tests for code-reviewer INTEROP.md Strategic Review Placement table (Task 5.2).

Validates:
- Strategic placement section exists
- Phase-to-level mapping table complete
- Capability-detection substring preserved
- Cross-references valid
- Ralph loops integration documented
"""

import unittest
from pathlib import Path


class TestStrategicPlacementDocumentation(unittest.TestCase):
    """Tests for Strategic Review Placement section in INTEROP.md."""

    @classmethod
    def setUpClass(cls):
        """Read INTEROP.md once for all tests."""
        interop_path = Path(__file__).parent.parent / "INTEROP.md"
        with open(interop_path) as f:
            cls.interop_content = f.read()

    def test_strategic_placement_section_exists(self):
        """Strategic Review Placement section should be present."""
        self.assertIn("Strategic Review Placement", self.interop_content)

    def test_phase_level_mapping_table_exists(self):
        """Phase-to-level mapping table should be present."""
        self.assertIn("ISDD Phase | Review Level | Purpose", self.interop_content)

    def test_requirements_phase_documented(self):
        """Requirements phase should be documented with Standard level."""
        self.assertIn("**Requirements**", self.interop_content)
        self.assertIn("Standard", self.interop_content)
        self.assertIn("Clarity validation", self.interop_content)

    def test_design_phase_documented(self):
        """Design phase should be documented with Deep level."""
        self.assertIn("**Design**", self.interop_content)
        self.assertIn("Coherence validation", self.interop_content)

    def test_tasks_phase_documented(self):
        """Tasks phase should be documented."""
        self.assertIn("**Tasks**", self.interop_content)

    def test_per_slice_red_phase_documented(self):
        """Per-slice Red phase should be documented with Quick level."""
        self.assertIn("**Impl: Per-Slice (Red)**", self.interop_content)
        self.assertIn("Quick", self.interop_content)

    def test_per_slice_green_phase_documented(self):
        """Per-slice Green phase should be documented with Standard/Deep."""
        self.assertIn("**Impl: Per-Slice (Green)**", self.interop_content)
        self.assertIn("Standard or Deep", self.interop_content)

    def test_coherence_phase_documented(self):
        """Coherence phase should be documented with Deep/Ultra."""
        self.assertIn("**Impl: Post-Slices (Coherence)**", self.interop_content)
        self.assertIn("Deep or Ultra", self.interop_content)

    def test_rationale_section_present(self):
        """Rationale section should explain why each level is used."""
        self.assertIn("**Rationale:**", self.interop_content)

    def test_ralph_loops_integration_documented(self):
        """Ralph loops integration should be documented."""
        self.assertIn("Ralph Loops Integration:", self.interop_content)
        self.assertIn("Traceability validation", self.interop_content)

    def test_capability_detection_substring_present(self):
        """Capability-detection substring should be present and preserved."""
        # Must have "Integrating Code Reviewer" substring
        self.assertIn("Integrating Code Reviewer", self.interop_content)

    def test_capability_detection_note_present(self):
        """Capability Detection Note section should be present."""
        self.assertIn("Capability Detection Note:", self.interop_content)
        self.assertIn("plugin-orchestrator", self.interop_content)

    def test_cross_references_section_present(self):
        """Cross-references to other documentation should be present."""
        self.assertIn("Cross-references:", self.interop_content)

    def test_code_reviewer_skill_referenced(self):
        """code-reviewer/SKILL.md should be referenced."""
        self.assertIn("code-reviewer/SKILL.md", self.interop_content)

    def test_agent_tdd_skill_referenced(self):
        """agent-tdd/SKILL.md should be referenced."""
        self.assertIn("agent-tdd/SKILL.md", self.interop_content)

    def test_design_md_referenced(self):
        """design.md should be referenced."""
        self.assertIn("design.md", self.interop_content)

    def test_plugin_orchestrator_test_referenced(self):
        """plugin-orchestrator test should be referenced."""
        self.assertIn("plugin-orchestrator/tests/test_smoke_e2e.py", self.interop_content)


class TestStrategicPlacementTableStructure(unittest.TestCase):
    """Tests for the strategic placement table structure."""

    @classmethod
    def setUpClass(cls):
        """Read INTEROP.md once for all tests."""
        interop_path = Path(__file__).parent.parent / "INTEROP.md"
        with open(interop_path) as f:
            cls.interop_content = f.read()

    def test_table_has_all_columns(self):
        """Table should have all required columns."""
        self.assertIn("ISDD Phase", self.interop_content)
        self.assertIn("Review Level", self.interop_content)
        self.assertIn("Purpose", self.interop_content)
        self.assertIn("What to Review", self.interop_content)
        self.assertIn("When", self.interop_content)
        self.assertIn("Invoked By", self.interop_content)

    def test_requirements_row_complete(self):
        """Requirements row should have all fields."""
        self.assertIn("Requirements", self.interop_content)
        self.assertIn("EARS formatting", self.interop_content)

    def test_design_row_complete(self):
        """Design row should have all fields."""
        self.assertIn("Design patterns", self.interop_content)

    def test_tasks_row_complete(self):
        """Tasks row should have all fields."""
        self.assertIn("Task phrasing", self.interop_content)

    def test_per_slice_rows_complete(self):
        """Per-slice rows should have all fields."""
        self.assertIn("Per-Slice", self.interop_content)
        self.assertIn("test-author", self.interop_content)

    def test_coherence_row_complete(self):
        """Coherence row should have all fields."""
        self.assertIn("Cross-slice interactions", self.interop_content)


class TestRalphLoopsIntegration(unittest.TestCase):
    """Tests for ralph loops integration documentation."""

    @classmethod
    def setUpClass(cls):
        """Read INTEROP.md once for all tests."""
        interop_path = Path(__file__).parent.parent / "INTEROP.md"
        with open(interop_path) as f:
            cls.interop_content = f.read()

    def test_ralph_loops_section_present(self):
        """Ralph Loops Integration section should be present."""
        self.assertIn("Ralph Loops Integration:", self.interop_content)

    def test_design_phase_findings_documented(self):
        """Design-phase finding flow should be documented."""
        self.assertIn("Design-phase Deep findings", self.interop_content)
        self.assertIn("Traceability validation", self.interop_content)

    def test_per_slice_findings_documented(self):
        """Per-slice finding flow should be documented."""
        self.assertIn("Per-slice Standard findings", self.interop_content)
        self.assertIn("Per-slice correctness", self.interop_content)

    def test_coherence_findings_documented(self):
        """Coherence finding flow should be documented."""
        self.assertIn("Coherence Deep/Ultra findings", self.interop_content)
        self.assertIn("Cross-slice regression", self.interop_content)

    def test_ralph_loops_skill_reference_present(self):
        """Reference to ralph loops skill should be present."""
        self.assertIn("Finding Flow to Ralph Loops", self.interop_content)


class TestConsistencyAndCrossBoundaries(unittest.TestCase):
    """Tests for consistency between INTEROP.md and related documents."""

    @classmethod
    def setUpClass(cls):
        """Read files for consistency checks."""
        interop_path = Path(__file__).parent.parent / "INTEROP.md"
        with open(interop_path) as f:
            cls.interop_content = f.read()

        skill_path = Path(__file__).parent.parent / "skills" / "code-reviewer" / "SKILL.md"
        with open(skill_path) as f:
            cls.skill_content = f.read()

    def test_review_levels_consistent(self):
        """Review levels should be mentioned consistently."""
        # Both files should mention Quick, Standard, Deep, Ultra
        for level in ["Quick", "Standard", "Deep", "Ultra"]:
            self.assertIn(level, self.interop_content)
            self.assertIn(level, self.skill_content)

    def test_phase_terminology_consistent(self):
        """Phase terminology should be consistent across files."""
        phases = ["Requirements", "Design", "Tasks"]
        for phase in phases:
            self.assertIn(phase, self.interop_content)

    def test_auto_detection_mentioned_consistently(self):
        """Auto-detection should be mentioned in both files."""
        self.assertIn("Auto-Detection", self.skill_content)
        # INTEROP references SKILL which has auto-detection
        self.assertIn("SKILL.md", self.interop_content)


if __name__ == "__main__":
    unittest.main()
