import os
import unittest
from pathlib import Path


class TestEscalationPathsDocumentation(unittest.TestCase):
    """Verify that two-way escalation paths are fully documented."""

    def setUp(self):
        self.escalation_doc = (
            Path(__file__).parent.parent / "references" / "escalation-paths.md"
        )

    def test_escalation_paths_file_exists(self):
        """Verify escalation paths documentation exists."""
        self.assertTrue(
            self.escalation_doc.exists(),
            "escalation-paths.md not found",
        )

    def test_documents_research_validation_escalations(self):
        """Verify Research Validation phase escalations documented."""
        content = self.escalation_doc.read_text()

        self.assertIn("Research Validation", content)
        self.assertIn("Research Too Thin", content)
        self.assertIn("Design Contradicts Research", content)
        self.assertIn("Constraint Mismatch", content)

    def test_documents_task_slicing_escalations(self):
        """Verify Task Slicing phase escalations documented."""
        content = self.escalation_doc.read_text()

        self.assertIn("Task Slicing", content)
        self.assertIn("Product Decision", content)
        self.assertIn("High-Risk Slice Cannot Be Split", content)

    def test_documents_per_slice_implementation_escalations(self):
        """Verify Per-Slice Implementation escalations documented."""
        content = self.escalation_doc.read_text()

        self.assertIn("Per-Slice Implementation", content)
        self.assertIn("Mid-Slice Research Request", content)
        self.assertIn("Plan Validity Flag", content)
        self.assertIn("Test Cannot Pass", content)

    def test_documents_research_gap_flag_marker(self):
        """Verify Research Gap Flag marker format documented."""
        content = self.escalation_doc.read_text()

        self.assertIn("AGENT-TDD-RESEARCH-GAP", content)
        self.assertIn("Research Gap Flag", content)

    def test_documents_plan_validity_flag_marker(self):
        """Verify Plan Validity Flag marker format documented."""
        content = self.escalation_doc.read_text()

        self.assertIn("AGENT-TDD-PLAN-FLAG", content)
        self.assertIn("Plan Validity Flag", content)

    def test_documents_resume_mechanism(self):
        """Verify Resume mechanism is documented."""
        content = self.escalation_doc.read_text()

        self.assertIn("Resume Mechanism", content)
        self.assertIn("before-continue", content)
        self.assertIn("SendMessage", content)

    def test_two_way_escalation_clearly_stated(self):
        """Verify two-way escalation is explicitly documented."""
        content = self.escalation_doc.read_text()

        self.assertIn("two-way", content.lower())
        self.assertIn("escalation", content.lower())
        self.assertIn("one-directional", content.lower())

    def test_documents_escalation_table(self):
        """Verify escalation summary table is provided."""
        content = self.escalation_doc.read_text()

        self.assertIn("Escalation Summary Table", content)
        self.assertIn("Phase", content)
        self.assertIn("Agent-TDD Action", content)
        self.assertIn("Agent-ISDD Action", content)

    def test_documents_key_properties(self):
        """Verify key properties of two-way escalation documented."""
        content = self.escalation_doc.read_text()

        self.assertIn("Explicit Pause Points", content)
        self.assertIn("Specific Escalation Reasons", content)
        self.assertIn("Design Authority Preserved", content)
        self.assertIn("Research Authority Preserved", content)
        self.assertIn("Task Authority Preserved", content)

    def test_includes_example_flows(self):
        """Verify example escalation flows are provided."""
        content = self.escalation_doc.read_text()

        self.assertIn("Examples of Escalation Flows", content)
        self.assertIn("Example 1", content)
        self.assertIn("Example 2", content)

    def test_guarantees_documented(self):
        """Verify escalation guarantees are clearly documented."""
        content = self.escalation_doc.read_text()

        self.assertIn("Agent-TDD Guarantees to Escalate When", content)
        self.assertIn("Does NOT Silently", content)


class TestAgentTDDDocumentsEscalations(unittest.TestCase):
    """Verify agent-TDD.md references escalation paths."""

    def setUp(self):
        self.agent_tdd_file = Path(__file__).parent.parent / "agents" / "agent-TDD.md"

    def test_agent_tdd_references_escalation_paths(self):
        """Verify agent-TDD.md references the escalation paths documentation."""
        content = self.agent_tdd_file.read_text()

        # Check for escalation-related content
        self.assertIn("Escalation", content)
        self.assertIn("escalate", content.lower())

    def test_agent_tdd_documents_mid_slice_research_request(self):
        """Verify Mid-Slice Research Request is documented."""
        content = self.agent_tdd_file.read_text()

        self.assertIn("Mid-Slice Research Request", content)
        self.assertIn("Research Gap Flag", content)

    def test_agent_tdd_documents_plan_validity_flag(self):
        """Verify Plan Validity Flag is documented."""
        content = self.agent_tdd_file.read_text()

        self.assertIn("Plan Validity Flag", content)

    def test_agent_tdd_documents_design_spec_escalations(self):
        """Verify Design Spec mode escalations are documented in agent-TDD.md."""
        content = self.agent_tdd_file.read_text()

        self.assertIn("Escalation Paths (Design Spec Mode)", content)
        self.assertIn("research thin", content.lower())
        self.assertIn("design contradicts", content.lower())


class TestInteropDocumentsEscalations(unittest.TestCase):
    """Verify INTEROP.md documents escalation paths."""

    def setUp(self):
        self.interop_file = Path(__file__).parent.parent / "INTEROP.md"

    def test_interop_documents_escalation_paths(self):
        """Verify INTEROP.md mentions escalation paths."""
        content = self.interop_file.read_text()

        self.assertIn("Escalation", content)

    def test_interop_documents_one_directional_handoff(self):
        """Verify INTEROP.md clarifies one-directional handoff."""
        content = self.interop_file.read_text()

        self.assertIn("one-directional", content.lower())


if __name__ == "__main__":
    unittest.main()
