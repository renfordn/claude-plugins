#!/usr/bin/env python3
"""
Tests for the (former) agent-cache-plugin integration in cache_hook.py and ux_render.py.

agent-cache-plugin exposes no transport a Python hook can reach (no HTTP server, no CLI
store/retrieve, JS-only in-process API), so both hooks must be free of network calls:
cache_hook.py is a documented no-op, ux_render.py renders the breadcrumb straight from
workflow-state.json. These tests pin that -- a regression that reintroduces urllib calls
against localhost:7771 would silently "gracefully degrade" forever, as the original did.
"""
import io
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'hooks'))

import cache_hook
import ux_render


def _write_state(feature_dir, **fields):
    path = os.path.join(feature_dir, "workflow-state.json")
    with open(path, "w") as f:
        json.dump(fields, f)
    return path


class NoNetworkTests(unittest.TestCase):
    """Neither hook may attempt a network call -- there is no server to talk to."""

    def test_no_http_endpoints_referenced(self):
        for module in (cache_hook, ux_render):
            with open(module.__file__) as f:
                src = f.read()
            self.assertNotIn("urllib", src, f"{module.__name__} must not use urllib")
            self.assertNotIn("urlopen", src, f"{module.__name__} must not open URLs")
            self.assertNotIn("Request(", src, f"{module.__name__} must not build HTTP requests")

    def test_dead_mcp_helpers_removed(self):
        for name in ("cache_write_via_mcp", "cache_invalidate_via_mcp", "cache_read_via_mcp"):
            self.assertFalse(hasattr(cache_hook, name), f"cache_hook.{name} should be gone")
            self.assertFalse(hasattr(ux_render, name), f"ux_render.{name} should be gone")

    def test_hooks_never_open_a_socket(self):
        with tempfile.TemporaryDirectory() as d:
            state_path = _write_state(d, current_phase="Design", rollback_pending=True)
            with patch("socket.socket", side_effect=AssertionError("network call attempted")):
                cache_hook.main({"cwd": d})
                ux_render.main({"state_path": state_path})


class CacheHookNoOpTests(unittest.TestCase):
    """cache_hook.main() is a documented no-op with the dispatcher-compatible signature."""

    def test_returns_none_with_payload(self):
        self.assertIsNone(cache_hook.main({"cwd": "/nonexistent"}))

    def test_returns_none_on_rollback_and_phase_states(self):
        with tempfile.TemporaryDirectory() as d:
            _write_state(d, current_phase="Design")
            self.assertIsNone(cache_hook.main({"cwd": d}))
            _write_state(d, current_phase="Design", rollback_pending=True)
            self.assertIsNone(cache_hook.main({"cwd": d}))

    def test_standalone_reads_stdin_and_returns_none(self):
        with patch("sys.stdin", io.StringIO(json.dumps({"cwd": "/x"}))):
            self.assertIsNone(cache_hook.main())
        with patch("sys.stdin", io.StringIO("not json")):
            self.assertIsNone(cache_hook.main())

    def test_docstring_explains_the_gap(self):
        doc = cache_hook.__doc__
        self.assertIn("localhost:7771", doc)
        self.assertIn("STRUCTURE.md", doc)
        self.assertIn("workflow-state.json", doc)


class UxRenderBreadcrumbTests(unittest.TestCase):
    """ux_render renders the breadcrumb from workflow-state.json alone."""

    def test_no_state_path_returns_none(self):
        self.assertIsNone(ux_render.main({}))

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

    def test_repeat_calls_stay_breadcrumb_only(self):
        """Phase transitions are the skill's job; the hook never emits a phase_transition
        delegation, even when the phase changes between calls."""
        with tempfile.TemporaryDirectory() as d:
            state_path = _write_state(d, current_phase="Requirements")
            ux_render.main({"state_path": state_path})
            _write_state(d, current_phase="Design")
            msg = ux_render.main({"state_path": state_path})
            self.assertEqual(msg, "UX: breadcrumb update (Design)")
            self.assertNotIn("phase_transition", msg)

    def test_feature_slug_extraction(self):
        self.assertEqual(ux_render.get_feature_slug("/x/sdd-memory/my-feat/workflow-state.json"),
                         "my-feat")
        self.assertEqual(ux_render.get_feature_slug("/x/tdd-memory/other/workflow-state.json"),
                         "other")
        self.assertEqual(ux_render.get_feature_slug("/plain/dir/workflow-state.json"), "dir")


if __name__ == "__main__":
    unittest.main()
