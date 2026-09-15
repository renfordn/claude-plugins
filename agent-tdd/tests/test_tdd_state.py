"""Tests for hooks/tdd_state.py."""
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "hooks"))
import tdd_state


class ProjectSlugTests(unittest.TestCase):
    def test_slug_replaces_non_alphanumeric_with_hyphens(self):
        slug = tdd_state.project_slug("/home/user/my project")
        self.assertNotIn(" ", slug)
        self.assertNotIn("/", slug)

    def test_slug_is_lowercase(self):
        slug = tdd_state.project_slug("/Users/Jay/Repo")
        self.assertEqual(slug, slug.lower())

    def test_slug_strips_leading_trailing_hyphens(self):
        slug = tdd_state.project_slug("/foo/bar")
        self.assertFalse(slug.startswith("-"))
        self.assertFalse(slug.endswith("-"))

    def test_slug_is_deterministic(self):
        self.assertEqual(
            tdd_state.project_slug("/some/path"),
            tdd_state.project_slug("/some/path"),
        )

    def test_slug_differs_for_different_paths(self):
        self.assertNotEqual(
            tdd_state.project_slug("/path/a"),
            tdd_state.project_slug("/path/b"),
        )


class TddMemoryDirTests(unittest.TestCase):
    def test_memory_dir_contains_base_and_slug(self):
        d = tdd_state.tdd_memory_dir("/some/project")
        self.assertIn("agent-tdd-state", d)
        slug = tdd_state.project_slug("/some/project")
        self.assertTrue(d.endswith(slug))


class ReadTddProgressTests(unittest.TestCase):
    def test_missing_file_returns_empty_slices(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = tdd_state.read_tdd_progress(os.path.join(tmp, "nonexistent"))
            self.assertEqual(result, {"slices": []})

    def test_malformed_json_returns_empty_slices(self):
        with tempfile.TemporaryDirectory() as tmp:
            mem = tdd_state.tdd_memory_dir(tmp)
            os.makedirs(mem, exist_ok=True)
            with open(os.path.join(mem, "tdd-progress.json"), "w") as f:
                f.write("not json{{{")
            result = tdd_state.read_tdd_progress(tmp)
            self.assertEqual(result, {"slices": []})

    def test_wrong_schema_returns_empty_slices(self):
        with tempfile.TemporaryDirectory() as tmp:
            mem = tdd_state.tdd_memory_dir(tmp)
            os.makedirs(mem, exist_ok=True)
            with open(os.path.join(mem, "tdd-progress.json"), "w") as f:
                json.dump(["not", "a", "dict"], f)
            result = tdd_state.read_tdd_progress(tmp)
            self.assertEqual(result, {"slices": []})

    def test_valid_file_returns_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = {"slices": [{"id": 1, "description": "test", "status": "green_pending_review"}]}
            tdd_state.write_tdd_progress(tmp, data)
            result = tdd_state.read_tdd_progress(tmp)
            self.assertEqual(result["slices"][0]["id"], 1)


class WriteTddProgressTests(unittest.TestCase):
    def test_creates_parent_dirs(self):
        with tempfile.TemporaryDirectory() as tmp:
            deep = os.path.join(tmp, "a", "b", "c")
            tdd_state.write_tdd_progress(deep, {"slices": []})
            path = os.path.join(tdd_state.tdd_memory_dir(deep), "tdd-progress.json")
            self.assertTrue(os.path.isfile(path))

    def test_written_file_is_valid_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            tdd_state.write_tdd_progress(tmp, {"slices": [{"id": 1}]})
            path = os.path.join(tdd_state.tdd_memory_dir(tmp), "tdd-progress.json")
            with open(path) as f:
                data = json.load(f)
            self.assertEqual(data["slices"][0]["id"], 1)

    def test_file_has_trailing_newline(self):
        with tempfile.TemporaryDirectory() as tmp:
            tdd_state.write_tdd_progress(tmp, {"slices": []})
            path = os.path.join(tdd_state.tdd_memory_dir(tmp), "tdd-progress.json")
            with open(path, "rb") as f:
                content = f.read()
            self.assertTrue(content.endswith(b"\n"))


class WriteLastStopTests(unittest.TestCase):
    def test_writes_timestamp_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            tdd_state.write_last_stop(tmp)
            path = os.path.join(tdd_state.tdd_memory_dir(tmp), "last-stop.json")
            self.assertTrue(os.path.isfile(path))
            with open(path) as f:
                data = json.load(f)
            self.assertIn("timestamp", data)

    def test_oserror_is_silently_ignored(self):
        # Write to a path where the parent cannot be created (root-owned dir)
        # Simulate by monkey-patching makedirs
        original = os.makedirs

        def raise_os_error(*args, **kwargs):
            raise OSError("simulated permission error")

        os.makedirs = raise_os_error
        try:
            tdd_state.write_last_stop("/some/path")  # must not raise
        finally:
            os.makedirs = original


class ClaudePluginDataEnvVarTests(unittest.TestCase):
    """Tests for ${CLAUDE_PLUGIN_DATA} env var support (Task 4.2)."""

    def test_base_respects_claude_plugin_data_env_var(self):
        """Verify BASE uses CLAUDE_PLUGIN_DATA when set."""
        with patch.dict(os.environ, {"CLAUDE_PLUGIN_DATA": "/custom/data"}):
            # Force reload to pick up env var
            import importlib
            importlib.reload(tdd_state)
            self.assertIn("/custom/data", tdd_state.BASE)

    def test_base_uses_fallback_when_env_unset(self):
        """Verify BASE falls back to ~/.claude/plugins/data when CLAUDE_PLUGIN_DATA unset."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CLAUDE_PLUGIN_DATA", None)
            # Force reload to pick up cleared env var
            import importlib
            importlib.reload(tdd_state)
            self.assertIn(".claude/plugins/data", tdd_state.BASE)
            self.assertIn("agent-tdd", tdd_state.BASE)

    def test_tdd_memory_dir_uses_updated_base(self):
        """Verify tdd_memory_dir returns paths under updated BASE."""
        with patch.dict(os.environ, {"CLAUDE_PLUGIN_DATA": "/test/plugin-data"}):
            import importlib
            importlib.reload(tdd_state)
            d = tdd_state.tdd_memory_dir("/some/project")
            self.assertIn("/test/plugin-data", d)
            self.assertIn("agent-tdd-state", d)


if __name__ == "__main__":
    unittest.main()
