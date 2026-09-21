"""Tests for mcp_server/spawn_context.py's build_spawn_context_response.

Pins Slice 7 (Plugin-Orchestrator -> Plugin-Harness Rework): get_spawn_context's
pure-Python core, split out of mcp_server/server.py specifically so it's
importable/testable without pulling in the `mcp` package (see this
environment's pre-existing mcp/pydantic incompatibility, noted in this
feature's recap.md -- `import mcp` itself raises TypeError under the
installed pydantic/CPython combination, not just ImportError, so
server.py's own module can't be imported directly in this environment.
spawn_context.py has zero `mcp` dependency, so it's fully testable here).

Covers both response shapes design.md calls for:
  - SDD-workflow-active: unchanged from before this feature (reads
    workflow_state["orchestration"]["last_spawn_context"]).
  - Standalone (no active SDD workflow): reads whatever
    handle_standalone_spawn has already cached in HarnessContextCache
    (read-only -- never calls handle_standalone_spawn itself).
"""
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "mcp_server")
)

from spawn_context import build_spawn_context_response  # noqa: E402
from orchestrator.harness_context_cache import HarnessContextCache  # noqa: E402


class TestSDDWorkflowActiveResponseUnchanged(unittest.TestCase):
    """The workflow_state_path(cwd) is not None branch must behave exactly
    as get_spawn_context did before this feature."""

    def test_no_active_workflow_state_but_state_path_missing_handled_by_standalone_branch(self):
        # workflow_state_path returning None routes to the standalone branch,
        # not this class's concern -- see TestStandaloneResponse below.
        pass

    def test_returns_joined_tiers_when_last_spawn_context_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            state_path = os.path.join(tmp, "workflow-state.json")
            fake_state = {
                "orchestration": {
                    "last_spawn_context": {
                        "tier1_context": "TIER1",
                        "tier2_context": "TIER2",
                        "error_pattern_context": None,
                    }
                }
            }
            with patch("spawn_context.workflow_state_path", return_value=state_path), \
                 patch("spawn_context.load_workflow_state", return_value=fake_state):
                result = build_spawn_context_response("agent-tdd", tmp)
        self.assertEqual(result, "TIER1\n\nTIER2")

    def test_returns_message_when_workflow_state_load_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            state_path = os.path.join(tmp, "workflow-state.json")
            with patch("spawn_context.workflow_state_path", return_value=state_path), \
                 patch("spawn_context.load_workflow_state", return_value={}):
                result = build_spawn_context_response("agent-tdd", tmp)
        self.assertIn("could not be loaded", result)

    def test_returns_message_when_no_last_spawn_context_cached(self):
        with tempfile.TemporaryDirectory() as tmp:
            state_path = os.path.join(tmp, "workflow-state.json")
            fake_state = {"orchestration": {}}
            with patch("spawn_context.workflow_state_path", return_value=state_path), \
                 patch("spawn_context.load_workflow_state", return_value=fake_state):
                result = build_spawn_context_response("agent-tdd", tmp)
        self.assertIn("proceed with your own research", result)


class TestStandaloneResponse(unittest.TestCase):
    """workflow_state_path(cwd) is None -> read HarnessContextCache instead,
    never call handle_standalone_spawn (read-only contract)."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.cwd = "/some/standalone/project"

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_returns_no_context_message_when_cache_is_empty(self):
        with patch("spawn_context.workflow_state_path", return_value=None), \
             patch.dict(os.environ, {"CLAUDE_PLUGIN_DATA": self.tmpdir.name}):
            result = build_spawn_context_response("agent-tdd", self.cwd)
        self.assertIn("proceed with your own research", result)

    def test_returns_capability_map_and_nelly_brief_from_cache(self):
        import importlib
        hook_state = importlib.import_module("hook_state")
        slug = hook_state.project_slug(self.cwd)

        with patch.dict(os.environ, {"CLAUDE_PLUGIN_DATA": self.tmpdir.name}):
            cache = HarnessContextCache(slug)
            cache.set("capability_map", {"agent-isdd": {"name": "agent-isdd"}}, 3600)
            cache.set(
                "nelly_brief",
                {"brief_text": "## Intent\nGoal", "metadata": {}},
                3600,
            )

            with patch("spawn_context.workflow_state_path", return_value=None):
                result = build_spawn_context_response("agent-tdd", self.cwd)

        self.assertIn("agent-isdd", result)
        self.assertIn("## Intent\nGoal", result)
        self.assertIn("standalone", result)

    def test_never_calls_handle_standalone_spawn(self):
        """Read-only contract: get_spawn_context must never trigger a fresh
        build/write (that's handle_standalone_spawn's job, invoked only by
        before_continue.py)."""
        with patch(
            "orchestrator.hooks.before_continue.handle_standalone_spawn"
        ) as mock_handle, \
             patch("spawn_context.workflow_state_path", return_value=None), \
             patch.dict(os.environ, {"CLAUDE_PLUGIN_DATA": self.tmpdir.name}):
            build_spawn_context_response("agent-tdd", self.cwd)
        mock_handle.assert_not_called()


if __name__ == "__main__":
    unittest.main()
