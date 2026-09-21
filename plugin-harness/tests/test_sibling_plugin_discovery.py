"""Tests for CapabilityMap's sibling-plugin discovery (F-13, 2026-09-21 GTM review).

Before this fix, CapabilityMap always read INTEROP.md from a single flat
`plugin_dir_base` -- in production that's a separately maintained git clone
(`~/.claude/plugins/claude-plugins`, cloned/pulled by hooks/bootstrap-plugins.sh).
A failed `git pull` there is swallowed and the stale checkout kept, so that
clone's INTEROP.md content could silently diverge from the plugin versions
actually installed and running -- `.exists()` alone can't detect staleness,
since the file is still there, just outdated.

`_discover_sibling_plugin_roots()` instead locates each sibling plugin's real,
currently-installed root directory from this plugin's own ${CLAUDE_PLUGIN_ROOT},
by scanning nearby directories for `.claude-plugin/plugin.json` files and
reading each one's own declared "name" -- which is always exactly the version
Claude Code actually installed and is running right now.
"""
import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

from orchestrator.interop_parser import CapabilityMap


def _write_plugin(root: Path, name: str, interop_content: str = "# INTEROP\n") -> None:
    """Scaffold a minimal installed-plugin directory: <root>/.claude-plugin/plugin.json
    plus an INTEROP.md (or STRUCTURE.md for agent-cache-plugin) at the plugin root.
    """
    manifest_dir = root / ".claude-plugin"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    (manifest_dir / "plugin.json").write_text(json.dumps({"name": name, "version": "0.0.1"}))

    filename = "STRUCTURE.md" if name == "agent-cache-plugin" else "INTEROP.md"
    (root / filename).write_text(interop_content)


class TestSiblingDiscoveryMarketplaceCacheLayout(unittest.TestCase):
    """<cache-root>/<marketplace>/<plugin>/<version>/ -- the CLI's own layout,
    confirmed against ~/.claude/plugins/cache/<marketplace>/ on a real machine.
    """

    def test_discovers_siblings_two_levels_up_with_version_subdirs(self):
        with self._tmp_marketplace_layout() as (marketplace_root, own_root):
            with patch.dict(os.environ, {"CLAUDE_PLUGIN_ROOT": str(own_root)}, clear=False):
                # plugin_dir_base explicitly given -> discovery still runs internally
                # via a fresh instance constructed with plugin_dir_base=None.
                cm = CapabilityMap.__new__(CapabilityMap)
                cm.PLUGIN_PATHS = CapabilityMap.PLUGIN_PATHS  # class attr, just for clarity
                discovered = CapabilityMap._discover_sibling_plugin_roots(cm)

            self.assertEqual(
                discovered.get("agent-isdd"),
                marketplace_root / "agent-isdd" / "0.1.44",
            )
            self.assertEqual(
                discovered.get("agent-tdd"),
                marketplace_root / "agent-tdd" / "0.2.10",
            )

    def test_picks_highest_version_when_multiple_installed(self):
        with self._tmp_marketplace_layout(agent_tdd_versions=["0.1.0", "0.2.10", "0.1.9"]) as (
            marketplace_root, own_root
        ):
            with patch.dict(os.environ, {"CLAUDE_PLUGIN_ROOT": str(own_root)}, clear=False):
                cm = CapabilityMap.__new__(CapabilityMap)
                discovered = CapabilityMap._discover_sibling_plugin_roots(cm)

            self.assertEqual(
                discovered.get("agent-tdd"),
                marketplace_root / "agent-tdd" / "0.2.10",
            )

    def _tmp_marketplace_layout(self, agent_tdd_versions=None):
        import tempfile
        import contextlib

        @contextlib.contextmanager
        def _ctx():
            with tempfile.TemporaryDirectory() as tmp:
                marketplace_root = Path(tmp) / "cache" / "renfordn-plugins"
                own_root = marketplace_root / "plugin-harness" / "1.2.9"
                _write_plugin(own_root, "plugin-harness")
                _write_plugin(marketplace_root / "agent-isdd" / "0.1.44", "agent-isdd")
                for v in (agent_tdd_versions or ["0.2.10"]):
                    _write_plugin(marketplace_root / "agent-tdd" / v, "agent-tdd")
                yield marketplace_root, own_root

        return _ctx()


class TestSiblingDiscoveryDesktopSnapshotLayout(unittest.TestCase):
    """<session-root>/plugin_<random-id>/ -- the desktop app's layout, where
    directory names carry no plugin identity at all and only plugin.json's
    own "name" field can identify each sibling.
    """

    def test_discovers_siblings_one_level_up_with_random_dir_names(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            session_root = Path(tmp) / "rpm"
            own_root = session_root / "plugin_01X5qiCWSsQTSjzgJeiEoift"
            sibling_root = session_root / "plugin_011Geb3E8GoLRe3JpL6baoyA"
            _write_plugin(own_root, "plugin-harness")
            _write_plugin(sibling_root, "agent-tdd")

            with patch.dict(os.environ, {"CLAUDE_PLUGIN_ROOT": str(own_root)}, clear=False):
                cm = CapabilityMap.__new__(CapabilityMap)
                discovered = CapabilityMap._discover_sibling_plugin_roots(cm)

            self.assertEqual(discovered.get("agent-tdd"), sibling_root)


class TestSiblingDiscoveryFallbackBehavior(unittest.TestCase):
    def test_returns_empty_dict_when_env_var_unset(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CLAUDE_PLUGIN_ROOT", None)
            cm = CapabilityMap.__new__(CapabilityMap)
            self.assertEqual(CapabilityMap._discover_sibling_plugin_roots(cm), {})

    def test_returns_empty_dict_when_no_siblings_discoverable(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            own_root = Path(tmp) / "some-plugin"
            _write_plugin(own_root, "plugin-harness")
            with patch.dict(os.environ, {"CLAUDE_PLUGIN_ROOT": str(own_root)}, clear=False):
                cm = CapabilityMap.__new__(CapabilityMap)
                self.assertEqual(CapabilityMap._discover_sibling_plugin_roots(cm), {})

    def test_test_fixture_construction_never_triggers_discovery(self):
        """CapabilityMap(explicit_dir) must never consult ${CLAUDE_PLUGIN_ROOT} --
        every test/fixture construction must stay fully isolated from whatever
        happens to be in the invoking shell's environment.
        """
        with self._tmp_marketplace_layout() as own_root:
            with patch.dict(os.environ, {"CLAUDE_PLUGIN_ROOT": str(own_root)}, clear=False):
                fixtures_dir = Path(__file__).parent / "fixtures"
                cm = CapabilityMap(str(fixtures_dir))
        self.assertEqual(cm._sibling_plugin_roots, {})

    def _tmp_marketplace_layout(self):
        import tempfile
        import contextlib

        @contextlib.contextmanager
        def _ctx():
            with tempfile.TemporaryDirectory() as tmp:
                own_root = Path(tmp) / "cache" / "mp" / "plugin-harness" / "1.0.0"
                _write_plugin(own_root, "plugin-harness")
                _write_plugin(Path(tmp) / "cache" / "mp" / "agent-tdd" / "0.1.0", "agent-tdd")
                yield own_root

        return _ctx()


class TestResolveInteropPathPrefersSibling(unittest.TestCase):
    def test_prefers_discovered_sibling_over_flat_plugin_dir_base(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            # A stale/flat legacy dir (stands in for the git clone).
            legacy_base = Path(tmp) / "legacy"
            (legacy_base / "agent-tdd").mkdir(parents=True)
            (legacy_base / "agent-tdd" / "INTEROP.md").write_text("STALE CONTENT\n")

            # A fresh, "actually installed" sibling.
            marketplace_root = Path(tmp) / "cache" / "mp"
            own_root = marketplace_root / "plugin-harness" / "1.0.0"
            sibling_root = marketplace_root / "agent-tdd" / "9.9.9"
            _write_plugin(own_root, "plugin-harness")
            _write_plugin(sibling_root, "agent-tdd", interop_content="FRESH CONTENT\n")

            with patch.dict(os.environ, {"CLAUDE_PLUGIN_ROOT": str(own_root)}, clear=False):
                cm = CapabilityMap.__new__(CapabilityMap)
                cm._sibling_plugin_roots = CapabilityMap._discover_sibling_plugin_roots(cm)
            cm.plugin_dir_base = legacy_base

            resolved = cm._resolve_interop_path("agent-tdd", "agent-tdd/INTEROP.md")
            self.assertEqual(resolved.read_text(), "FRESH CONTENT\n")

    def test_falls_back_to_legacy_path_when_sibling_not_discovered(self):
        cm = CapabilityMap.__new__(CapabilityMap)
        cm._sibling_plugin_roots = {}
        cm.plugin_dir_base = Path(__file__).parent / "fixtures"

        resolved = cm._resolve_interop_path("agent-tdd", "agent-tdd/INTEROP.md")
        self.assertEqual(resolved, Path(__file__).parent / "fixtures" / "agent-tdd" / "INTEROP.md")


if __name__ == "__main__":
    unittest.main()
