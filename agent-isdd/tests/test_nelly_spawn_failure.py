"""Tests for hooks/nelly_spawn_failure.py.

The exact real-world shape of a failed `Agent` PostToolUse `tool_response` (subagent_type not
found) was not available to confirm against during authoring -- see this hook's module
docstring and the agent-tdd handoff report for this slice. Every payload shape used below is
this test's own explicit assumption about that shape (an `is_error`-style dict field, or a
content string/block list containing "not found" alongside the subagent_type name), not a
confirmed production fixture. Kept deliberately conservative/fail-closed to match the hook.
"""
import json
import os
import unittest

import hook_test_utils as h


def _seed_state(home, repo, agent_nelly_available=True):
    feature_dir = h.feature_spec_dir(home, repo)
    h.seed_state_file(feature_dir, title="My Feature", workflow_status="In Progress")
    json_path = os.path.join(feature_dir, "workflow-state.json")
    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump({"current_phase": "Requirements",
                    "agent_nelly_available": agent_nelly_available}, fh)
    return feature_dir, json_path


class NellySpawnFailureTests(unittest.TestCase):
    def test_failed_spawn_dict_is_error_clears_cache(self):
        """Assumed shape: tool_response is a dict with a truthy `is_error` field."""
        with h.temp_git_repo() as repo, h.temp_home() as home:
            _feature_dir, json_path = _seed_state(home, repo, agent_nelly_available=True)
            payload = {
                "cwd": repo,
                "tool_input": {"subagent_type": "agent-nelly:agent-nelly"},
                "tool_response": {"is_error": True, "content": "subagent_type not found"},
            }
            msg, rc = h.run_hook_message(
                "nelly_spawn_failure.py", payload, env_extra={"HOME": home}
            )
            self.assertEqual(rc, 0)
            self.assertIsNotNone(msg)
            with open(json_path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            self.assertFalse(data["agent_nelly_available"])

    def test_failed_spawn_content_block_list_clears_cache(self):
        """Assumed shape: tool_response is a dict whose `content` is a list of text blocks."""
        with h.temp_git_repo() as repo, h.temp_home() as home:
            _feature_dir, json_path = _seed_state(home, repo, agent_nelly_available=True)
            payload = {
                "cwd": repo,
                "tool_input": {"subagent_type": "agent-nelly:agent-nelly"},
                "tool_response": {
                    "content": [
                        {"type": "text",
                         "text": "Error: subagent_type 'agent-nelly:agent-nelly' not found"}
                    ]
                },
            }
            msg, rc = h.run_hook_message(
                "nelly_spawn_failure.py", payload, env_extra={"HOME": home}
            )
            self.assertEqual(rc, 0)
            self.assertIsNotNone(msg)
            with open(json_path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            self.assertFalse(data["agent_nelly_available"])

    def test_successful_spawn_is_a_noop(self):
        """Regression guard: a normal, successful spawn response must never clear the cache."""
        with h.temp_git_repo() as repo, h.temp_home() as home:
            _feature_dir, json_path = _seed_state(home, repo, agent_nelly_available=True)
            payload = {
                "cwd": repo,
                "tool_input": {"subagent_type": "agent-nelly:agent-nelly"},
                "tool_response": {"content": [{"type": "text", "text": "Intent captured."}]},
            }
            msg, rc = h.run_hook_message(
                "nelly_spawn_failure.py", payload, env_extra={"HOME": home}
            )
            self.assertEqual(rc, 0)
            self.assertIsNone(msg)
            with open(json_path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            self.assertTrue(data["agent_nelly_available"])

    def test_ambiguous_payload_shape_is_a_noop(self):
        """Fail-closed guard: an unrecognized tool_response shape (e.g. an int) must never be
        treated as a failure -- no crash, no clear."""
        with h.temp_git_repo() as repo, h.temp_home() as home:
            _feature_dir, json_path = _seed_state(home, repo, agent_nelly_available=True)
            payload = {
                "cwd": repo,
                "tool_input": {"subagent_type": "agent-nelly:agent-nelly"},
                "tool_response": 42,
            }
            msg, rc = h.run_hook_message(
                "nelly_spawn_failure.py", payload, env_extra={"HOME": home}
            )
            self.assertEqual(rc, 0)
            self.assertIsNone(msg)
            with open(json_path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            self.assertTrue(data["agent_nelly_available"])

    def test_unrelated_subagent_type_is_a_noop(self):
        """Scoped to agent-nelly:agent-nelly only -- agent-tdd:agent-TDD is out of scope by
        design (see module docstring); any other spawn must pass through untouched."""
        with h.temp_git_repo() as repo, h.temp_home() as home:
            _feature_dir, json_path = _seed_state(home, repo, agent_nelly_available=True)
            payload = {
                "cwd": repo,
                "tool_input": {"subagent_type": "agent-tdd:agent-TDD"},
                "tool_response": {"is_error": True, "content": "subagent_type not found"},
            }
            msg, rc = h.run_hook_message(
                "nelly_spawn_failure.py", payload, env_extra={"HOME": home}
            )
            self.assertEqual(rc, 0)
            self.assertIsNone(msg)
            with open(json_path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            self.assertTrue(data["agent_nelly_available"])

    def test_already_false_cache_is_a_noop(self):
        """Regression guard: nothing stale to clear when the cache is already False."""
        with h.temp_git_repo() as repo, h.temp_home() as home:
            _feature_dir, json_path = _seed_state(home, repo, agent_nelly_available=False)
            payload = {
                "cwd": repo,
                "tool_input": {"subagent_type": "agent-nelly:agent-nelly"},
                "tool_response": {"is_error": True, "content": "subagent_type not found"},
            }
            msg, rc = h.run_hook_message(
                "nelly_spawn_failure.py", payload, env_extra={"HOME": home}
            )
            self.assertEqual(rc, 0)
            self.assertIsNone(msg)


if __name__ == "__main__":
    unittest.main()
