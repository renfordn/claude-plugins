"""Tests for hooks/research_cache.py.

research_cache.py is a pure library module (no stdin/CLI interface), tested here via direct
import + a real temp git repo, mirroring test_diff_fingerprint.py's pattern.
"""
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hooks"))
import research_cache  # noqa: E402


class FindStaleSummariesTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = self._tmp.name
        subprocess.run(["git", "init", "-q"], cwd=self.repo, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=self.repo, check=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=self.repo, check=True)

    def tearDown(self):
        self._tmp.cleanup()

    def _write(self, rel_path, content):
        full = os.path.join(self.repo, rel_path)
        os.makedirs(os.path.dirname(full), exist_ok=True) if os.path.dirname(full) else None
        with open(full, "w") as fh:
            fh.write(content)

    def _hash_of(self, rel_path):
        result = subprocess.run(
            ["git", "hash-object", rel_path], cwd=self.repo, capture_output=True, check=True
        )
        return result.stdout.decode("utf-8").strip()

    def test_empty_list_returns_empty_list_no_error(self):
        self.assertEqual(research_cache.find_stale_summaries([], self.repo), [])

    def test_matching_hash_is_not_stale_mismatched_hash_is(self):
        self._write("fresh.py", "fresh content\n")
        self._write("stale.py", "current content\n")

        fresh_summary = {"path": "fresh.py", "git_hash": self._hash_of("fresh.py")}
        stale_summary = {"path": "stale.py", "git_hash": "0000000000000000000000000000000000000"}

        result = research_cache.find_stale_summaries([fresh_summary, stale_summary], self.repo)

        self.assertEqual(result, [stale_summary])

    def test_deleted_file_is_stale(self):
        missing_summary = {"path": "does-not-exist.py", "git_hash": "deadbeef"}
        result = research_cache.find_stale_summaries([missing_summary], self.repo)
        self.assertEqual(result, [missing_summary])

    def test_does_not_mutate_input_list(self):
        self._write("fresh.py", "fresh content\n")
        fresh_summary = {"path": "fresh.py", "git_hash": self._hash_of("fresh.py")}
        original = [fresh_summary]
        research_cache.find_stale_summaries(original, self.repo)
        self.assertEqual(original, [fresh_summary])


if __name__ == "__main__":
    unittest.main()
