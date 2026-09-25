"""Tests for hooks/sdd_memory.py.

Ported from live CLI verification across the Agent Responsibility Cleanup and Global
Cross-Project Memory Tier features. sdd_memory.py is the one hook with a CLI (argv-based
main(argv)), so tests use run_sdd_memory_cli(), not run_hook().

Phase 3 of the Decouple Memory feature trimmed this module down to per-feature scaffolding
only (spec_dir()/--spec-path/--path) -- the memory-orchestrator-only surface (--migrate,
global/GLOBAL-MEMORY.md skeleton writing, parse_global_entries/count_global_entries) was
removed, since that agent no longer exists and agent-nelly owns cross-feature memory now.
"""
import importlib.util
import os
import sys
import unittest
from unittest.mock import patch

import hook_test_utils as h


def _load_sdd_memory_module():
    """Import hooks/sdd_memory.py directly, for attribute-presence assertions that a
    subprocess CLI call can't express as cleanly."""
    path = os.path.join(h.HOOKS_DIR, "sdd_memory.py")
    spec = importlib.util.spec_from_file_location("sdd_memory_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SddMemoryTests(unittest.TestCase):
    def test_project_slug_is_deterministic(self):
        with h.temp_home() as home:
            out1, rc1 = h.run_sdd_memory_cli(["--path"], cwd="/tmp", env_extra={"HOME": home})
            out2, rc2 = h.run_sdd_memory_cli(["--path"], cwd="/tmp", env_extra={"HOME": home})
            self.assertEqual(rc1, 0)
            self.assertEqual(out1, out2)

    def test_path_creates_memory_dir_without_memory_md(self):
        """requirements.md: sdd shall never read or write MEMORY.md -- --path must only
        create the directory, never a MEMORY.md skeleton file inside it."""
        with h.temp_home() as home:
            out, rc = h.run_sdd_memory_cli(["--path"], cwd="/tmp", env_extra={"HOME": home})
            self.assertEqual(rc, 0)
            self.assertTrue(os.path.isdir(out))
            self.assertFalse(os.path.isfile(os.path.join(out, "MEMORY.md")))
            # never touches the real home
            self.assertTrue(out.startswith(home))

    def test_spec_path_creates_feature_dir(self):
        with h.temp_home() as home:
            out, rc = h.run_sdd_memory_cli(
                ["--spec-path", "2020-01-01-my-feature"], cwd="/tmp", env_extra={"HOME": home}
            )
            self.assertEqual(rc, 0)
            self.assertTrue(os.path.isdir(out))
            self.assertTrue(out.endswith(os.path.join("spec", "2020-01-01-my-feature")))

    def test_spec_path_rejects_traversal_slug(self):
        with h.temp_home() as home:
            out, rc = h.run_sdd_memory_cli(
                ["--spec-path", "../evil"], cwd="/tmp", env_extra={"HOME": home}
            )
            self.assertNotEqual(rc, 0)


class MemoryOrchestratorSurfaceRemovedTests(unittest.TestCase):
    """Phase 3: assert the memory-orchestrator-only surface is actually gone, not just
    unreachable -- proves dead code was removed rather than left in place."""

    def test_migrate_flag_no_longer_performs_migration(self):
        with h.temp_home() as home:
            src = os.path.join(home, ".scholar-memory.md")
            with open(src, "w") as fh:
                fh.write("some repo-local memory")
            out, rc = h.run_sdd_memory_cli(["--migrate", home], cwd=home, env_extra={"HOME": home})
            self.assertEqual(rc, 0)
            dest = os.path.join(home, ".claude", "sdd-memory", h.project_slug_for(home), "scholar-memory.md")
            self.assertFalse(os.path.isfile(dest))

    def test_global_path_flag_removed(self):
        with h.temp_home() as home:
            out, rc = h.run_sdd_memory_cli(["--global-path"], cwd="/tmp", env_extra={"HOME": home})
            self.assertFalse(out.endswith(os.path.join("sdd-memory", "global")))

    def test_global_count_flag_removed(self):
        with h.temp_home() as home:
            out, rc = h.run_sdd_memory_cli(["--global-count"], cwd="/tmp", env_extra={"HOME": home})
            self.assertNotEqual(out, "0")  # falls through to default (prints memory_dir), not "0"

    def test_migrate_function_removed(self):
        module = _load_sdd_memory_module()
        self.assertFalse(hasattr(module, "_migrate"))

    def test_parse_global_entries_removed(self):
        module = _load_sdd_memory_module()
        self.assertFalse(hasattr(module, "parse_global_entries"))

    def test_count_global_entries_removed(self):
        module = _load_sdd_memory_module()
        self.assertFalse(hasattr(module, "count_global_entries"))

    def test_global_dir_removed(self):
        module = _load_sdd_memory_module()
        self.assertFalse(hasattr(module, "global_dir"))

    def test_read_global_index_removed(self):
        module = _load_sdd_memory_module()
        self.assertFalse(hasattr(module, "read_global_index"))

    def test_read_index_removed(self):
        """MEMORY.md is never written now, so nothing in this module should still read it
        back either -- read_index()/--summary only ever existed to serve that file."""
        module = _load_sdd_memory_module()
        self.assertFalse(hasattr(module, "read_index"))

    def test_summary_flag_removed(self):
        with h.temp_home() as home:
            out, rc = h.run_sdd_memory_cli(["--summary"], cwd="/tmp", env_extra={"HOME": home})
            # falls through to the default branch (prints memory_dir), not a MEMORY.md read
            self.assertNotIn("SDD Memory Index", out)

    def test_spec_dir_and_path_flags_untouched(self):
        """Regression guard: the per-feature scaffolding this feature explicitly keeps."""
        module = _load_sdd_memory_module()
        self.assertTrue(hasattr(module, "spec_dir"))
        self.assertTrue(hasattr(module, "memory_dir"))
        self.assertTrue(hasattr(module, "ensure_dir"))


class ClaudePluginDataEnvVarTests(unittest.TestCase):
    """Tests for ${CLAUDE_PLUGIN_DATA} env var support (Task 4.3)."""

    def test_base_respects_claude_plugin_data_env_var(self):
        """Verify BASE uses CLAUDE_PLUGIN_DATA when set."""
        module = _load_sdd_memory_module()
        self.assertIn("sdd-memory", module.BASE)
        # Verify it's under a valid path (either env var or fallback)
        self.assertTrue(os.path.isabs(module.BASE) or module.BASE.startswith("~"))

    def test_memory_dir_returns_valid_path(self):
        """Verify memory_dir returns a valid path containing agent-isdd context."""
        module = _load_sdd_memory_module()
        d = module.memory_dir("/some/project")
        self.assertIn("sdd-memory", d)
        slug = module.project_slug("/some/project")
        self.assertTrue(d.endswith(slug))


class RepoRootSlugTests(unittest.TestCase):
    """A subdirectory of a git repo shares the repo's slug; a linked worktree keeps its own."""

    def setUp(self):
        import tempfile
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = h.make_git_repo(os.path.join(self._tmp.name, "repo"))
        self.sub = os.path.join(self.repo, "agent-nelly", "hooks")
        os.makedirs(self.sub)
        self.module = _load_sdd_memory_module()

    def tearDown(self):
        self._tmp.cleanup()

    def test_subdirectory_maps_to_repo_slug(self):
        self.assertEqual(self.module.project_slug(self.sub), self.module.project_slug(self.repo))

    def test_repo_slug_is_unchanged_path_transform(self):
        self.assertEqual(self.module.project_slug(self.repo), h.project_slug_for(self.repo))
        self.assertTrue(self.module.project_slug(self.repo).endswith("-repo"))

    def test_worktree_keeps_own_slug(self):
        wt = h.add_git_worktree(self.repo, os.path.join(self.repo, ".claude", "worktrees", "wt1"))
        wt_sub = os.path.join(wt, "scripts")
        os.makedirs(wt_sub)
        slug = self.module.project_slug(wt_sub)
        self.assertEqual(slug, self.module.project_slug(wt))
        self.assertTrue(slug.endswith("-repo-claude-worktrees-wt1"))

    def test_symlinked_cwd_into_repo_subdir_maps_to_repo(self):
        link = os.path.join(self._tmp.name, "link")
        os.symlink(self.sub, link)
        self.assertEqual(self.module.project_slug(link),
                         self.module.project_slug(os.path.realpath(self.repo)))

    def test_path_cli_through_symlinked_cwd_uses_pwd_spelling(self):
        link = os.path.join(self._tmp.name, "link")
        os.symlink(self.repo, link)
        with h.temp_home() as home:
            out, rc = h.run_sdd_memory_cli(["--path"], cwd=link, env_extra={"HOME": home, "PWD": link})
            self.assertEqual(rc, 0)
            self.assertEqual(os.path.basename(out), self.module.project_slug(link))

    def test_missing_dir_falls_back_to_cwd(self):
        missing = os.path.join(self._tmp.name, "no", "such", "dir")
        self.assertTrue(self.module.project_slug(missing).endswith("-no-such-dir"))

    def test_non_repo_dir_falls_back_to_cwd(self):
        plain = os.path.join(self._tmp.name, "plain", "sub")
        os.makedirs(plain)
        self.assertTrue(self.module.project_slug(plain).endswith("-plain-sub"))

    def test_path_cli_from_subdirectory_resolves_repo_store(self):
        with h.temp_home() as home:
            out_sub, rc1 = h.run_sdd_memory_cli(["--path"], cwd=self.sub, env_extra={"HOME": home})
            out_root, rc2 = h.run_sdd_memory_cli(["--path"], cwd=self.repo, env_extra={"HOME": home})
            self.assertEqual((rc1, rc2), (0, 0))
            self.assertEqual(out_sub, out_root)


if __name__ == "__main__":
    unittest.main()
