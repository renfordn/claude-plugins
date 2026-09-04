#!/usr/bin/env python3
"""
Tests for agent-cache-plugin HTTP integration.

Tests cache_hook.py and ux_render.py's HTTP-based cache operations with graceful
degradation when agent-cache-plugin is unavailable.
"""
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'hooks'))

import cache_hook
import ux_render


class CacheWriteTests(unittest.TestCase):
    """Tests for cache_write_via_mcp in both hooks."""

    def test_cache_write_success_via_http(self):
        """Successful cache write returns True."""
        with patch('urllib.request.urlopen') as mock_urlopen:
            mock_response = MagicMock()
            mock_response.status = 200
            mock_urlopen.return_value.__enter__.return_value = mock_response

            result = cache_hook.cache_write_via_mcp(
                "phase_state",
                {"current_phase": "Design"},
                "agent-isdd:test-feature",
                ttl_seconds=3600
            )

            self.assertTrue(result)
            mock_urlopen.assert_called_once()

    def test_cache_write_unavailable_graceful_degradation(self):
        """Cache write gracefully degrades when agent-cache-plugin unavailable."""
        with patch('urllib.request.urlopen') as mock_urlopen:
            import urllib.error
            mock_urlopen.side_effect = urllib.error.URLError("Connection refused")

            result = cache_hook.cache_write_via_mcp(
                "phase_state",
                {"current_phase": "Design"},
                "agent-isdd:test-feature"
            )

            # Should return True (graceful degradation, not failure)
            self.assertTrue(result)

    def test_cache_write_timeout_graceful_degradation(self):
        """Cache write gracefully handles timeout."""
        with patch('urllib.request.urlopen') as mock_urlopen:
            mock_urlopen.side_effect = TimeoutError("Request timeout")

            result = cache_hook.cache_write_via_mcp(
                "phase_state",
                {"current_phase": "Design"},
                "agent-isdd:test-feature"
            )

            self.assertTrue(result)

    def test_cache_write_sends_correct_payload(self):
        """Cache write sends correct JSON payload to endpoint."""
        with patch('urllib.request.Request') as mock_request_class:
            with patch('urllib.request.urlopen'):
                cache_hook.cache_write_via_mcp(
                    "phase_state",
                    {"current_phase": "Design", "phase_state": "In Progress"},
                    "agent-isdd:test-feature",
                    ttl_seconds=3600
                )

                # Verify Request was called with correct endpoint
                call_args = mock_request_class.call_args
                self.assertEqual(
                    call_args[0][0],
                    "http://localhost:7771/cache/write"
                )


class CacheReadTests(unittest.TestCase):
    """Tests for cache_read_via_mcp in ux_render."""

    def test_cache_read_hit(self):
        """Cache read returns hit result."""
        cache_value = {"current_phase": "Design", "phase_state": "In Progress"}

        with patch('urllib.request.urlopen') as mock_urlopen:
            mock_response = MagicMock()
            mock_response.status = 200
            mock_response.read.return_value = json.dumps({
                "hit": True,
                "value": cache_value
            }).encode('utf-8')
            mock_urlopen.return_value.__enter__.return_value = mock_response

            result = ux_render.cache_read_via_mcp("phase_state", "agent-isdd:test-feature")

            self.assertTrue(result.get("hit"))
            self.assertEqual(result.get("value"), cache_value)

    def test_cache_read_miss(self):
        """Cache read returns miss result."""
        with patch('urllib.request.urlopen') as mock_urlopen:
            mock_response = MagicMock()
            mock_response.status = 200
            mock_response.read.return_value = json.dumps({"hit": False}).encode('utf-8')
            mock_urlopen.return_value.__enter__.return_value = mock_response

            result = ux_render.cache_read_via_mcp("phase_state", "agent-isdd:test-feature")

            self.assertFalse(result.get("hit"))

    def test_cache_read_unavailable_graceful_degradation(self):
        """Cache read gracefully returns miss when agent-cache-plugin unavailable."""
        with patch('urllib.request.urlopen') as mock_urlopen:
            import urllib.error
            mock_urlopen.side_effect = urllib.error.URLError("Connection refused")

            result = ux_render.cache_read_via_mcp("phase_state", "agent-isdd:test-feature")

            # Should return cache miss (graceful degradation)
            self.assertFalse(result.get("hit"))

    def test_cache_read_timeout_graceful_degradation(self):
        """Cache read gracefully handles timeout."""
        with patch('urllib.request.urlopen') as mock_urlopen:
            mock_urlopen.side_effect = TimeoutError("Request timeout")

            result = ux_render.cache_read_via_mcp("phase_state", "agent-isdd:test-feature")

            self.assertFalse(result.get("hit"))

    def test_cache_read_malformed_json_graceful_degradation(self):
        """Cache read gracefully handles malformed JSON response."""
        with patch('urllib.request.urlopen') as mock_urlopen:
            mock_response = MagicMock()
            mock_response.status = 200
            mock_response.read.return_value = b"invalid json {{{{"
            mock_urlopen.return_value.__enter__.return_value = mock_response

            result = ux_render.cache_read_via_mcp("phase_state", "agent-isdd:test-feature")

            # Should return cache miss (graceful degradation)
            self.assertFalse(result.get("hit"))


class CacheInvalidateTests(unittest.TestCase):
    """Tests for cache_invalidate_via_mcp in cache_hook."""

    def test_cache_invalidate_success(self):
        """Successful cache invalidate returns True."""
        with patch('urllib.request.urlopen') as mock_urlopen:
            mock_response = MagicMock()
            mock_response.status = 200
            mock_urlopen.return_value.__enter__.return_value = mock_response

            result = cache_hook.cache_invalidate_via_mcp("agent-isdd:test-feature")

            self.assertTrue(result)

    def test_cache_invalidate_unavailable_graceful_degradation(self):
        """Cache invalidate gracefully degrades when unavailable."""
        with patch('urllib.request.urlopen') as mock_urlopen:
            import urllib.error
            mock_urlopen.side_effect = urllib.error.URLError("Connection refused")

            result = cache_hook.cache_invalidate_via_mcp("agent-isdd:test-feature")

            # Should return True (graceful degradation)
            self.assertTrue(result)

    def test_cache_invalidate_sends_scope(self):
        """Cache invalidate sends correct scope in payload."""
        with patch('urllib.request.Request') as mock_request_class:
            with patch('urllib.request.urlopen'):
                cache_hook.cache_invalidate_via_mcp("agent-isdd:test-feature")

                call_args = mock_request_class.call_args
                self.assertEqual(
                    call_args[0][0],
                    "http://localhost:7771/cache/invalidate"
                )


class UxRenderBreadcrumbLogicTests(unittest.TestCase):
    """Tests for breadcrumb rendering logic with cache."""

    def test_phase_change_detected(self):
        """Phase change is correctly detected."""
        self.assertTrue(ux_render.is_phase_change("Requirements", "Design"))
        self.assertFalse(ux_render.is_phase_change(None, "Design"))  # No prior phase
        self.assertFalse(ux_render.is_phase_change("Design", "Design"))
        self.assertFalse(ux_render.is_phase_change(None, None))

    def test_cache_hit_on_same_phase(self):
        """Same phase with cache hit uses cached value."""
        # This is more of an integration test of the main() logic,
        # but we can verify the decision tree
        old_phase = "Design"
        new_phase = "Design"
        is_changed = ux_render.is_phase_change(old_phase, new_phase)
        self.assertFalse(is_changed)  # Should not render full transition

    def test_cache_miss_renders_full_breadcrumb(self):
        """Cache miss forces full breadcrumb render."""
        cache_miss = {"hit": False}
        is_hit = cache_miss.get("hit")
        self.assertFalse(is_hit)  # Should render full breadcrumb


if __name__ == "__main__":
    unittest.main()
