"""Tests for hooks/diff_fingerprint.py.

diff_fingerprint.py is a pure library module (no stdin/CLI interface), imported directly by
hooks/commit_audit_gate.py -- tested here via direct import + a real temp git repo, not via
run_hook(). Ported from the live verification run during the Doc Consistency Auditor feature.
"""
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hooks"))
import diff_fingerprint  # noqa: E402


class DiffFingerprintTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = self._tmp.name
        subprocess.run(["git", "init", "-q"], cwd=self.repo, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=self.repo, check=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=self.repo, check=True)
        os.makedirs(os.path.join(self.repo, "skills", "foo"))

    def tearDown(self):
        self._tmp.cleanup()

    def _write_and_stage(self, rel_path, content):
        full = os.path.join(self.repo, rel_path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w") as fh:
            fh.write(content)
        subprocess.run(["git", "add", rel_path], cwd=self.repo, check=True)

    def test_nothing_staged_returns_none(self):
        self.assertIsNone(diff_fingerprint.compute(self.repo))

    def test_staged_content_produces_a_hash(self):
        self._write_and_stage("skills/foo/SKILL.md", "hello\n")
        fp = diff_fingerprint.compute(self.repo)
        self.assertIsNotNone(fp)
        self.assertEqual(len(fp), 64)  # sha256 hex digest

    def test_content_change_produces_a_different_hash(self):
        self._write_and_stage("skills/foo/SKILL.md", "hello\n")
        first = diff_fingerprint.compute(self.repo)
        self._write_and_stage("skills/foo/SKILL.md", "hello world\n")
        second = diff_fingerprint.compute(self.repo)
        self.assertNotEqual(first, second)

    def test_unrelated_staged_file_does_not_affect_fingerprint(self):
        self._write_and_stage("skills/foo/SKILL.md", "hello\n")
        before = diff_fingerprint.compute(self.repo)
        self._write_and_stage("README.md", "irrelevant\n")
        after = diff_fingerprint.compute(self.repo)
        self.assertEqual(before, after)

    def test_unstaging_returns_none(self):
        self._write_and_stage("skills/foo/SKILL.md", "hello\n")
        subprocess.run(["git", "reset"], cwd=self.repo, check=True)
        self.assertIsNone(diff_fingerprint.compute(self.repo))

    def test_non_git_directory_returns_none(self):
        with tempfile.TemporaryDirectory() as not_git:
            self.assertIsNone(diff_fingerprint.compute(not_git))


if __name__ == "__main__":
    unittest.main()
