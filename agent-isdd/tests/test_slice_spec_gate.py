"""Tests for hooks/slice_spec_gate.py.

PreToolUse hard-deny gate, originally written pre-Phase-2+3 for every agent-tdd:agent-TDD /
agent-tdd:test-author spawn, then disabled (removed from hooks.json) once Phase 2+3 made the
Design Spec handoff (no field-labeled Slice Spec text at all) the normal path. Re-enabled
2026-09-17, scoped to `Track: Fast` only (see the hook's own module docstring) -- every test
here seeds a `Track` value via hook_test_utils.seed_state_file so the track-scoping itself
gets direct coverage, not just the field-presence checks.

High-risk per tasks.md: a false positive here blocks a legitimate handoff, so every
required-field case gets its own test.
"""
import unittest

import hook_test_utils as h

COMPLETE_PROMPT = """
Task description: Implement the thing.
Ordered Steps:
1. Write a failing test.
2. Make it pass.
Test Intent: Add tests/test_thing.py covering the happy path.
Risk Tier: standard
Data Contracts And Interfaces: ThingService.do_thing(x) -> bool
"""

# Per agent-tdd/skills/slice-spec/SKILL.md's field-subset rule, a real test-author spawn
# never includes Risk Tier, Pre-Slice Brief, or Review handoff mode (agent-TDD-only concerns).
TEST_AUTHOR_PROMPT = """
Task description: Implement the thing.
Test Intent: Add tests/test_thing.py covering the happy path.
Data Contracts And Interfaces: ThingService.do_thing(x) -> bool
"""


def _prompt_without(section_line, base=COMPLETE_PROMPT):
    lines = [l for l in base.splitlines() if section_line not in l]
    return "\n".join(lines)


class SliceSpecGateTests(unittest.TestCase):
    def _call(self, repo, home, subagent_type, prompt):
        return h.run_hook(
            "slice_spec_gate.py",
            {"cwd": repo, "tool_input": {"subagent_type": subagent_type, "prompt": prompt}},
            env_extra={"HOME": home},
        )

    def _call_fast_track(self, subagent_type, prompt):
        """Convenience wrapper: seeds Track: Fast in a fresh repo/home, then calls the hook.
        Most tests only care about the field-presence logic once track-scoping is known to
        work (see test_track_standard_is_noop / test_no_active_workflow_is_noop for that)."""
        with h.temp_git_repo() as repo, h.temp_home() as home:
            feature_dir = h.feature_spec_dir(home, repo)
            h.seed_state_file(feature_dir, title="Fast Feature", track="Fast")
            return self._call(repo, home, subagent_type, prompt)

    def test_unrelated_subagent_type_is_noop(self):
        decision, rc = self._call_fast_track("agent-isdd:research-consolidator", COMPLETE_PROMPT)
        self.assertEqual(rc, 0)
        self.assertIsNone(decision)

    def test_no_active_workflow_is_noop(self):
        """No workflow-state.md at all: no-op regardless of prompt shape, same as
        design_spec_gate.py's own "not this plugin's business" precedent."""
        with h.temp_git_repo() as repo, h.temp_home() as home:
            decision, rc = self._call(repo, home, "agent-tdd:agent-TDD", COMPLETE_PROMPT)
            self.assertEqual(rc, 0)
            self.assertIsNone(decision)

    def test_track_standard_is_noop_even_for_a_slice_spec_shaped_prompt(self):
        """The whole point of track-scoping: Track: Standard must no-op unconditionally, so
        this gate can never misfire on the still-live Design Spec path -- checked here with a
        prompt that *would* pass the field check, to isolate the track gate itself."""
        with h.temp_git_repo() as repo, h.temp_home() as home:
            feature_dir = h.feature_spec_dir(home, repo)
            h.seed_state_file(feature_dir, title="Standard Feature", track="Standard")
            decision, rc = self._call(repo, home, "agent-tdd:agent-TDD", COMPLETE_PROMPT)
            self.assertEqual(rc, 0)
            self.assertIsNone(decision)

    def test_track_missing_defaults_to_standard_and_is_noop(self):
        """Absent Track (a feature started before this field existed) means Standard -- same
        precedent as every other optional field in workflow-state.md/.json."""
        with h.temp_git_repo() as repo, h.temp_home() as home:
            feature_dir = h.feature_spec_dir(home, repo)
            h.seed_state_file(feature_dir, title="Old Feature")  # no track field at all
            decision, rc = self._call(repo, home, "agent-tdd:agent-TDD", COMPLETE_PROMPT)
            self.assertEqual(rc, 0)
            self.assertIsNone(decision)

    def test_test_author_is_gated_under_track_standard(self):
        """Unlike agent-TDD, test-author's prompt shape is never ambiguous by Track -- both
        Standard's own high-risk path and Fast Track's pass it the same field-labeled subset,
        so its check must apply even when Track: Standard would no-op agent-TDD's."""
        with h.temp_git_repo() as repo, h.temp_home() as home:
            feature_dir = h.feature_spec_dir(home, repo)
            h.seed_state_file(feature_dir, title="Standard Feature", track="Standard")
            decision, rc = self._call(repo, home, "agent-tdd:test-author", TEST_AUTHOR_PROMPT)
            self.assertEqual(rc, 0)
            self.assertEqual(decision["permissionDecision"], "allow")

            decision, rc = self._call(
                repo, home, "agent-tdd:test-author",
                _prompt_without("Task description:", base=TEST_AUTHOR_PROMPT),
            )
            self.assertEqual(decision["permissionDecision"], "deny")

    def test_test_author_is_gated_with_no_active_workflow(self):
        """test-author's contract is agent-tdd's own, independent of any agent-isdd SDD
        workflow being active at all (agent-tdd is usable standalone) -- unlike agent-TDD,
        which needs an active workflow to even know which Track it's on."""
        with h.temp_git_repo() as repo, h.temp_home() as home:
            decision, rc = self._call(
                repo, home, "agent-tdd:test-author",
                _prompt_without("Task description:", base=TEST_AUTHOR_PROMPT),
            )
            self.assertEqual(rc, 0)
            self.assertEqual(decision["permissionDecision"], "deny")
            self.assertIn("Task description", decision["permissionDecisionReason"])

    def test_complete_slice_spec_is_allowed(self):
        decision, rc = self._call_fast_track("agent-tdd:agent-TDD", COMPLETE_PROMPT)
        self.assertEqual(rc, 0)
        self.assertIsNotNone(decision)
        self.assertEqual(decision["permissionDecision"], "allow")

    def test_test_author_subagent_type_is_also_gated(self):
        decision, rc = self._call_fast_track("agent-tdd:test-author", COMPLETE_PROMPT)
        self.assertEqual(rc, 0)
        self.assertIsNotNone(decision)
        self.assertEqual(decision["permissionDecision"], "allow")

    def test_realistic_test_author_prompt_without_risk_tier_is_allowed(self):
        """A real test-author spawn per agent-tdd's own contract never includes Risk Tier --
        the gate must not require a field that subagent_type's own prompt shape omits."""
        decision, rc = self._call_fast_track("agent-tdd:test-author", TEST_AUTHOR_PROMPT)
        self.assertEqual(rc, 0)
        self.assertIsNotNone(decision)
        self.assertEqual(decision["permissionDecision"], "allow")

    def test_test_author_missing_task_description_is_still_denied(self):
        decision, rc = self._call_fast_track(
            "agent-tdd:test-author",
            _prompt_without("Task description:", base=TEST_AUTHOR_PROMPT),
        )
        self.assertEqual(rc, 0)
        self.assertEqual(decision["permissionDecision"], "deny")
        self.assertIn("Task description", decision["permissionDecisionReason"])
        self.assertNotIn("Risk Tier", decision["permissionDecisionReason"])

    def test_missing_task_description_is_denied(self):
        decision, rc = self._call_fast_track("agent-tdd:agent-TDD", _prompt_without("Task description:"))
        self.assertEqual(rc, 0)
        self.assertEqual(decision["permissionDecision"], "deny")
        self.assertIn("Task description", decision["permissionDecisionReason"])

    def test_missing_test_intent_is_denied(self):
        decision, rc = self._call_fast_track("agent-tdd:agent-TDD", _prompt_without("Test Intent:"))
        self.assertEqual(rc, 0)
        self.assertEqual(decision["permissionDecision"], "deny")
        self.assertIn("Test Intent", decision["permissionDecisionReason"])

    def test_missing_risk_tier_is_denied(self):
        decision, rc = self._call_fast_track("agent-tdd:agent-TDD", _prompt_without("Risk Tier:"))
        self.assertEqual(rc, 0)
        self.assertEqual(decision["permissionDecision"], "deny")
        self.assertIn("Risk Tier", decision["permissionDecisionReason"])

    def test_missing_data_contracts_is_denied(self):
        decision, rc = self._call_fast_track("agent-tdd:agent-TDD", _prompt_without("Data Contracts"))
        self.assertEqual(rc, 0)
        self.assertEqual(decision["permissionDecision"], "deny")
        self.assertIn("Data Contracts", decision["permissionDecisionReason"])

    def test_malformed_payload_is_noop(self):
        decision, rc = h.run_hook("slice_spec_gate.py", {})
        self.assertEqual(rc, 0)
        self.assertIsNone(decision)


if __name__ == "__main__":
    unittest.main()
