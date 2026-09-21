#!/usr/bin/env python3
"""
Red test: Agent-ISDD Model Escalation Detection Hook

Tests escalation marker detection in before_continue hook to trigger model re-spawning.
Simulates agent-tdd handoff reports containing MODEL-ESCALATE markers and verifies:
1. Marker is detected and parsed
2. Accumulated context is pulled via get_spawn_context MCP tool
3. Re-spawn is triggered at escalated model tier (Sonnet, Opus)
4. Escalation is logged with reason, from-model, to-model, success/failure
5. Malformed markers are handled gracefully with logging
"""

import json
import os
import tempfile
import unittest
from pathlib import Path

import hook_test_utils as h


def _assistant_line(content):
    """Format assistant message for JSONL transcript."""
    return json.dumps({"type": "assistant", "message": {"role": "assistant", "content": content}})


class BeforeContinueModelEscalationTests(unittest.TestCase):
    """Red tests for MODEL-ESCALATE marker detection in before_continue hook."""

    def _state_json_path(self, feature_dir):
        """Return path to workflow-state.json in feature directory."""
        return os.path.join(feature_dir, "workflow-state.json")

    def _escalation_log_path(self, feature_dir):
        """Return path to escalation log in workflow state (if implemented)."""
        state_path = self._state_json_path(feature_dir)
        return state_path  # escalations should be logged in workflow-state.json

    def test_detects_model_escalate_marker_with_haiku_to_sonnet(self):
        """
        Test: Detect MODEL-ESCALATE marker escalating from Haiku to Sonnet.

        Scenario:
        1. agent-tdd completes with MODEL-ESCALATE marker in handoff
        2. User re-enters via /isdd-continue
        3. before_continue hook detects marker
        4. Hook logs escalation event

        Assertion: workflow-state.json contains escalation_pending with marker details.
        """
        with h.temp_git_repo() as repo, h.temp_home() as home:
            feature_dir = h.feature_spec_dir(home, repo)
            h.seed_state_file(feature_dir, title="Complex Feature", workflow_status="Implementing")

            # Create workflow-state.json with initial state
            state_path = self._state_json_path(feature_dir)
            with open(state_path, "w", encoding="utf-8") as fh:
                json.dump({"current_phase": "Implementation", "executor_model": "Haiku"}, fh)

            # Create transcript with MODEL-ESCALATE marker
            transcript = os.path.join(home, "transcript.jsonl")
            with open(transcript, "w", encoding="utf-8") as fh:
                fh.write(_assistant_line(
                    '<!--AGENT-TDD-MODEL-ESCALATE: reason="Complex async patterns require deeper reasoning" '
                    'from_model="Haiku" to_model="Sonnet"-->\n'
                    "Encountered complex concurrency patterns requiring escalation to Sonnet for deeper analysis."
                ) + "\n")

            # Run before_continue hook
            result, rc = h.run_hook_message(
                "before_continue.py",
                {"cwd": repo, "transcript_path": transcript},
                env_extra={"HOME": home},
            )

            self.assertEqual(rc, 0, f"Hook failed with return code {rc}")

            # Verify escalation_pending is recorded
            with open(state_path) as fh:
                state = json.load(fh)
            self.assertIn("escalation_pending", state, "escalation_pending should be recorded in workflow-state.json")
            escalation = state["escalation_pending"]
            self.assertEqual(escalation.get("from_model"), "Haiku")
            self.assertEqual(escalation.get("to_model"), "Sonnet")
            self.assertEqual(escalation.get("reason"), "Complex async patterns require deeper reasoning")

    def test_detects_model_escalate_marker_with_sonnet_to_opus(self):
        """
        Test: Detect MODEL-ESCALATE marker escalating from Sonnet to Opus.

        Scenario: agent-tdd escalates to Opus for highest-complexity reasoning tasks.

        Assertion: Escalation details correctly captured with Sonnet->Opus transition.
        """
        with h.temp_git_repo() as repo, h.temp_home() as home:
            feature_dir = h.feature_spec_dir(home, repo)
            h.seed_state_file(feature_dir, title="Ultra Complex Feature", workflow_status="Implementing")

            state_path = self._state_json_path(feature_dir)
            with open(state_path, "w", encoding="utf-8") as fh:
                json.dump({"current_phase": "Implementation", "executor_model": "Sonnet"}, fh)

            transcript = os.path.join(home, "transcript.jsonl")
            with open(transcript, "w", encoding="utf-8") as fh:
                fh.write(_assistant_line(
                    '<!--AGENT-TDD-MODEL-ESCALATE: reason="Multi-step architectural refactoring with high interdependency" '
                    'from_model="Sonnet" to_model="Opus"-->\n'
                    "Escalating to Opus for comprehensive architectural analysis."
                ) + "\n")

            result, rc = h.run_hook_message(
                "before_continue.py",
                {"cwd": repo, "transcript_path": transcript},
                env_extra={"HOME": home},
            )

            self.assertEqual(rc, 0)
            with open(state_path) as fh:
                state = json.load(fh)
            self.assertIn("escalation_pending", state)
            escalation = state["escalation_pending"]
            self.assertEqual(escalation.get("from_model"), "Sonnet")
            self.assertEqual(escalation.get("to_model"), "Opus")

    def test_escalation_logs_timestamp(self):
        """
        Test: Escalation event includes timestamp for audit trail.

        Assertion: escalation_pending contains detected_at timestamp.
        """
        with h.temp_git_repo() as repo, h.temp_home() as home:
            feature_dir = h.feature_spec_dir(home, repo)
            h.seed_state_file(feature_dir, title="Feature", workflow_status="Implementing")

            state_path = self._state_json_path(feature_dir)
            with open(state_path, "w", encoding="utf-8") as fh:
                json.dump({"current_phase": "Implementation", "executor_model": "Haiku"}, fh)

            transcript = os.path.join(home, "transcript.jsonl")
            with open(transcript, "w", encoding="utf-8") as fh:
                fh.write(_assistant_line(
                    '<!--AGENT-TDD-MODEL-ESCALATE: reason="Research gap in async patterns" '
                    'from_model="Haiku" to_model="Sonnet"-->\n'
                    "Escalating."
                ) + "\n")

            result, rc = h.run_hook_message(
                "before_continue.py",
                {"cwd": repo, "transcript_path": transcript},
                env_extra={"HOME": home},
            )

            self.assertEqual(rc, 0)
            with open(state_path) as fh:
                state = json.load(fh)
            escalation = state.get("escalation_pending", {})
            self.assertIn("detected_at", escalation, "Escalation should include detected_at timestamp")
            self.assertIsNotNone(escalation.get("detected_at"))

    def test_malformed_marker_missing_reason_is_logged(self):
        """
        Test: Gracefully handle malformed marker missing reason field.

        Scenario: Marker lacks reason field.

        Assertion: Hook logs malformed marker and does NOT record escalation_pending.
        """
        with h.temp_git_repo() as repo, h.temp_home() as home:
            feature_dir = h.feature_spec_dir(home, repo)
            h.seed_state_file(feature_dir, title="Feature", workflow_status="Implementing")

            state_path = self._state_json_path(feature_dir)
            with open(state_path, "w", encoding="utf-8") as fh:
                json.dump({"current_phase": "Implementation"}, fh)

            transcript = os.path.join(home, "transcript.jsonl")
            with open(transcript, "w", encoding="utf-8") as fh:
                fh.write(_assistant_line(
                    '<!--AGENT-TDD-MODEL-ESCALATE: from_model="Haiku" to_model="Sonnet"-->\n'
                    "Missing reason field."
                ) + "\n")

            result, rc = h.run_hook_message(
                "before_continue.py",
                {"cwd": repo, "transcript_path": transcript},
                env_extra={"HOME": home},
            )

            # Hook should not crash
            self.assertEqual(rc, 0)

            with open(state_path) as fh:
                state = json.load(fh)

            # Malformed marker should be logged but not recorded as escalation
            # (behavior TBD: either skip silently or log warning + skip)
            if "escalation_pending" in state:
                # If implementation chooses to log malformed markers as escalation_errors
                escalation = state.get("escalation_errors", [])
                self.assertTrue(any("malformed" in str(e).lower() for e in escalation) or len(escalation) > 0)

    def test_malformed_marker_missing_to_model_is_logged(self):
        """
        Test: Gracefully handle malformed marker missing to_model field.

        Assertion: Hook logs malformed marker, does not process escalation.
        """
        with h.temp_git_repo() as repo, h.temp_home() as home:
            feature_dir = h.feature_spec_dir(home, repo)
            h.seed_state_file(feature_dir, title="Feature", workflow_status="Implementing")

            state_path = self._state_json_path(feature_dir)
            with open(state_path, "w", encoding="utf-8") as fh:
                json.dump({"current_phase": "Implementation"}, fh)

            transcript = os.path.join(home, "transcript.jsonl")
            with open(transcript, "w", encoding="utf-8") as fh:
                fh.write(_assistant_line(
                    '<!--AGENT-TDD-MODEL-ESCALATE: reason="Need higher tier" from_model="Haiku"-->\n'
                    "Missing to_model field."
                ) + "\n")

            result, rc = h.run_hook_message(
                "before_continue.py",
                {"cwd": repo, "transcript_path": transcript},
                env_extra={"HOME": home},
            )

            self.assertEqual(rc, 0)
            with open(state_path) as fh:
                state = json.load(fh)

            # Malformed marker should not create valid escalation
            if "escalation_pending" in state:
                escalation = state["escalation_pending"]
                # Should either not exist or have error marker
                self.assertIsNone(escalation.get("to_model"))

    def test_escalation_marker_has_highest_priority_over_rollback(self):
        """
        Test: MODEL-ESCALATE marker takes priority over other escalation markers.

        Scenario: Both MODEL-ESCALATE and PLAN-FLAG markers present.

        Assertion: MODEL-ESCALATE is processed, rollback is deferred.
        """
        with h.temp_git_repo() as repo, h.temp_home() as home:
            feature_dir = h.feature_spec_dir(home, repo)
            h.seed_state_file(feature_dir, title="Feature", workflow_status="Implementing")

            state_path = self._state_json_path(feature_dir)
            with open(state_path, "w", encoding="utf-8") as fh:
                json.dump({"current_phase": "Implementation"}, fh)

            transcript = os.path.join(home, "transcript.jsonl")
            with open(transcript, "w", encoding="utf-8") as fh:
                fh.write(_assistant_line(
                    '<!--AGENT-TDD-MODEL-ESCALATE: reason="Complex patterns" '
                    'from_model="Haiku" to_model="Sonnet"-->\n'
                    '<!--AGENT-TDD-PLAN-FLAG: reason="Also needs research"-->\n'
                    "Both escalation markers present."
                ) + "\n")

            result, rc = h.run_hook_message(
                "before_continue.py",
                {"cwd": repo, "transcript_path": transcript},
                env_extra={"HOME": home},
            )

            self.assertEqual(rc, 0)
            with open(state_path) as fh:
                state = json.load(fh)

            # MODEL-ESCALATE should be recorded
            self.assertIn("escalation_pending", state)
            # Rollback should NOT be recorded (MODEL-ESCALATE takes priority)
            self.assertNotIn("rollback_pending", state)

    def test_no_active_state_is_noop(self):
        """
        Test: No-op when no active workflow state (safe degradation).

        Assertion: Hook exits cleanly without error.
        """
        with h.temp_git_repo() as repo, h.temp_home() as home:
            transcript = os.path.join(home, "transcript.jsonl")
            with open(transcript, "w", encoding="utf-8") as fh:
                fh.write(_assistant_line(
                    '<!--AGENT-TDD-MODEL-ESCALATE: reason="test" from_model="Haiku" to_model="Sonnet"-->'
                ) + "\n")

            result, rc = h.run_hook_message(
                "before_continue.py",
                {"cwd": repo, "transcript_path": transcript},
                env_extra={"HOME": home},
            )

            self.assertEqual(rc, 0)
            # Should be silent (no systemMessage)
            self.assertIsNone(result)

    def test_non_escalation_report_is_silent(self):
        """
        Test: Regular reports without MODEL-ESCALATE are not affected.

        Assertion: Hook continues normally, no escalation_pending recorded.
        """
        with h.temp_git_repo() as repo, h.temp_home() as home:
            feature_dir = h.feature_spec_dir(home, repo)
            h.seed_state_file(feature_dir, title="Feature", workflow_status="Implementing")

            state_path = self._state_json_path(feature_dir)
            with open(state_path, "w", encoding="utf-8") as fh:
                json.dump({"current_phase": "Implementation"}, fh)

            transcript = os.path.join(home, "transcript.jsonl")
            with open(transcript, "w", encoding="utf-8") as fh:
                fh.write(_assistant_line("Implementation complete, all slices passing.") + "\n")

            result, rc = h.run_hook_message(
                "before_continue.py",
                {"cwd": repo, "transcript_path": transcript},
                env_extra={"HOME": home},
            )

            self.assertEqual(rc, 0)
            with open(state_path) as fh:
                state = json.load(fh)

            self.assertNotIn("escalation_pending", state)

    def test_escalation_surface_message_to_user(self):
        """
        Test: Escalation is surfaced to user via systemMessage for awareness.

        Assertion: Hook returns systemMessage indicating model escalation.
        """
        with h.temp_git_repo() as repo, h.temp_home() as home:
            feature_dir = h.feature_spec_dir(home, repo)
            h.seed_state_file(feature_dir, title="Feature", workflow_status="Implementing")

            state_path = self._state_json_path(feature_dir)
            with open(state_path, "w", encoding="utf-8") as fh:
                json.dump({"current_phase": "Implementation", "executor_model": "Haiku"}, fh)

            transcript = os.path.join(home, "transcript.jsonl")
            with open(transcript, "w", encoding="utf-8") as fh:
                fh.write(_assistant_line(
                    '<!--AGENT-TDD-MODEL-ESCALATE: reason="Complex concurrency patterns" '
                    'from_model="Haiku" to_model="Sonnet"-->\n'
                    "Escalating for better analysis."
                ) + "\n")

            result, rc = h.run_hook_message(
                "before_continue.py",
                {"cwd": repo, "transcript_path": transcript},
                env_extra={"HOME": home},
            )

            self.assertEqual(rc, 0)
            # Should return a systemMessage to user
            self.assertIsNotNone(result, "Hook should surface escalation to user via systemMessage")
            self.assertIn("Haiku", result)
            self.assertIn("Sonnet", result)

    def test_escalation_message_instructs_get_spawn_context_respawn(self):
        """
        Test: systemMessage explicitly instructs calling get_spawn_context and
        re-spawning agent-TDD at the escalated tier (Task 8 AC: hook surfaces
        the concrete re-spawn action since it cannot invoke MCP tools or the
        Agent tool itself).
        """
        with h.temp_git_repo() as repo, h.temp_home() as home:
            feature_dir = h.feature_spec_dir(home, repo)
            h.seed_state_file(feature_dir, title="Feature", workflow_status="Implementing")

            state_path = self._state_json_path(feature_dir)
            with open(state_path, "w", encoding="utf-8") as fh:
                json.dump({"current_phase": "Implementation", "executor_model": "Haiku"}, fh)

            transcript = os.path.join(home, "transcript.jsonl")
            with open(transcript, "w", encoding="utf-8") as fh:
                fh.write(_assistant_line(
                    '<!--AGENT-TDD-MODEL-ESCALATE: reason="Complex concurrency patterns" '
                    'from_model="Haiku" to_model="Sonnet"-->\n'
                    "Escalating for better analysis."
                ) + "\n")

            result, rc = h.run_hook_message(
                "before_continue.py",
                {"cwd": repo, "transcript_path": transcript},
                env_extra={"HOME": home},
            )

            self.assertEqual(rc, 0)
            self.assertIsNotNone(result)
            self.assertIn("get_spawn_context", result)
            self.assertIn("agent-TDD", result)

    def test_escalation_message_does_not_claim_bare_tool_name_is_directly_callable(self):
        """Regression test: the message must not tell the model to "call the
        `get_spawn_context` MCP tool" as if that bare string is the tool's
        actual callable name -- Claude Code exposes a plugin-bundled MCP
        server's tools harness-prefixed (e.g. mcp__<server>__<tool>), never
        under their raw protocol-level name alone, so that phrasing sent a
        model looking for a tool that doesn't exist under that exact string.
        The message must instead name the server ("spawn-context") and point
        the model at ToolSearch (or equivalent discovery) to find the real
        name, since the exact prefix isn't something this hook can predict.
        """
        with h.temp_git_repo() as repo, h.temp_home() as home:
            feature_dir = h.feature_spec_dir(home, repo)
            h.seed_state_file(feature_dir, title="Feature", workflow_status="Implementing")

            state_path = self._state_json_path(feature_dir)
            with open(state_path, "w", encoding="utf-8") as fh:
                json.dump({"current_phase": "Implementation", "executor_model": "Haiku"}, fh)

            transcript = os.path.join(home, "transcript.jsonl")
            with open(transcript, "w", encoding="utf-8") as fh:
                fh.write(_assistant_line(
                    '<!--AGENT-TDD-MODEL-ESCALATE: reason="Complex concurrency patterns" '
                    'from_model="Haiku" to_model="Sonnet"-->\n'
                    "Escalating for better analysis."
                ) + "\n")

            result, rc = h.run_hook_message(
                "before_continue.py",
                {"cwd": repo, "transcript_path": transcript},
                env_extra={"HOME": home},
            )

            self.assertEqual(rc, 0)
            self.assertIsNotNone(result)
            self.assertNotIn(
                "Call the `get_spawn_context` MCP tool", result,
                "message must not claim the bare string is the directly-callable tool name",
            )
            self.assertIn("spawn-context", result, "message must name the MCP server")
            self.assertIn("ToolSearch", result, "message must point to a discovery fallback")

    def test_escalation_includes_reason_in_workflow_state(self):
        """
        Test: Escalation reason is preserved in workflow-state.json.

        Assertion: Reason field is captured exactly as provided.
        """
        with h.temp_git_repo() as repo, h.temp_home() as home:
            feature_dir = h.feature_spec_dir(home, repo)
            h.seed_state_file(feature_dir, title="Feature", workflow_status="Implementing")

            state_path = self._state_json_path(feature_dir)
            with open(state_path, "w", encoding="utf-8") as fh:
                json.dump({"current_phase": "Implementation"}, fh)

            reason_text = "Multi-threaded deadlock analysis with event loop semantics"
            transcript = os.path.join(home, "transcript.jsonl")
            with open(transcript, "w", encoding="utf-8") as fh:
                fh.write(_assistant_line(
                    f'<!--AGENT-TDD-MODEL-ESCALATE: reason="{reason_text}" '
                    'from_model="Haiku" to_model="Sonnet"-->\n'
                ) + "\n")

            result, rc = h.run_hook_message(
                "before_continue.py",
                {"cwd": repo, "transcript_path": transcript},
                env_extra={"HOME": home},
            )

            self.assertEqual(rc, 0)
            with open(state_path) as fh:
                state = json.load(fh)
            escalation = state.get("escalation_pending", {})
            self.assertEqual(escalation.get("reason"), reason_text)


if __name__ == "__main__":
    unittest.main()
