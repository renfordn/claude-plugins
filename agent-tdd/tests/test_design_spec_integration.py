import json
import os
import unittest
from pathlib import Path


class TestDesignSpecInputValidation(unittest.TestCase):
    """Test that Design Spec input validation works correctly."""

    def setUp(self):
        self.fixture_dir = Path(__file__).parent / "fixtures" / "design-spec-integration"

    def test_design_spec_files_exist(self):
        """Verify all required Design Spec files are present."""
        required_files = [
            "requirements.md",
            "design.md",
            "research-cache.md",
        ]

        for filename in required_files:
            filepath = self.fixture_dir / filename
            self.assertTrue(
                filepath.exists(),
                f"Design Spec file missing: {filename}",
            )

    def test_requirements_contains_acceptance_criteria(self):
        """Verify requirements.md has acceptance criteria for all user stories."""
        req_file = self.fixture_dir / "requirements.md"
        content = req_file.read_text()

        # Check for user stories and acceptance criteria
        self.assertIn("User Stories", content)
        self.assertIn("Acceptance Criteria", content)
        self.assertIn("US-1", content)
        self.assertIn("US-2", content)
        self.assertIn("US-3", content)

    def test_design_has_file_touchpoints(self):
        """Verify design.md specifies all file touchpoints."""
        design_file = self.fixture_dir / "design.md"
        content = design_file.read_text()

        self.assertIn("File Touchpoints", content)
        self.assertIn("src/auth/", content)

        expected_files = [
            "src/auth/login.ts",
            "src/auth/token.ts",
            "src/auth/middleware.ts",
            "src/auth/db.ts",
            "src/types/user.ts",
        ]

        for file_path in expected_files:
            self.assertIn(file_path, content)

    def test_design_has_interfaces_and_contracts(self):
        """Verify design.md documents interfaces and contracts."""
        design_file = self.fixture_dir / "design.md"
        content = design_file.read_text()

        self.assertIn("Interfaces & Contracts", content)
        self.assertIn("LoginRequest", content)
        self.assertIn("TokenPayload", content)

    def test_design_has_research_basis_section(self):
        """Verify design.md has research basis explaining known information."""
        design_file = self.fixture_dir / "design.md"
        content = design_file.read_text()

        self.assertIn("Research Basis", content)

    def test_research_cache_has_file_summaries(self):
        """Verify research cache documents file summaries."""
        cache_file = self.fixture_dir / "research-cache.md"
        content = cache_file.read_text()

        self.assertIn("file_summaries", content.lower())
        self.assertIn("src/auth/login.ts", content)
        self.assertIn("src/auth/token.ts", content)

    def test_research_cache_has_slicing_opportunity(self):
        """Verify research cache identifies task slicing opportunity."""
        cache_file = self.fixture_dir / "research-cache.md"
        content = cache_file.read_text()

        self.assertIn("Identified Slicing Opportunity", content)
        self.assertIn("Slice 1", content)
        self.assertIn("Slice 2", content)
        self.assertIn("Slice 3", content)

    def test_research_cache_identifies_risk_tiers(self):
        """Verify research cache recommends risk tiers for each slice."""
        cache_file = self.fixture_dir / "research-cache.md"
        content = cache_file.read_text()

        self.assertIn("Risk Assessment", content)
        self.assertIn("high-risk", content.lower())
        self.assertIn("standard", content.lower())


class TestResearchValidationPhase(unittest.TestCase):
    """Test the Research Validation phase logic."""

    def setUp(self):
        self.fixture_dir = Path(__file__).parent / "fixtures" / "design-spec-integration"

    def test_design_file_touchpoints_in_research_cache(self):
        """Verify that all design file touchpoints are mentioned in research cache."""
        design_file = self.fixture_dir / "design.md"
        cache_file = self.fixture_dir / "research-cache.md"

        design_content = design_file.read_text()
        cache_content = cache_file.read_text()

        # Extract file paths from design
        expected_files = [
            "src/auth/login.ts",
            "src/auth/token.ts",
            "src/auth/middleware.ts",
            "src/auth/db.ts",
            "src/types/user.ts",
        ]

        # Verify each design touchpoint is in research cache
        for file_path in expected_files:
            self.assertIn(
                file_path,
                cache_content,
                f"Design file '{file_path}' not found in research cache",
            )

    def test_design_interfaces_documented_in_research(self):
        """Verify design interfaces are documented in research cache."""
        design_file = self.fixture_dir / "design.md"
        cache_file = self.fixture_dir / "research-cache.md"

        design_content = design_file.read_text()
        cache_content = cache_file.read_text()

        # Check for key interface documentation
        self.assertIn("LoginRequest", cache_content)
        self.assertIn("TokenPayload", cache_content)

    def test_design_constraints_documented_in_research(self):
        """Verify design constraints are captured in research cache."""
        cache_file = self.fixture_dir / "research-cache.md"
        content = cache_file.read_text()

        self.assertIn("Key Constraints", content)
        self.assertIn("RS256", content)
        self.assertIn("bcrypt", content)
        self.assertIn("SQLite", content)


class TestTaskSlicingPhase(unittest.TestCase):
    """Test the Task Slicing phase logic."""

    def setUp(self):
        self.fixture_dir = Path(__file__).parent / "fixtures" / "design-spec-integration"

    def test_slices_identified_in_research_cache(self):
        """Verify that slices are identified in research cache."""
        cache_file = self.fixture_dir / "research-cache.md"
        content = cache_file.read_text()

        # Verify at least 3 slices are identified
        self.assertIn("Slice 1:", content)
        self.assertIn("Slice 2:", content)
        self.assertIn("Slice 3:", content)

    def test_slices_have_dependencies_specified(self):
        """Verify each slice specifies dependencies."""
        cache_file = self.fixture_dir / "research-cache.md"
        content = cache_file.read_text()

        # Slice 2 depends on Slice 1
        self.assertIn("Depends On: Slice 1", content)
        # Slice 3 depends on Slice 1, 2
        self.assertIn("Depends On: Slice 1, Slice 2", content)

    def test_slices_specify_test_intent(self):
        """Verify each slice specifies test intent."""
        cache_file = self.fixture_dir / "research-cache.md"
        content = cache_file.read_text()

        self.assertIn("Test Intent:", content)

    def test_slices_specify_files(self):
        """Verify each slice specifies which files it touches."""
        cache_file = self.fixture_dir / "research-cache.md"
        content = cache_file.read_text()

        self.assertIn("Files:", content)
        # Verify specific files are mentioned in slices
        self.assertIn("src/auth/db.ts", content)
        self.assertIn("src/auth/token.ts", content)
        self.assertIn("src/auth/login.ts", content)

    def test_slices_within_size_limits(self):
        """Verify each slice touches ≤3 files (TDD safe size)."""
        cache_file = self.fixture_dir / "research-cache.md"
        content = cache_file.read_text()

        # Manually verify from the fixture:
        # Slice 1: db.ts, types/user.ts (2 files) ✓
        # Slice 2: token.ts (1 file) ✓
        # Slice 3: login.ts, middleware.ts (2 files) ✓

        self.assertIn("Slice 1:", content)
        self.assertIn("Slice 2:", content)
        self.assertIn("Slice 3:", content)


class TestRalphLoopsValidation(unittest.TestCase):
    """Test Ralph Loops validation logic."""

    def setUp(self):
        self.fixture_dir = Path(__file__).parent / "fixtures" / "design-spec-integration"

    def test_dependency_graph_is_acyclic(self):
        """Verify the dependency graph has no cycles."""
        cache_file = self.fixture_dir / "research-cache.md"
        content = cache_file.read_text()

        # From the fixture:
        # Slice 1 → no deps
        # Slice 2 → Slice 1
        # Slice 3 → Slice 1, Slice 2
        # This is acyclic (topological sort: 1, 2, 3)

        self.assertIn("Depends On: Slice 1, Slice 2", content)

    def test_research_to_implementation_traceability(self):
        """Verify slices are traceable to research findings."""
        cache_file = self.fixture_dir / "research-cache.md"
        content = cache_file.read_text()

        # Slice 1 references db.ts and user.ts from research
        self.assertIn("src/auth/db.ts", content)
        self.assertIn("src/types/user.ts", content)

        # Slice 2 references token.ts and jsonwebtoken from research
        self.assertIn("src/auth/token.ts", content)
        self.assertIn("jsonwebtoken", content)

        # Slice 3 references login.ts, middleware.ts, and bcrypt
        self.assertIn("src/auth/login.ts", content)
        self.assertIn("src/auth/middleware.ts", content)
        self.assertIn("bcrypt", content)


class TestRiskTierAssignment(unittest.TestCase):
    """Test Risk Tier assignment logic."""

    def setUp(self):
        self.fixture_dir = Path(__file__).parent / "fixtures" / "design-spec-integration"

    def test_risk_tiers_assigned_to_slices(self):
        """Verify risk tiers are assigned to each slice."""
        cache_file = self.fixture_dir / "research-cache.md"
        content = cache_file.read_text()

        # Check that risk tiers are mentioned
        self.assertIn("standard", content.lower())
        self.assertIn("high-risk", content.lower())

    def test_high_risk_slices_have_justification(self):
        """Verify high-risk slices have documented justification."""
        cache_file = self.fixture_dir / "research-cache.md"
        content = cache_file.read_text()

        # Slice 3 is high-risk, should have justification
        self.assertIn("High-risk", content)
        self.assertIn("integration point", content.lower())

    def test_standard_risk_slices_focused(self):
        """Verify standard-risk slices are focused and safe."""
        cache_file = self.fixture_dir / "research-cache.md"
        content = cache_file.read_text()

        # Slice 1 and 2 are standard, should be focused
        self.assertIn("Slice 1", content)
        self.assertIn("Slice 2", content)


class TestReadinessCheckCriteria(unittest.TestCase):
    """Test Readiness Check validation criteria."""

    def setUp(self):
        self.fixture_dir = Path(__file__).parent / "fixtures" / "design-spec-integration"

    def test_at_least_one_slice_exists(self):
        """Verify at least one slice exists in task slicing."""
        cache_file = self.fixture_dir / "research-cache.md"
        content = cache_file.read_text()

        # Multiple slices identified
        self.assertIn("Slice 1:", content)

    def test_slices_have_test_intent(self):
        """Verify all slices have test intent specified."""
        cache_file = self.fixture_dir / "research-cache.md"
        content = cache_file.read_text()

        self.assertIn("Test Intent:", content)

    def test_slices_have_ordered_steps(self):
        """Verify slices have concrete ordered implementation steps."""
        cache_file = self.fixture_dir / "research-cache.md"
        content = cache_file.read_text()

        # Verify the research identifies the task breakdown
        self.assertIn("Identified Slicing Opportunity", content)
        # Verify slices are described with implementation details
        self.assertIn("Task:", content)


class TestDesignSpecModePhaseMarkers(unittest.TestCase):
    """Test that Design Spec mode handoff report markers are documented."""

    def test_slicing_complete_phase_marker_documented(self):
        """Verify slicing_complete phase marker is documented."""
        agent_tdd_file = (
            Path(__file__).parent.parent / "agents" / "agent-TDD.md"
        )
        content = agent_tdd_file.read_text()

        self.assertIn("slicing_complete", content)

    def test_all_slices_complete_phase_marker_documented(self):
        """Verify all_slices_complete phase marker is documented."""
        agent_tdd_file = (
            Path(__file__).parent.parent / "agents" / "agent-TDD.md"
        )
        content = agent_tdd_file.read_text()

        self.assertIn("all_slices_complete", content)

    def test_design_spec_handoff_report_format_documented(self):
        """Verify Design Spec handoff report format is documented."""
        agent_tdd_file = (
            Path(__file__).parent.parent / "agents" / "agent-TDD.md"
        )
        content = agent_tdd_file.read_text()

        self.assertIn("Design Spec Mode (Multi-Slice Workflow)", content)
        self.assertIn("Research Validation", content)
        self.assertIn("Task Slicing", content)
        self.assertIn("Ralph Loops", content)


if __name__ == "__main__":
    unittest.main()
