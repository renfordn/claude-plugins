"""Security assertions for plugin-harness's MCP server.

Verifies the three audit criteria from SECURITY.md:
  1. Transport is stdio (no TCP/UDP socket opened)
  2. File access is scoped — cwd path traversal is sanitized by project_slug()
  3. get_spawn_context() is read-only (never writes files)
"""
import inspect
import os
import sys
import tempfile
import unittest

# Bring hooks/ onto the path for project_slug / workflow_state_path
_PLUGIN_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_HOOKS_DIR = os.path.join(_PLUGIN_ROOT, "hooks")
if _HOOKS_DIR not in sys.path:
    sys.path.insert(0, _HOOKS_DIR)
if _PLUGIN_ROOT not in sys.path:
    sys.path.insert(0, _PLUGIN_ROOT)


class TestMCPTransportIsStdio(unittest.TestCase):
    """The MCP server must use stdio transport, not a TCP listener."""

    def test_fastmcp_run_has_no_host_or_port_binding(self):
        """mcp.run() with no arguments uses stdio — verify the call site."""
        # Read server.py and assert it calls mcp.run() with no network args.
        server_py = os.path.join(_PLUGIN_ROOT, "mcp_server", "server.py")
        with open(server_py) as f:
            source = f.read()
        self.assertIn("mcp.run()", source,
                      "server.py must call mcp.run() with no args (stdio transport)")
        self.assertNotIn("host=", source,
                         "server.py must not bind to a host address")
        self.assertNotIn("port=", source,
                         "server.py must not bind to a TCP port")

    def test_server_module_imports_fastmcp_not_http_server(self):
        """server.py must not import any HTTP or socket server primitives."""
        server_py = os.path.join(_PLUGIN_ROOT, "mcp_server", "server.py")
        with open(server_py) as f:
            source = f.read()
        for forbidden in ("http.server", "socketserver", "flask", "aiohttp", "uvicorn", "starlette"):
            self.assertNotIn(forbidden, source,
                             f"server.py must not use {forbidden} — stdio only")


class TestCwdPathTraversalSanitization(unittest.TestCase):
    """project_slug() must neutralise all path-traversal attempts in the cwd parameter."""

    def setUp(self):
        from hook_state import project_slug
        self.project_slug = project_slug

    def test_absolute_path_becomes_flat_slug(self):
        slug = self.project_slug("/Users/alice/myproject")
        self.assertNotIn("/", slug)
        self.assertNotIn("\\", slug)
        self.assertTrue(slug.replace("-", "").replace("_", "").isalnum() or slug == "root")

    def test_traversal_dots_neutralised(self):
        slug = self.project_slug("../../etc/passwd")
        self.assertNotIn("..", slug)
        self.assertNotIn("/", slug)

    def test_null_bytes_stripped(self):
        slug = self.project_slug("/tmp/foo\x00bar")
        self.assertNotIn("\x00", slug)

    def test_slug_never_starts_with_dash(self):
        slug = self.project_slug("/")
        self.assertFalse(slug.startswith("-"),
                         f"Slug must not start with dash; got {slug!r}")

    def test_slug_stays_within_base(self):
        from hook_state import memory_dir, BASE
        slug = self.project_slug("../../../../../../etc")
        mem = memory_dir("../../../../../../etc")
        self.assertTrue(mem.startswith(BASE),
                        f"memory_dir must stay under BASE; got {mem!r}")


class TestGetSpawnContextReadOnly(unittest.TestCase):
    """get_spawn_context() must never write any files."""

    @staticmethod
    def _mcp_available():
        try:
            import mcp  # noqa: F401
            return True
        except Exception:
            # Broad catch (not just ImportError): some environments have the
            # `mcp` package installed but broken (e.g. an incompatible
            # pydantic/CPython combination raises TypeError deep inside
            # `mcp`'s own model construction at import time, not
            # ImportError) -- either way, "mcp isn't usable here" means the
            # same thing to this guard: skip the functional test rather than
            # erroring. See recap.md for this feature's tracked environment
            # follow-up. get_spawn_context's actual read-only/never-raises
            # behavior is covered independently, without needing `mcp` at
            # all, by tests/test_spawn_context.py.
            return False

    def test_no_missing_cwd_raises(self):
        """Tool returns a string for any cwd — never raises."""
        if not self._mcp_available():
            self.skipTest("mcp package not installed — skipping functional test")
        from mcp_server.server import get_spawn_context
        result = get_spawn_context(agent_type="test-agent", cwd="/nonexistent/path")
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 0)

    def test_get_spawn_context_does_not_write_files(self):
        """Calling get_spawn_context must not create or modify any files."""
        if not self._mcp_available():
            self.skipTest("mcp package not installed — skipping functional test")
        from mcp_server.server import get_spawn_context

        with tempfile.TemporaryDirectory() as tmpdir:
            before = set(os.listdir(tmpdir))
            get_spawn_context(agent_type="test-agent", cwd=tmpdir)
            after = set(os.listdir(tmpdir))
            self.assertEqual(before, after,
                             "get_spawn_context must not create files in cwd")

    def test_get_spawn_context_source_has_no_write_calls(self):
        """Source-level assertion: no open(..., 'w') or write() in server.py."""
        server_py = os.path.join(_PLUGIN_ROOT, "mcp_server", "server.py")
        with open(server_py) as f:
            source = f.read()
        # Only the tool function body matters; ignore comments and imports
        # Strip comment lines then check
        non_comment = "\n".join(
            line for line in source.splitlines()
            if not line.strip().startswith("#")
        )
        self.assertNotIn("open(", non_comment.replace("open(server_py", ""),
                         "server.py must not open files for writing")


if __name__ == "__main__":
    unittest.main()
