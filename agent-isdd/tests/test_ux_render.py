#!/usr/bin/env python3
"""
Tests for hooks/ux_render.py (SubagentStop breadcrumb refresh).

Also pins that the hook makes no network calls: it used to POST to a non-existent
agent-cache-plugin HTTP server on localhost:7771 and "gracefully degrade" forever.
"""
import io
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'hooks'))

import ux_render


def _write_state(feature_dir, **fields):
    path = os.path.join(feature_dir, "workflow-state.json")
    with open(path, "w") as f:
        json.dump(fields, f)
    return path


class NoNetworkTests(unittest.TestCase):

    def test_no_http_client_in_source(self):
        with open(ux_render.__file__) as f:
            src = f.read()
        for needle in ("urllib", "urlopen", "Request("):
            self.assertNotIn(needle, src)
        for name in ("cache_read_via_mcp", "cache_write_via_mcp"):
            self.assertFalse(hasattr(ux_render, name))

    def test_never_opens_a_socket(self):
        with tempfile.TemporaryDirectory() as d:
            state_path = _write_state(d, current_phase="Design")
            with patch("socket.socket", side_effect=AssertionError("network call attempted")):
                ux_render.main({"state_path": state_path})


class BreadcrumbTests(unittest.TestCase):

    def test_no_active_feature_returns_none(self):
        with patch.object(ux_render, "active_state_file", return_value=None):
            self.assertIsNone(ux_render.main({"cwd": "/nonexistent"}))

    def test_missing_state_file_returns_none(self):
        self.assertIsNone(ux_render.main({"state_path": "/nonexistent/workflow-state.json"}))

    def test_no_current_phase_returns_none(self):
        with tempfile.TemporaryDirectory() as d:
            state_path = _write_state(d, workflow_status="active")
            self.assertIsNone(ux_render.main({"state_path": state_path}))

    def test_breadcrumb_message_from_current_phase(self):
        with tempfile.TemporaryDirectory() as d:
            state_path = _write_state(d, current_phase="Design", phase_state="In Progress")
            self.assertEqual(ux_render.main({"state_path": state_path}),
                             "UX: breadcrumb update (Design)")

    def test_resolves_active_feature_from_cwd(self):
        """The real SubagentStop payload carries cwd, not state_path."""
        with tempfile.TemporaryDirectory() as d:
            _write_state(d, current_phase="Tasks")
            md_path = os.path.join(d, "workflow-state.md")
            open(md_path, "w").close()
            with patch.object(ux_render, "active_state_file", return_value=md_path) as asf:
                self.assertEqual(ux_render.main({"cwd": "/some/project"}),
                                 "UX: breadcrumb update (Tasks)")
                asf.assert_called_once_with("/some/project")

    def test_never_emits_phase_transition(self):
        """Phase transitions are the skill's job, even when the phase changes between calls."""
        with tempfile.TemporaryDirectory() as d:
            state_path = _write_state(d, current_phase="Requirements")
            ux_render.main({"state_path": state_path})
            _write_state(d, current_phase="Design")
            msg = ux_render.main({"state_path": state_path})
            self.assertEqual(msg, "UX: breadcrumb update (Design)")

    def test_standalone_reads_stdin(self):
        with tempfile.TemporaryDirectory() as d:
            state_path = _write_state(d, current_phase="Design")
            with patch("sys.stdin", io.StringIO(json.dumps({"state_path": state_path}))):
                self.assertEqual(ux_render.main(), "UX: breadcrumb update (Design)")

    def test_feature_slug_extraction(self):
        self.assertEqual(ux_render.get_feature_slug("/x/sdd-memory/my-feat/workflow-state.json"),
                         "my-feat")
        self.assertEqual(ux_render.get_feature_slug("/x/tdd-memory/other/workflow-state.json"),
                         "other")
        self.assertEqual(ux_render.get_feature_slug("/plain/dir/workflow-state.json"), "dir")


class DispatcherTests(unittest.TestCase):

    def test_cache_hook_removed_from_dispatch(self):
        import subagent_dispatch
        names = [m.__name__ for m in subagent_dispatch.MODULES]
        self.assertEqual(names, ["subagent_report", "high_risk_reviewer", "ux_render"])
        self.assertFalse(os.path.exists(os.path.join(os.path.dirname(ux_render.__file__),
                                                     "cache_hook.py")))


if __name__ == "__main__":
    unittest.main()
