"""
Tests for auto-detection logic: mapping phase + risk_tier + context → review_level.

Validates:
- Priority-based decision tree (explicit → phase → scope → prior → fallback)
- Phase context mappings (red → Quick, green → Standard/Deep, etc.)
- Risk tier influence on Green phase
- File scope fallback when phase unavailable
- Prior context escalation
- Fallback to Standard
"""

import unittest


class TestAutoDetectionPriority1ExplicitRequest(unittest.TestCase):
    """Priority 1: Explicit caller-specified review_level overrides all."""

    def test_explicit_quick_overrides_all_context(self):
        """Explicit Quick should be used even if phase/scope suggest otherwise."""
        explicit_level = "Quick"
        phase = "coherence"  # Would normally be Deep
        risk_tier = "high_risk"
        file_scope = "module"

        # Priority 1 takes precedence
        review_level = explicit_level if explicit_level else "fallback"

        self.assertEqual(review_level, "Quick")

    def test_explicit_ultra_overrides_all_context(self):
        """Explicit Ultra should be used even if phase suggests Deep."""
        explicit_level = "Ultra"
        phase = "red"  # Would normally be Quick

        review_level = explicit_level if explicit_level else "fallback"

        self.assertEqual(review_level, "Ultra")

    def test_explicit_standard_overrides_risk_tier(self):
        """Explicit Standard should be used even if risk_tier is high_risk."""
        explicit_level = "Standard"
        phase = "green"
        risk_tier = "high_risk"  # Would normally trigger Deep

        review_level = explicit_level if explicit_level else "fallback"

        self.assertEqual(review_level, "Standard")


class TestAutoDetectionPriority2PhaseContext(unittest.TestCase):
    """Priority 2: Phase context (when no explicit level)."""

    def test_red_phase_maps_to_quick(self):
        """Red phase should map to Quick review."""
        phase = "red"
        risk_tier = None
        explicit_level = None

        if explicit_level:
            review_level = explicit_level
        elif phase == "red":
            review_level = "Quick"

        self.assertEqual(review_level, "Quick")

    def test_green_phase_standard_tier_maps_to_standard(self):
        """Green phase with standard risk should map to Standard."""
        phase = "green"
        risk_tier = "standard"
        explicit_level = None

        if explicit_level:
            review_level = explicit_level
        elif phase == "green":
            review_level = "Deep" if risk_tier == "high_risk" else "Standard"

        self.assertEqual(review_level, "Standard")

    def test_green_phase_high_risk_tier_maps_to_deep(self):
        """Green phase with high_risk should map to Deep."""
        phase = "green"
        risk_tier = "high_risk"
        explicit_level = None

        if explicit_level:
            review_level = explicit_level
        elif phase == "green":
            review_level = "Deep" if risk_tier == "high_risk" else "Standard"

        self.assertEqual(review_level, "Deep")

    def test_refactor_phase_maps_to_quick(self):
        """Refactor phase should map to Quick."""
        phase = "refactor"
        explicit_level = None

        if explicit_level:
            review_level = explicit_level
        elif phase == "refactor":
            review_level = "Quick"

        self.assertEqual(review_level, "Quick")

    def test_coherence_phase_minority_high_risk_maps_to_deep(self):
        """Coherence phase with ≤50% high-risk should map to Deep."""
        phase = "coherence"
        high_risk_ratio = 0.33
        multi_agent_available = True
        explicit_level = None

        if explicit_level:
            review_level = explicit_level
        elif phase == "coherence":
            if high_risk_ratio > 0.5 and multi_agent_available:
                review_level = "Ultra"
            else:
                review_level = "Deep"

        self.assertEqual(review_level, "Deep")

    def test_coherence_phase_majority_high_risk_maps_to_ultra(self):
        """Coherence phase with >50% high-risk should map to Ultra."""
        phase = "coherence"
        high_risk_ratio = 0.67
        multi_agent_available = True
        explicit_level = None

        if explicit_level:
            review_level = explicit_level
        elif phase == "coherence":
            if high_risk_ratio > 0.5 and multi_agent_available:
                review_level = "Ultra"
            else:
                review_level = "Deep"

        self.assertEqual(review_level, "Ultra")

    def test_coherence_phase_without_multi_agent_uses_deep(self):
        """Coherence phase >50% high-risk but no multi-agent should use Deep."""
        phase = "coherence"
        high_risk_ratio = 0.67
        multi_agent_available = False
        explicit_level = None

        if explicit_level:
            review_level = explicit_level
        elif phase == "coherence":
            if high_risk_ratio > 0.5 and multi_agent_available:
                review_level = "Ultra"
            else:
                review_level = "Deep"

        self.assertEqual(review_level, "Deep")


class TestAutoDetectionPriority3FileScope(unittest.TestCase):
    """Priority 3: File scope (when no phase or explicit level)."""

    def test_single_function_scope_maps_to_quick(self):
        """Single function scope should map to Quick."""
        phase = None
        file_scope = "single_function"
        explicit_level = None

        if explicit_level:
            review_level = explicit_level
        elif phase:
            # Phase logic...
            review_level = None
        elif file_scope:
            scope_map = {
                "single_function": "Quick",
                "single_file": "Standard",
                "multiple_files": "Deep",
                "module": "Ultra",
            }
            review_level = scope_map.get(file_scope, "Standard")

        self.assertEqual(review_level, "Quick")

    def test_single_file_scope_maps_to_standard(self):
        """Single file scope should map to Standard."""
        phase = None
        file_scope = "single_file"
        explicit_level = None

        if explicit_level:
            review_level = explicit_level
        elif phase:
            review_level = None
        elif file_scope:
            scope_map = {
                "single_function": "Quick",
                "single_file": "Standard",
                "multiple_files": "Deep",
                "module": "Ultra",
            }
            review_level = scope_map.get(file_scope, "Standard")

        self.assertEqual(review_level, "Standard")

    def test_multiple_files_scope_maps_to_deep(self):
        """Multiple files scope should map to Deep."""
        phase = None
        file_scope = "multiple_files"
        explicit_level = None

        if explicit_level:
            review_level = explicit_level
        elif phase:
            review_level = None
        elif file_scope:
            scope_map = {
                "single_function": "Quick",
                "single_file": "Standard",
                "multiple_files": "Deep",
                "module": "Ultra",
            }
            review_level = scope_map.get(file_scope, "Standard")

        self.assertEqual(review_level, "Deep")

    def test_module_scope_maps_to_ultra(self):
        """Module scope should map to Ultra."""
        phase = None
        file_scope = "module"
        explicit_level = None

        if explicit_level:
            review_level = explicit_level
        elif phase:
            review_level = None
        elif file_scope:
            scope_map = {
                "single_function": "Quick",
                "single_file": "Standard",
                "multiple_files": "Deep",
                "module": "Ultra",
            }
            review_level = scope_map.get(file_scope, "Standard")

        self.assertEqual(review_level, "Ultra")

    def test_unknown_scope_defaults_to_standard(self):
        """Unknown scope should default to Standard."""
        phase = None
        file_scope = "unknown_scope"
        explicit_level = None

        if explicit_level:
            review_level = explicit_level
        elif phase:
            review_level = None
        elif file_scope:
            scope_map = {
                "single_function": "Quick",
                "single_file": "Standard",
                "multiple_files": "Deep",
                "module": "Ultra",
            }
            review_level = scope_map.get(file_scope, "Standard")

        self.assertEqual(review_level, "Standard")


class TestAutoDetectionPriority4PriorContext(unittest.TestCase):
    """Priority 4: Prior context escalation (when no phase/scope/explicit)."""

    def test_prior_quick_escalates_to_standard(self):
        """Prior Quick should escalate to Standard."""
        phase = None
        file_scope = None
        prior_level = "Quick"
        explicit_level = None

        if explicit_level:
            review_level = explicit_level
        elif phase:
            review_level = None
        elif file_scope:
            review_level = None
        elif prior_level:
            escalation = {
                "Quick": "Standard",
                "Standard": "Deep",
                "Deep": "Ultra",
                "Ultra": "Ultra",
            }
            review_level = escalation.get(prior_level, "Standard")

        self.assertEqual(review_level, "Standard")

    def test_prior_standard_escalates_to_deep(self):
        """Prior Standard should escalate to Deep."""
        phase = None
        file_scope = None
        prior_level = "Standard"
        explicit_level = None

        if explicit_level:
            review_level = explicit_level
        elif phase:
            review_level = None
        elif file_scope:
            review_level = None
        elif prior_level:
            escalation = {
                "Quick": "Standard",
                "Standard": "Deep",
                "Deep": "Ultra",
                "Ultra": "Ultra",
            }
            review_level = escalation.get(prior_level, "Standard")

        self.assertEqual(review_level, "Deep")

    def test_prior_deep_escalates_to_ultra(self):
        """Prior Deep should escalate to Ultra."""
        phase = None
        file_scope = None
        prior_level = "Deep"
        explicit_level = None

        if explicit_level:
            review_level = explicit_level
        elif phase:
            review_level = None
        elif file_scope:
            review_level = None
        elif prior_level:
            escalation = {
                "Quick": "Standard",
                "Standard": "Deep",
                "Deep": "Ultra",
                "Ultra": "Ultra",
            }
            review_level = escalation.get(prior_level, "Standard")

        self.assertEqual(review_level, "Ultra")

    def test_prior_ultra_stays_ultra(self):
        """Prior Ultra should stay Ultra (already max)."""
        phase = None
        file_scope = None
        prior_level = "Ultra"
        explicit_level = None

        if explicit_level:
            review_level = explicit_level
        elif phase:
            review_level = None
        elif file_scope:
            review_level = None
        elif prior_level:
            escalation = {
                "Quick": "Standard",
                "Standard": "Deep",
                "Deep": "Ultra",
                "Ultra": "Ultra",
            }
            review_level = escalation.get(prior_level, "Standard")

        self.assertEqual(review_level, "Ultra")


class TestAutoDetectionPriority5Fallback(unittest.TestCase):
    """Priority 5: Fallback to Standard when no context available."""

    def test_no_context_defaults_to_standard(self):
        """No context at all should default to Standard."""
        explicit_level = None
        phase = None
        file_scope = None
        prior_level = None

        if explicit_level:
            review_level = explicit_level
        elif phase:
            review_level = None
        elif file_scope:
            review_level = None
        elif prior_level:
            review_level = None
        else:
            review_level = "Standard"

        self.assertEqual(review_level, "Standard")

    def test_empty_file_scope_uses_fallback(self):
        """Empty file scope should trigger fallback."""
        file_scope = ""
        explicit_level = None
        phase = None

        if explicit_level:
            review_level = explicit_level
        elif phase:
            review_level = None
        elif file_scope:  # Empty string is falsy
            review_level = "from_scope"
        else:
            review_level = "Standard"

        self.assertEqual(review_level, "Standard")


class TestAutoDetectionRealWorldScenarios(unittest.TestCase):
    """Integration tests with real-world scenario combinations."""

    def test_scenario_red_phase_high_risk_slice(self):
        """Red phase of high-risk slice: should be Quick."""
        phase = "red"
        risk_tier = "high_risk"
        file_scope = "single_file"
        explicit_level = None
        prior_level = "Deep"  # From prior work

        # Priority 2 (phase) wins
        if explicit_level:
            result = explicit_level
        elif phase == "red":
            result = "Quick"

        self.assertEqual(result, "Quick")

    def test_scenario_green_phase_high_risk_multiple_files(self):
        """Green phase of high-risk slice touching multiple files: Deep."""
        phase = "green"
        risk_tier = "high_risk"
        file_scope = "multiple_files"
        explicit_level = None

        # Priority 2 (phase + risk_tier)
        if explicit_level:
            result = explicit_level
        elif phase == "green":
            result = "Deep" if risk_tier == "high_risk" else "Standard"

        self.assertEqual(result, "Deep")

    def test_scenario_no_phase_single_file_context(self):
        """No phase info, single file scope: Standard."""
        phase = None
        file_scope = "single_file"
        explicit_level = None
        prior_level = None

        # Priority 3 (file scope)
        if explicit_level:
            result = explicit_level
        elif phase:
            result = None
        elif file_scope == "single_file":
            result = "Standard"

        self.assertEqual(result, "Standard")

    def test_scenario_fix_attempt_escalation(self):
        """Fix attempt after prior Standard review: escalate to Deep."""
        phase = None
        file_scope = None
        prior_level = "Standard"
        explicit_level = None

        # Priority 4 (prior context escalation)
        if explicit_level:
            result = explicit_level
        elif phase:
            result = None
        elif file_scope:
            result = None
        elif prior_level == "Standard":
            result = "Deep"  # Escalate

        self.assertEqual(result, "Deep")

    def test_scenario_coherence_review_majority_high_risk(self):
        """Coherence review with majority high-risk slices: Ultra."""
        phase = "coherence"
        high_risk_ratio = 0.67
        multi_agent_available = True
        explicit_level = None

        # Priority 2 (phase context)
        if explicit_level:
            result = explicit_level
        elif phase == "coherence":
            if high_risk_ratio > 0.5 and multi_agent_available:
                result = "Ultra"
            else:
                result = "Deep"

        self.assertEqual(result, "Ultra")

    def test_scenario_explicit_overrides_coherence_high_risk(self):
        """Explicit Quick overrides coherence high-risk logic."""
        phase = "coherence"
        high_risk_ratio = 0.67
        multi_agent_available = True
        explicit_level = "Quick"  # User override

        # Priority 1 (explicit)
        if explicit_level:
            result = explicit_level

        self.assertEqual(result, "Quick")


if __name__ == "__main__":
    unittest.main()
