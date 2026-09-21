"""Tests for the standalone (no agent-isdd SDD workflow active) spawn path.

Pins Slice 5 (Plugin-Orchestrator -> Plugin-Harness Rework):
handle_standalone_spawn(agent_type, cwd) builds a Tier-1-equivalent context
(capability map + a standalone nelly-brief lookup backed by
HarnessContextCache) without ever requiring or mutating workflow-state.json.
See design.md's "Standalone Tier 1 Split" and "Data Contracts And Interfaces".
"""
import os
import tempfile
import unittest
from unittest.mock import patch

from orchestrator.hooks.before_continue import handle_standalone_spawn


class TestHandleStandaloneSpawn(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.project_dir = os.path.join(self.tmpdir.name, "some-project")
        os.makedirs(self.project_dir, exist_ok=True)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_returns_standalone_shaped_context_dict(self):
        result = handle_standalone_spawn("agent-tdd", self.project_dir)
        self.assertIsInstance(result, dict)
        self.assertEqual(result.get("source"), "standalone")
        self.assertIn("capability_map", result)
        self.assertIn("nelly_brief", result)

    def test_creates_no_workflow_state_file(self):
        handle_standalone_spawn("agent-tdd", self.project_dir)
        # A zero-prior-SDD-activity project directory must gain no sdd-memory
        # / workflow-state.json artifacts as a side effect of this call.
        for root, dirs, files in os.walk(self.project_dir):
            self.assertNotIn(
                "workflow-state.json", files,
                f"handle_standalone_spawn must never create workflow-state.json (found in {root})",
            )

    def test_capability_map_is_populated_from_filesystem_not_workflow_state(self):
        with patch(
            "orchestrator.hooks.before_continue._build_capability_map",
            return_value={"agent-isdd": {"name": "agent-isdd"}},
        ) as mock_build:
            result = handle_standalone_spawn("agent-tdd", self.project_dir)
        mock_build.assert_called_once()
        self.assertEqual(result["capability_map"], {"agent-isdd": {"name": "agent-isdd"}})

    def test_nelly_brief_lookup_uses_harness_context_cache_backend(self):
        with patch(
            "orchestrator.hooks.before_continue.NellyBriefManager.fetch_brief",
            return_value=("## Intent\nGoal", {"task_id": "t1"}),
        ) as mock_fetch:
            result = handle_standalone_spawn("agent-tdd", self.project_dir)

        self.assertEqual(result["nelly_brief"], "## Intent\nGoal")
        _, kwargs = mock_fetch.call_args
        self.assertIsNone(kwargs.get("workflow_state"))
        self.assertIsNotNone(kwargs.get("cache_backend"))

    def test_nelly_brief_degrades_to_none_on_fetch_failure(self):
        with patch(
            "orchestrator.hooks.before_continue.NellyBriefManager.fetch_brief",
            side_effect=RuntimeError("agent-nelly unavailable"),
        ):
            result = handle_standalone_spawn("agent-tdd", self.project_dir)
        self.assertIsNone(result["nelly_brief"])

    def test_emits_standalone_context_requested_telemetry_event(self):
        with patch(
            "orchestrator.hooks.before_continue.get_hook_telemetry_logger"
        ) as mock_get_logger:
            mock_logger = mock_get_logger.return_value
            handle_standalone_spawn("agent-tdd", self.project_dir)

        mock_logger.emit.assert_called_once()
        args, kwargs = mock_logger.emit.call_args
        self.assertEqual(args[0], "standalone_context_requested")


if __name__ == "__main__":
    unittest.main()
