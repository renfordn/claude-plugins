"""Tests for hooks/commit_audit_gate.py.

Ported from the live verification run during the Doc Consistency Auditor feature (2026-07-31),
run against a temp fixture repo (never the real one).
"""
import os
import sys
import unittest

import hook_test_utils as h

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hooks"))
import diff_fingerprint  # noqa: E402


class CommitAuditGateTests(unittest.TestCase):
    def _stage_a_change(self, repo):
        with open(os.path.join(repo, "skills", "x.md"), "w") as fh:
            fh.write("content\n")
        import subprocess
        subprocess.run(["git", "add", "skills/x.md"], cwd=repo, check=True)

    def test_no_state_file_is_denied(self):
        with h.temp_git_repo(with_plugin_dirs=True) as repo, h.temp_home() as home:
            self._stage_a_change(repo)
            decision, rc = h.run_hook(
                "commit_audit_gate.py",
                {"tool_input": {"command": 'git commit -m "test"'}, "cwd": repo},
                env_extra={"HOME": home},
            )
            self.assertEqual(rc, 0)
            self.assertIsNotNone(decision)
            self.assertEqual(decision["permissionDecision"], "deny")

    def test_non_commit_command_is_noop(self):
        with h.temp_git_repo(with_plugin_dirs=True) as repo, h.temp_home() as home:
            decision, rc = h.run_hook(
                "commit_audit_gate.py",
                {"tool_input": {"command": "ls -la"}, "cwd": repo},
                env_extra={"HOME": home},
            )
            self.assertEqual(rc, 0)
            self.assertIsNone(decision)

    def test_unrelated_repo_is_noop(self):
        with h.temp_git_repo(with_plugin_dirs=False) as repo, h.temp_home() as home:
            decision, rc = h.run_hook(
                "commit_audit_gate.py",
                {"tool_input": {"command": 'git commit -m "test"'}, "cwd": repo},
                env_extra={"HOME": home},
            )
            self.assertEqual(rc, 0)
            self.assertIsNone(decision)

    def test_nothing_staged_is_allowed(self):
        with h.temp_git_repo(with_plugin_dirs=True) as repo, h.temp_home() as home:
            decision, rc = h.run_hook(
                "commit_audit_gate.py",
                {"tool_input": {"command": 'git commit -m "test"'}, "cwd": repo},
                env_extra={"HOME": home},
            )
            self.assertEqual(rc, 0)
            self.assertIsNotNone(decision)
            self.assertEqual(decision["permissionDecision"], "allow")

    def test_matching_fingerprint_is_allowed(self):
        with h.temp_git_repo(with_plugin_dirs=True) as repo, h.temp_home() as home:
            self._stage_a_change(repo)
            fp = diff_fingerprint.compute(repo)

            import re
            slug = re.sub(r"[^A-Za-z0-9]+", "-", os.path.abspath(repo)).strip("-").lower()
            mem_dir = os.path.join(home, ".claude", "sdd-memory", slug)
            os.makedirs(mem_dir)
            with open(os.path.join(mem_dir, "DOC-AUDIT-STATE.md"), "w") as fh:
                fh.write(f"- Status: `passed`\n- Diff Fingerprint: `{fp}`\n")

            decision, rc = h.run_hook(
                "commit_audit_gate.py",
                {"tool_input": {"command": 'git commit -m "test"'}, "cwd": repo},
                env_extra={"HOME": home},
            )
            self.assertEqual(rc, 0)
            self.assertIsNotNone(decision)
            self.assertEqual(decision["permissionDecision"], "allow")

    def test_stale_fingerprint_is_denied(self):
        with h.temp_git_repo(with_plugin_dirs=True) as repo, h.temp_home() as home:
            self._stage_a_change(repo)
            fp = diff_fingerprint.compute(repo)

            import re
            slug = re.sub(r"[^A-Za-z0-9]+", "-", os.path.abspath(repo)).strip("-").lower()
            mem_dir = os.path.join(home, ".claude", "sdd-memory", slug)
            os.makedirs(mem_dir)
            with open(os.path.join(mem_dir, "DOC-AUDIT-STATE.md"), "w") as fh:
                fh.write(f"- Status: `passed`\n- Diff Fingerprint: `{fp}`\n")

            # drift the staged content after the audit "ran"
            with open(os.path.join(repo, "skills", "x.md"), "w") as fh:
                fh.write("drifted content\n")
            import subprocess
            subprocess.run(["git", "add", "skills/x.md"], cwd=repo, check=True)

            decision, rc = h.run_hook(
                "commit_audit_gate.py",
                {"tool_input": {"command": 'git commit -m "test"'}, "cwd": repo},
                env_extra={"HOME": home},
            )
            self.assertEqual(rc, 0)
            self.assertIsNotNone(decision)
            self.assertEqual(decision["permissionDecision"], "deny")

    def test_sdd_gate_off_bypasses(self):
        with h.temp_git_repo(with_plugin_dirs=True) as repo, h.temp_home() as home:
            self._stage_a_change(repo)
            decision, rc = h.run_hook(
                "commit_audit_gate.py",
                {"tool_input": {"command": 'git commit -m "test"'}, "cwd": repo},
                env_extra={"HOME": home, "SDD_GATE": "off"},
            )
            self.assertEqual(rc, 0)
            self.assertIsNotNone(decision)
            self.assertEqual(decision["permissionDecision"], "allow")


if __name__ == "__main__":
    unittest.main()
