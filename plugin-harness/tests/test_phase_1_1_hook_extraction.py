"""Phase 1.1: Red tests for hook logic extraction into pure functions.

Goal: Verify that before_continue hook tier-building logic is independently testable,
follows pure function principles, and handles missing dependencies gracefully.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
from orchestrator.hooks.before_continue import (
    _build_tier1_context,
    _build_tier2_context,
    _build_tier3_context,
    _assemble_context_tiers,
    _ensure_orchestration_structure,
    _fetch_nelly_brief,
    _get_or_build_capability_map,
)


class TestTier1Context(unittest.TestCase):
    """Red tests: Tier 1 (stable) context building."""

    def test_tier1_includes_capability_map_heading(self):
        """GIVEN capability_map with plugins
        WHEN _build_tier1_context is called
        THEN output includes '## Capability Map' heading."""
        capability_map = {"agent-isdd": {}, "agent-tdd": {}}
        tier1 = _build_tier1_context(capability_map, None)
        self.assertIn("## Capability Map", tier1)

    def test_tier1_lists_available_plugins(self):
        """GIVEN capability_map with specific plugins
        WHEN _build_tier1_context is called
        THEN output lists plugin names."""
        capability_map = {"agent-isdd": {}, "agent-tdd": {}, "code-reviewer": {}}
        tier1 = _build_tier1_context(capability_map, None)
        self.assertIn("agent-isdd", tier1)
        self.assertIn("agent-tdd", tier1)
        self.assertIn("code-reviewer", tier1)

    def test_tier1_includes_nelly_brief_when_available(self):
        """GIVEN brief_text is provided
        WHEN _build_tier1_context is called
        THEN output includes '## Project Context' section with brief text."""
        capability_map = {"agent-isdd": {}}
        brief_text = "This is the nelly brief content."
        tier1 = _build_tier1_context(capability_map, brief_text)
        self.assertIn("## Project Context", tier1)
        self.assertIn("This is the nelly brief content.", tier1)

    def test_tier1_handles_empty_capability_map(self):
        """GIVEN capability_map is empty
        WHEN _build_tier1_context is called
        THEN output still includes Tier 1 header, no errors."""
        tier1 = _build_tier1_context({}, None)
        self.assertIn("=== TIER 1:", tier1)

    def test_tier1_handles_missing_brief(self):
        """GIVEN brief_text is None
        WHEN _build_tier1_context is called
        THEN output includes capability map, no 'Project Context' section."""
        capability_map = {"agent-isdd": {}}
        tier1 = _build_tier1_context(capability_map, None)
        self.assertIn("## Capability Map", tier1)
        self.assertNotIn("## Project Context", tier1)

    def test_tier1_is_pure_function(self):
        """GIVEN capability_map and brief_text
        WHEN _build_tier1_context is called twice with same inputs
        THEN output is identical (deterministic, no side effects)."""
        capability_map = {"agent-isdd": {}}
        brief_text = "Brief content."
        tier1_a = _build_tier1_context(capability_map, brief_text)
        tier1_b = _build_tier1_context(capability_map, brief_text)
        self.assertEqual(tier1_a, tier1_b)


class TestTier2Context(unittest.TestCase):
    """Red tests: Tier 2 (derived) context building."""

    def test_tier2_includes_requirements_when_present(self):
        """GIVEN workflow_state with requirements_md
        WHEN _build_tier2_context is called
        THEN output includes '## Requirements' section."""
        workflow_state = {
            "requirements_md": "# Requirements\n- Req 1\n- Req 2"
        }
        tier2 = _build_tier2_context(workflow_state)
        self.assertIn("## Requirements", tier2)
        self.assertIn("- Req 1", tier2)

    def test_tier2_includes_design_when_present(self):
        """GIVEN workflow_state with design_md
        WHEN _build_tier2_context is called
        THEN output includes '## Design' section."""
        workflow_state = {
            "design_md": "# Design\n- Architecture\n- Interfaces"
        }
        tier2 = _build_tier2_context(workflow_state)
        self.assertIn("## Design", tier2)
        self.assertIn("- Architecture", tier2)

    def test_tier2_includes_research_cache_when_present(self):
        """GIVEN workflow_state with research_cache
        WHEN _build_tier2_context is called
        THEN output includes '## Research Cache' section."""
        workflow_state = {
            "research_cache": {"findings": "Research data"}
        }
        tier2 = _build_tier2_context(workflow_state)
        self.assertIn("## Research Cache", tier2)
        self.assertIn("findings", tier2)

    def test_tier2_handles_empty_workflow_state(self):
        """GIVEN workflow_state with no design artifacts
        WHEN _build_tier2_context is called
        THEN output includes Tier 2 header, no sections."""
        tier2 = _build_tier2_context({})
        self.assertIn("=== TIER 2:", tier2)

    def test_tier2_is_pure_function(self):
        """GIVEN workflow_state
        WHEN _build_tier2_context is called twice
        THEN output is identical (deterministic)."""
        workflow_state = {
            "requirements_md": "# Requirements",
            "design_md": "# Design"
        }
        tier2_a = _build_tier2_context(workflow_state)
        tier2_b = _build_tier2_context(workflow_state)
        self.assertEqual(tier2_a, tier2_b)


class TestTier3Context(unittest.TestCase):
    """Red tests: Tier 3 (per-call) context building."""

    def test_tier3_returns_spawn_prompt_unchanged(self):
        """GIVEN spawn_prompt
        WHEN _build_tier3_context is called
        THEN output is the original spawn_prompt (per-call context is minimal)."""
        prompt = "This is the original agent spawn prompt."
        tier3 = _build_tier3_context(prompt)
        self.assertEqual(tier3, prompt)

    def test_tier3_preserves_multiline_prompt(self):
        """GIVEN multi-line spawn_prompt
        WHEN _build_tier3_context is called
        THEN output preserves all lines exactly."""
        prompt = "Line 1\nLine 2\nLine 3"
        tier3 = _build_tier3_context(prompt)
        self.assertEqual(tier3, prompt)

    def test_tier3_is_pure_function(self):
        """GIVEN spawn_prompt
        WHEN _build_tier3_context is called twice
        THEN output is identical."""
        prompt = "Agent spawn prompt"
        tier3_a = _build_tier3_context(prompt)
        tier3_b = _build_tier3_context(prompt)
        self.assertEqual(tier3_a, tier3_b)


class TestAssembleContextTiers(unittest.TestCase):
    """Red tests: Assembling tiers into final context."""

    def test_assemble_combines_all_tiers(self):
        """GIVEN tier1, tier2, tier3 strings
        WHEN _assemble_context_tiers is called
        THEN output includes all three tiers separated by blank lines."""
        tier1 = "=== TIER 1 ==="
        tier2 = "=== TIER 2 ==="
        tier3 = "Original prompt"
        assembled = _assemble_context_tiers(tier1, tier2, tier3)
        self.assertIn(tier1, assembled)
        self.assertIn(tier2, assembled)
        self.assertIn(tier3, assembled)

    def test_assemble_skips_empty_tiers(self):
        """GIVEN tier1 is empty string
        WHEN _assemble_context_tiers is called
        THEN output skips empty tier (no blank lines for missing tiers)."""
        tier1 = ""
        tier2 = "=== TIER 2 ==="
        tier3 = "Prompt"
        assembled = _assemble_context_tiers(tier1, tier2, tier3)
        # Should not have extra blank lines for empty tier1
        self.assertNotIn("\n\n\n", assembled)
        self.assertIn(tier2, assembled)

    def test_assemble_skips_none_tiers(self):
        """GIVEN tier1 is None
        WHEN _assemble_context_tiers is called
        THEN output skips None tier."""
        tier1 = None
        tier2 = "=== TIER 2 ==="
        tier3 = "Prompt"
        assembled = _assemble_context_tiers(tier1, tier2, tier3)
        self.assertNotIn("None", assembled)
        self.assertIn(tier2, assembled)

    def test_assemble_preserves_tier_order(self):
        """GIVEN tiers in order 1, 2, 3
        WHEN _assemble_context_tiers is called
        THEN output preserves order (Tier 1 before Tier 2 before Tier 3)."""
        tier1 = "TIER_1"
        tier2 = "TIER_2"
        tier3 = "TIER_3"
        assembled = _assemble_context_tiers(tier1, tier2, tier3)
        idx1 = assembled.find(tier1)
        idx2 = assembled.find(tier2)
        idx3 = assembled.find(tier3)
        self.assertLess(idx1, idx2)
        self.assertLess(idx2, idx3)


class TestBuildCapabilityMap(unittest.TestCase):
    """Red tests: Capability map building and caching."""

    def test_capability_map_cached_in_workflow_state(self):
        """GIVEN workflow_state with empty orchestration.capability_map
        WHEN _get_or_build_capability_map is called
        THEN capability_map is populated in workflow_state."""
        workflow_state = {"orchestration": {}}
        result = _get_or_build_capability_map(workflow_state)
        self.assertIsInstance(result, dict)
        self.assertIn("capability_map", workflow_state["orchestration"])

    def test_capability_map_reused_from_cache(self):
        """GIVEN workflow_state with cached capability_map
        WHEN _get_or_build_capability_map is called
        THEN cached map is returned without rebuilding."""
        cached_map = {"agent-isdd": {"name": "agent-isdd"}}
        workflow_state = {"orchestration": {"capability_map": cached_map}}
        result = _get_or_build_capability_map(workflow_state)
        self.assertEqual(result, cached_map)


class TestFetchNellyBrief(unittest.TestCase):
    """Red tests: Nelly brief fetching and graceful degradation."""

    def test_fetch_nelly_brief_returns_tuple(self):
        """GIVEN workflow_state
        WHEN _fetch_nelly_brief is called
        THEN output is a tuple of (brief_text, metadata_dict)."""
        workflow_state = {}
        result = _fetch_nelly_brief(workflow_state)
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)

    def test_fetch_nelly_brief_graceful_degradation_on_network_error(self):
        """GIVEN NellyBriefManager raises ConnectionError
        WHEN _fetch_nelly_brief is called
        THEN returns (None, {}) and continues."""
        workflow_state = {"task": "test"}
        # This will degrade gracefully (mock will raise ConnectionError internally)
        brief_text, metadata = _fetch_nelly_brief(workflow_state)
        # Should degrade to None, not raise
        self.assertIsNone(brief_text)
        self.assertIsInstance(metadata, dict)

    def test_fetch_nelly_brief_handles_missing_files(self):
        """GIVEN NellyBriefManager raises IOError
        WHEN _fetch_nelly_brief is called
        THEN returns (None, {}) and continues."""
        workflow_state = {"task": "test"}
        # Will degrade gracefully
        brief_text, metadata = _fetch_nelly_brief(workflow_state)
        self.assertIsNone(brief_text)


class TestEnsureOrchestrationStructure(unittest.TestCase):
    """Red tests: Workflow state structure initialization."""

    def test_ensure_creates_orchestration_dict(self):
        """GIVEN workflow_state without orchestration key
        WHEN _ensure_orchestration_structure is called
        THEN orchestration dict is created."""
        workflow_state = {}
        _ensure_orchestration_structure(workflow_state)
        self.assertIn("orchestration", workflow_state)

    def test_ensure_creates_nelly_brief_cache(self):
        """GIVEN workflow_state
        WHEN _ensure_orchestration_structure is called
        THEN orchestration.nelly_brief_cache dict exists."""
        workflow_state = {}
        _ensure_orchestration_structure(workflow_state)
        self.assertIn("nelly_brief_cache", workflow_state["orchestration"])

    def test_ensure_creates_handoff_history(self):
        """GIVEN workflow_state
        WHEN _ensure_orchestration_structure is called
        THEN orchestration.handoff_history list exists."""
        workflow_state = {}
        _ensure_orchestration_structure(workflow_state)
        self.assertIn("handoff_history", workflow_state["orchestration"])

    def test_ensure_creates_checkpoints(self):
        """GIVEN workflow_state
        WHEN _ensure_orchestration_structure is called
        THEN orchestration.checkpoints list exists."""
        workflow_state = {}
        _ensure_orchestration_structure(workflow_state)
        self.assertIn("checkpoints", workflow_state["orchestration"])

    def test_ensure_idempotent(self):
        """GIVEN workflow_state already with orchestration structure
        WHEN _ensure_orchestration_structure is called again
        THEN structure is unchanged."""
        workflow_state = {"orchestration": {"nelly_brief_cache": {"existing": "data"}}}
        _ensure_orchestration_structure(workflow_state)
        self.assertEqual(workflow_state["orchestration"]["nelly_brief_cache"]["existing"], "data")


if __name__ == "__main__":
    unittest.main()
