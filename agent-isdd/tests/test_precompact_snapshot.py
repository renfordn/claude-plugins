"""Tests for hooks/precompact_snapshot.py.

New test design (no prior ad-hoc coverage this session).
"""
import os
import unittest

import hook_test_utils as h


class PrecompactSnapshotTests(unittest.TestCase):
    def _snapshots_dir(self, home, cwd):
        slug = h.project_slug_for(cwd)
        return os.path.join(home, ".claude", "sdd-memory", slug, "snapshots")

    def test_nothing_to_snapshot_is_silent(self):
        with h.temp_git_repo() as repo, h.temp_home() as home:
            msg, rc = h.run_hook_message(
                "precompact_snapshot.py", {"cwd": repo, "trigger": "manual"},
                env_extra={"HOME": home},
            )
            self.assertEqual(rc, 0)
            self.assertIsNone(msg)
            self.assertFalse(os.path.isdir(self._snapshots_dir(home, repo)))

    def test_seeded_state_produces_a_snapshot_with_expected_content(self):
        with h.temp_git_repo() as repo, h.temp_home() as home:
            feature_dir = h.feature_spec_dir(home, repo)
            h.seed_state_file(
                feature_dir,
                title="My Feature",
                current_phase="Design",
                workflow_status="In Progress",
            )
            os.makedirs(os.path.join(feature_dir, "recap"), exist_ok=True)
            with open(os.path.join(feature_dir, "recap", "recap.md"), "w") as fh:
                fh.write("Recap content here.\n")

            msg, rc = h.run_hook_message(
                "precompact_snapshot.py", {"cwd": repo, "trigger": "manual"},
                env_extra={"HOME": home},
            )
            self.assertEqual(rc, 0)
            self.assertIsNotNone(msg)
            snap_dir = self._snapshots_dir(home, repo)
            self.assertTrue(os.path.isdir(snap_dir))
            snapshots = os.listdir(snap_dir)
            self.assertEqual(len(snapshots), 1)
            with open(os.path.join(snap_dir, snapshots[0])) as fh:
                content = fh.read()
            self.assertIn("My Feature", content)
            self.assertIn("Recap content here.", content)


if __name__ == "__main__":
    unittest.main()
