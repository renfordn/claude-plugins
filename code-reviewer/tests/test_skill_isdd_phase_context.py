"""
Tests for code-reviewer SKILL.md ISDD Phase Context documentation (Task 5.1).

Validates:
- ISDD Phase Context section exists
- Phase-to-level mapping table present with all phases
- Auto-detection priority documented
- Examples provided
- Cross-references valid
- Language consistent
"""

import unittest
from pathlib import Path


class TestISddPhaseContextDocumentation(unittest.TestCase):
    """Tests for ISDD Phase Context section in SKILL.md."""

    @classmethod
    def setUpClass(cls):
        """Read SKILL.md once for all tests."""
        skill_path = Path(__file__).parent.parent / "skills" / "code-reviewer" / "SKILL.md"
        with open(skill_path) as f:
            cls.skill_content = f.read()

    def test_isdd_phase_context_section_exists(self):
        """ISDD Phase Context section should be present."""
        self.assertIn("ISDD Phase Context", self.skill_content)

    def test_auto_detection_in_workflows_header_present(self):
        """'Auto-Detection in Workflows' header should be present."""
        self.assertIn("Auto-Detection in Workflows", self.skill_content)

    def test_phase_to_level_mapping_table_exists(self):
        """Phase-to-level mapping table should be present."""
        self.assertIn("Phase | Context | Recommended Level", self.skill_content)

    def test_requirements_phase_documented(self):
        """Requirements phase should be documented with Standard level."""
        self.assertIn("Requirements", self.skill_content)
        # Check in context of table
        self.assertIn("EARS formatting", self.skill_content)

    def test_design_phase_documented(self):
        """Design phase should be documented with Deep level."""
        self.assertIn("Design", self.skill_content)
        self.assertIn("Deep", self.skill_content)

    def test_tasks_phase_documented(self):
        """Tasks phase should be documented with Standard level."""
        self.assertIn("Tasks", self.skill_content)
        self.assertIn("Task phrasing", self.skill_content)

    def test_per_slice_red_phase_documented(self):
        """Per-slice Red phase should be documented with Quick level."""
        self.assertIn("Impl: Per-Slice (Red)", self.skill_content)
        self.assertIn("Quick", self.skill_content)
        self.assertIn("Test intent", self.skill_content)

    def test_per_slice_green_phase_documented(self):
        """Per-slice Green phase should be documented with Standard/Deep."""
        self.assertIn("Impl: Per-Slice (Green)", self.skill_content)
        self.assertIn("Standard (or Deep if high-risk)", self.skill_content)

    def test_coherence_phase_documented(self):
        """Post-slices Coherence phase should be documented with Deep/Ultra."""
        self.assertIn("Impl: Post-Slices (Coherence)", self.skill_content)
        self.assertIn("Deep (or Ultra if majority high-risk)", self.skill_content)

    def test_auto_detection_priority_documented(self):
        """Auto-detection priority order should be documented."""
        self.assertIn("Auto-Detection Priority (ISDD context):", self.skill_content)
        self.assertIn("1.", self.skill_content)
        self.assertIn("Explicit request", self.skill_content)

    def test_explicit_request_is_priority_1(self):
        """Explicit request should be priority 1."""
        self.assertIn("1. **Explicit request**:", self.skill_content)

    def test_phase_context_is_priority_2(self):
        """Phase + Risk Context should be priority 2."""
        self.assertIn("2. **Phase + Risk Context**:", self.skill_content)

    def test_file_scope_is_priority_3(self):
        """File scope should be priority 3."""
        self.assertIn("3. **File scope**:", self.skill_content)

    def test_prior_context_is_priority_4(self):
        """Prior context should be priority 4."""
        self.assertIn("4. **Prior context**:", self.skill_content)

    def test_fallback_is_priority_5(self):
        """Fallback should be priority 5."""
        self.assertIn("5. **Fallback**:", self.skill_content)

    def test_examples_provided(self):
        """Examples section should be present."""
        self.assertIn("Examples:", self.skill_content)

    def test_red_phase_example(self):
        """Red phase example should show Quick level."""
        self.assertIn("Red phase of any slice", self.skill_content)
        self.assertIn("`Quick`", self.skill_content)

    def test_green_standard_tier_example(self):
        """Green phase standard-tier example should show Standard level."""
        self.assertIn("Green phase of standard-tier slice", self.skill_content)
        self.assertIn("`Standard`", self.skill_content)

    def test_green_high_risk_example(self):
        """Green phase high-risk example should show Deep level."""
        self.assertIn("Green phase of high-risk slice", self.skill_content)
        self.assertIn("`Deep`", self.skill_content)

    def test_coherence_high_risk_multi_agent_example(self):
        """Coherence high-risk with multi-agent example should show Ultra."""
        self.assertIn("Coherence review, 60% high-risk slices, multi-agent available", self.skill_content)
        self.assertIn("`Ultra`", self.skill_content)

    def test_coherence_high_risk_no_multi_agent_example(self):
        """Coherence high-risk without multi-agent example should show Deep."""
        self.assertIn("Coherence review, 60% high-risk slices, no multi-agent", self.skill_content)
        self.assertIn("`Deep`", self.skill_content)

    def test_key_insight_present(self):
        """Key Insight section should explain auto-detection lives in caller."""
        self.assertIn("Key Insight:", self.skill_content)
        self.assertIn("Auto-detection lives in the caller's reasoning", self.skill_content)

    def test_cross_references_section_present(self):
        """Cross-references to other documentation should be present."""
        self.assertIn("Cross-references:", self.skill_content)

    def test_agent_tdd_skill_referenced(self):
        """agent-tdd/SKILL.md should be referenced."""
        self.assertIn("agent-tdd/SKILL.md", self.skill_content)
        self.assertIn("Review-Level Strategy", self.skill_content)

    def test_agent_isdd_interop_referenced(self):
        """agent-isdd/INTEROP.md should be referenced."""
        self.assertIn("agent-isdd/INTEROP.md", self.skill_content)
        self.assertIn("Strategic Review Placement", self.skill_content)

    def test_agent_tdd_auto_detection_logic_referenced(self):
        """agent-tdd auto-detection logic should be referenced."""
        self.assertIn("agent-tdd/agents/agent-TDD.md", self.skill_content)
        self.assertIn("Auto-Detection Logic", self.skill_content)

    def test_design_md_auto_detection_referenced(self):
        """design.md auto-detection rules should be referenced."""
        self.assertIn("design.md", self.skill_content)
        self.assertIn("Auto-Detection Rules", self.skill_content)

    def test_section_formatting_consistent(self):
        """Section should use consistent markdown formatting."""
        # Check for consistent header levels
        self.assertIn("### ISDD Phase Context", self.skill_content)
        # Headers should be h3 (###) to match surrounding sections
        self.assertIn("**ISDD Phase → Review Level Mapping:**", self.skill_content)
        self.assertIn("**Auto-Detection Priority (ISDD context):**", self.skill_content)

    def test_language_clarity(self):
        """Language should be clear and professional."""
        # Should not have grammatical errors or unclear phrasing
        self.assertIn("infers", self.skill_content)
        self.assertIn("Auto-detection lives in", self.skill_content)

    def test_no_conflicts_with_existing_sections(self):
        """Should not conflict with existing Auto-Detection Rules section."""
        # Both sections should exist and refer to each other
        self.assertIn("### Auto-Detection Rules", self.skill_content)
        self.assertIn("### ISDD Phase Context", self.skill_content)


class TestPhaseContextTableStructure(unittest.TestCase):
    """Tests for the phase mapping table structure."""

    @classmethod
    def setUpClass(cls):
        """Read SKILL.md once for all tests."""
        skill_path = Path(__file__).parent.parent / "skills" / "code-reviewer" / "SKILL.md"
        with open(skill_path) as f:
            cls.skill_content = f.read()

    def test_table_has_all_columns(self):
        """Table should have all required columns."""
        # Extract table header
        table_start = self.skill_content.find("Phase | Context | Recommended Level")
        self.assertNotEqual(table_start, -1)

        # Check columns
        self.assertIn("Phase", self.skill_content[table_start:table_start+200])
        self.assertIn("Context", self.skill_content[table_start:table_start+200])
        self.assertIn("Recommended Level", self.skill_content[table_start:table_start+200])
        self.assertIn("What to Review", self.skill_content[table_start:table_start+200])
        self.assertIn("Why", self.skill_content[table_start:table_start+200])

    def test_table_has_requirements_row(self):
        """Table should have Requirements phase row."""
        self.assertIn("**Requirements**", self.skill_content)

    def test_table_has_design_row(self):
        """Table should have Design phase row."""
        self.assertIn("**Design**", self.skill_content)

    def test_table_has_tasks_row(self):
        """Table should have Tasks phase row."""
        self.assertIn("**Tasks**", self.skill_content)

    def test_table_has_per_slice_phases(self):
        """Table should have per-slice Red and Green rows."""
        self.assertIn("**Impl: Per-Slice (Red)**", self.skill_content)
        self.assertIn("**Impl: Per-Slice (Green)**", self.skill_content)

    def test_table_has_coherence_row(self):
        """Table should have coherence phase row."""
        self.assertIn("**Impl: Post-Slices (Coherence)**", self.skill_content)


if __name__ == "__main__":
    unittest.main()
