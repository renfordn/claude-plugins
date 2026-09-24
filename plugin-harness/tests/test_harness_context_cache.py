"""Tests for orchestrator/harness_context_cache.py's HarnessContextCache.

Pins Slice 3 (Plugin-Orchestrator -> Plugin-Harness Rework): a new,
project-slug-keyed JSON cache file, independent of workflow-state.json, that
backs the standalone Tier-1 context path (Slice 5) and NellyBriefManager's new
cache_backend param (Slice 4). See design.md's "Data Contracts And Interfaces"
for the get/set contract and invariants (atomic writes, never raises on read,
one file per project slug).
"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "orchestrator")
)

from harness_context_cache import HarnessContextCache  # noqa: E402


class TestHarnessContextCacheRoundTrip(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.cache = HarnessContextCache("my-project-slug", base_dir=self.tmpdir.name)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_get_missing_key_returns_none(self):
        self.assertIsNone(self.cache.get("nelly_brief"))

    def test_set_then_get_round_trips(self):
        self.cache.set("nelly_brief", {"text": "hello"}, ttl_seconds=3600)
        self.assertEqual(self.cache.get("nelly_brief"), {"text": "hello"})

    def test_set_writes_to_project_slug_scoped_file(self):
        self.cache.set("capability_map", {"plugins": []}, ttl_seconds=3600)
        expected_path = os.path.join(self.tmpdir.name, "my-project-slug", "context-cache.json")
        self.assertTrue(os.path.exists(expected_path))

    def test_two_project_slugs_do_not_share_a_file(self):
        other = HarnessContextCache("other-project-slug", base_dir=self.tmpdir.name)
        self.cache.set("nelly_brief", {"text": "for-my-project"}, ttl_seconds=3600)
        self.assertIsNone(other.get("nelly_brief"))

    def test_multiple_keys_coexist_in_one_file(self):
        self.cache.set("nelly_brief", {"text": "brief"}, ttl_seconds=3600)
        self.cache.set("capability_map", {"plugins": ["agent-isdd"]}, ttl_seconds=3600)
        self.assertEqual(self.cache.get("nelly_brief"), {"text": "brief"})
        self.assertEqual(self.cache.get("capability_map"), {"plugins": ["agent-isdd"]})


class TestHarnessContextCacheTTLExpiry(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.cache = HarnessContextCache("ttl-project", base_dir=self.tmpdir.name)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_get_returns_none_after_ttl_expires(self):
        self.cache.set("nelly_brief", {"text": "stale"}, ttl_seconds=-1)
        self.assertIsNone(self.cache.get("nelly_brief"))

    def test_get_returns_value_before_ttl_expires(self):
        self.cache.set("nelly_brief", {"text": "fresh"}, ttl_seconds=3600)
        self.assertEqual(self.cache.get("nelly_brief"), {"text": "fresh"})


class TestHarnessContextCacheNeverRaises(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_get_on_missing_file_returns_none_not_raise(self):
        cache = HarnessContextCache("never-written-project", base_dir=self.tmpdir.name)
        self.assertIsNone(cache.get("anything"))

    def test_get_on_malformed_json_file_returns_none_not_raise(self):
        cache = HarnessContextCache("malformed-project", base_dir=self.tmpdir.name)
        project_dir = os.path.join(self.tmpdir.name, "malformed-project")
        os.makedirs(project_dir, exist_ok=True)
        with open(os.path.join(project_dir, "context-cache.json"), "w") as f:
            f.write("{not valid json")
        self.assertIsNone(cache.get("nelly_brief"))


class TestHarnessContextCacheAtomicWrite(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.cache = HarnessContextCache("atomic-project", base_dir=self.tmpdir.name)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_set_leaves_no_tmp_file_behind(self):
        self.cache.set("nelly_brief", {"text": "hi"}, ttl_seconds=3600)
        project_dir = os.path.join(self.tmpdir.name, "atomic-project")
        leftover = [f for f in os.listdir(project_dir) if f.endswith(".tmp")]
        self.assertEqual(leftover, [])

    def test_set_survives_simulated_crash_leaving_prior_value_intact(self):
        """A crash mid-write (temp file created but os.replace never called)
        must not corrupt or lose the previously-committed value -- the
        write-temp-then-rename pattern guarantees the target file is only
        ever the last fully-written version."""
        self.cache.set("nelly_brief", {"text": "committed"}, ttl_seconds=3600)

        project_dir = os.path.join(self.tmpdir.name, "atomic-project")
        crashed_tmp = os.path.join(project_dir, ".context-cache-crash.tmp")
        with open(crashed_tmp, "w") as f:
            f.write('{"incomplete": ')  # simulate a crash mid-write; never replaced

        self.assertEqual(self.cache.get("nelly_brief"), {"text": "committed"})
        target_path = os.path.join(project_dir, "context-cache.json")
        with open(target_path) as f:
            on_disk = json.load(f)
        self.assertIn("nelly_brief", on_disk)



class TestHarnessContextCacheTempFiles(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.cache = HarnessContextCache("my-project-slug", base_dir=self.tmpdir.name)

    def _tmp_files(self):
        return [f for f in os.listdir(self.cache.project_dir) if f.endswith(".tmp")]

    def test_failed_write_removes_temp_file(self):
        import unittest.mock
        with unittest.mock.patch.object(
            sys.modules[HarnessContextCache.__module__].json, "dump", side_effect=OSError("disk full")
        ):
            with self.assertRaises(OSError):
                self.cache.set("k", "v", ttl_seconds=60)
        self.assertEqual(self._tmp_files(), [])

    def test_successful_write_sweeps_only_stale_temp_files(self):
        import time
        os.makedirs(self.cache.project_dir, exist_ok=True)
        stale = os.path.join(self.cache.project_dir, f".{HarnessContextCache.FILENAME}-stale.tmp")
        fresh = os.path.join(self.cache.project_dir, f".{HarnessContextCache.FILENAME}-fresh.tmp")
        for p in (stale, fresh):
            with open(p, "w") as f:
                f.write("{}")
        old = time.time() - HarnessContextCache.STALE_TMP_SECONDS - 60
        os.utime(stale, (old, old))

        self.cache.set("k", "v", ttl_seconds=60)

        self.assertFalse(os.path.exists(stale))
        self.assertTrue(os.path.exists(fresh))
        self.assertEqual(self.cache.get("k"), "v")


if __name__ == "__main__":
    unittest.main()
