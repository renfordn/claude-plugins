"""
Tests for code-reviewer SKILL.md ISDD phase context documentation.

Validates that the Auto-Detection Rules section correctly documents
phase-to-level mapping and priority ordering for ISDD workflows.
"""

import unittest
from pathlib import Path


class TestISddPhaseContextDocumentation(unittest.TestCase):
    """Tests for ISDD phase context in SKILL.md Auto-Detection Rules."""

    @classmethod
    def setUpClass(cls):
        skill_path = Path(__file__).parent.parent / "skills" / "code-reviewer" / "SKILL.md"
        with open(skill_path) as f:
            cls.skill_content = f.read()

    def test_isdd_phase_context_section_exists(self):
        """ISDD workflow phase context should be present in auto-detection rules."""
        self.assertIn("ISDD workflow phase", self.skill_content)

    def test_auto_detection_in_workflows_header_present(self):
        """Auto-Detection Rules header should be present."""
        self.assertIn("Auto-Detection Rules", self.skill_content)

    def test_phase_to_level_mapping_table_exists(self):
        """Phase-to-level mapping should be present (bullet list form)."""
        self.assertIn("ISDD workflow phase", self.skill_content)
        # Mapping bullets use the → arrow convention
        self.assertIn("→", self.skill_content)

    def test_requirements_phase_documented(self):
        """Requirements phase should be documented with Standard level."""
        self.assertIn("Requirements", self.skill_content)
        self.assertIn("EARS formatting", self.skill_content)

    def test_design_phase_documented(self):
        """Design phase should be documented with Deep level."""
        self.assertIn("Design", self.skill_content)
        self.assertIn("Deep", self.skill_content)

    def test_tasks_phase_documented(self):
        """Tasks phase should be documented with Standard level."""
        self.assertIn("Tasks", self.skill_content)
        # phrasing appears in the Tasks bullet
        self.assertIn("phrasing", self.skill_content)

    def test_per_slice_red_phase_documented(self):
        """Per-slice Red phase should be documented with Quick level."""
        self.assertIn("Impl per-slice (Red)", self.skill_content)
        self.assertIn("Quick", self.skill_content)
        self.assertIn("test intent", self.skill_content)

    def test_per_slice_green_phase_documented(self):
        """Per-slice Green phase should be documented with Standard/Deep."""
        self.assertIn("Impl per-slice (Green)", self.skill_content)
        self.assertIn("risk_tier: high_risk", self.skill_content)

    def test_coherence_phase_documented(self):
        """Post-slices Coherence phase should be documented with Deep/Ultra."""
        self.assertIn("Impl post-slices (Coherence)", self.skill_content)
        self.assertIn("majority high-risk", self.skill_content)

    def test_auto_detection_priority_documented(self):
        """Auto-detection priority order should be documented."""
        self.assertIn("Auto-Detection Rules", self.skill_content)
        self.assertIn("Explicit request", self.skill_content)

    def test_explicit_request_is_priority_1(self):
        """Explicit request should be priority 1."""
        self.assertIn("1. **Explicit request**", self.skill_content)

    def test_phase_context_is_priority_2(self):
        """ISDD workflow phase should be priority 2."""
        self.assertIn("2. **ISDD workflow phase**", self.skill_content)

    def test_file_scope_is_priority_3(self):
        """File scope should be priority 3."""
        self.assertIn("3. **File scope**", self.skill_content)

    def test_prior_context_is_priority_4(self):
        """Prior context should be priority 4."""
        self.assertIn("4. **Prior context**", self.skill_content)

    def test_fallback_is_priority_5(self):
        """Fallback should be priority 5."""
        self.assertIn("5. **Fallback**", self.skill_content)

    def test_examples_provided(self):
        """Concrete level examples should appear in the auto-detection section."""
        # Phase-specific level examples are given inline with the bullet items
        self.assertIn("`Quick`", self.skill_content)
        self.assertIn("`Standard`", self.skill_content)
        self.assertIn("`Deep`", self.skill_content)
        self.assertIn("`Ultra`", self.skill_content)

    def test_red_phase_example(self):
        """Red phase should map to Quick."""
        idx = self.skill_content.find("Impl per-slice (Red)")
        self.assertNotEqual(idx, -1)
        context = self.skill_content[idx:idx + 80]
        self.assertIn("Quick", context)

    def test_green_standard_tier_example(self):
        """Green phase should map to Standard (default)."""
        idx = self.skill_content.find("Impl per-slice (Green)")
        self.assertNotEqual(idx, -1)
        context = self.skill_content[idx:idx + 80]
        self.assertIn("Standard", context)

    def test_green_high_risk_example(self):
        """Green phase high-risk should map to Deep."""
        idx = self.skill_content.find("Impl per-slice (Green)")
        self.assertNotEqual(idx, -1)
        context = self.skill_content[idx:idx + 80]
        self.assertIn("Deep", context)

    def test_coherence_high_risk_multi_agent_example(self):
        """Coherence review majority-high-risk with multi-agent should map to Ultra."""
        idx = self.skill_content.find("Impl post-slices (Coherence)")
        self.assertNotEqual(idx, -1)
        context = self.skill_content[idx:idx + 120]
        self.assertIn("Ultra", context)

    def test_coherence_high_risk_no_multi_agent_example(self):
        """Coherence review should default to Deep when multi-agent unavailable."""
        idx = self.skill_content.find("Impl post-slices (Coherence)")
        self.assertNotEqual(idx, -1)
        context = self.skill_content[idx:idx + 80]
        self.assertIn("Deep", context)

    def test_key_insight_present(self):
        """Graceful Degradation section should explain fallback behaviour."""
        self.assertIn("Graceful Degradation", self.skill_content)

    def test_cross_references_section_present(self):
        """Review Levels section should document all four levels."""
        for level in ["Quick", "Standard", "Deep", "Ultra"]:
            self.assertIn(level, self.skill_content)

    def test_agent_tdd_skill_referenced(self):
        """agent-tdd concepts should be present (risk_tier referenced)."""
        self.assertIn("risk_tier", self.skill_content)

    def test_agent_isdd_interop_referenced(self):
        """ISDD workflow phases should be explicitly referenced."""
        self.assertIn("ISDD workflow phase", self.skill_content)

    def test_agent_tdd_auto_detection_logic_referenced(self):
        """Multi-agent availability should be documented in auto-detection."""
        self.assertIn("multi-agent", self.skill_content)

    def test_design_md_auto_detection_referenced(self):
        """Auto-Detection Rules section should exist."""
        self.assertIn("### Auto-Detection Rules", self.skill_content)

    def test_section_formatting_consistent(self):
        """Auto-Detection Rules should use consistent markdown formatting."""
        self.assertIn("### Auto-Detection Rules", self.skill_content)
        # Priorities use bold numbering
        self.assertIn("**Explicit request**", self.skill_content)
        self.assertIn("**ISDD workflow phase**", self.skill_content)

    def test_language_clarity(self):
        """Language should be clear and use the canonical terms."""
        self.assertIn("infers", self.skill_content)
        self.assertIn("priority order", self.skill_content)

    def test_no_conflicts_with_existing_sections(self):
        """Auto-Detection Rules section should be present once."""
        count = self.skill_content.count("### Auto-Detection Rules")
        self.assertEqual(count, 1, "Auto-Detection Rules should appear exactly once")


class TestPhaseContextTableStructure(unittest.TestCase):
    """Tests for the phase mapping content structure in SKILL.md."""

    @classmethod
    def setUpClass(cls):
        skill_path = Path(__file__).parent.parent / "skills" / "code-reviewer" / "SKILL.md"
        with open(skill_path) as f:
            cls.skill_content = f.read()

    def test_table_has_all_columns(self):
        """Auto-detection phase mapping should cover ISDD phase, level, and purpose."""
        self.assertIn("ISDD workflow phase", self.skill_content)
        # Purpose expressed as inline bullet explanations
        self.assertIn("EARS formatting", self.skill_content)
        self.assertIn("file touchpoints", self.skill_content)

    def test_table_has_requirements_row(self):
        """Requirements phase should be mapped."""
        self.assertIn("Requirements", self.skill_content)
        self.assertIn("Standard", self.skill_content)

    def test_table_has_design_row(self):
        """Design phase should be mapped."""
        self.assertIn("Design", self.skill_content)
        self.assertIn("Deep", self.skill_content)

    def test_table_has_tasks_row(self):
        """Tasks phase should be mapped."""
        self.assertIn("Tasks", self.skill_content)

    def test_table_has_per_slice_phases(self):
        """Per-slice Red and Green phases should be documented."""
        self.assertIn("Impl per-slice (Red)", self.skill_content)
        self.assertIn("Impl per-slice (Green)", self.skill_content)

    def test_table_has_coherence_row(self):
        """Coherence phase should be documented."""
        self.assertIn("Impl post-slices (Coherence)", self.skill_content)


if __name__ == "__main__":
    unittest.main()
