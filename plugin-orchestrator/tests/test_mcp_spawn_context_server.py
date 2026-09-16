"""End-to-end test for mcp_server/server.py's get_spawn_context tool.

Skipped entirely when the `mcp` package isn't installed (see
mcp_server/requirements.txt) -- unlike the production hooks
(before_continue.py, subagent_stop.py), which stay dependency-free by
design, the bundled MCP server is the one place in this plugin with a real
third-party dependency, so its tests are opt-in rather than part of the
always-green suite.

Runs the server as a real stdio subprocess and drives it with a real MCP
client session -- not a unit test of the decorated function in isolation --
because the actual bug this tool works around (the Agent tool's broken
updatedInput merge, see hooks/before_continue.py) is a wire-protocol-level
concern: what matters is that a subagent calling this tool over stdio gets
the context back, not that some Python function returns the right string.

hook_state.py resolves ${CLAUDE_PLUGIN_DATA} into a module-level BASE
constant at *import* time, not per call. Under `unittest discover`, some
earlier test module in the same process may import hook_state first (with
whatever CLAUDE_PLUGIN_DATA happened to be set then, often unset -- which
would resolve BASE to the real ~/.claude/plugins/data/... on this machine),
and Python's module cache means a later `import hook_state` here is a
no-op that can't re-resolve it. Setting the env var from this file would
therefore either do nothing (already cached) or, worse, seed test fixtures
into the user's real ~/.claude directory. Each test instead patches
hook_state.BASE directly (a temp dir, scoped per test via setUp/addCleanup)
and passes that same directory to the subprocess via CLAUDE_PLUGIN_DATA, so
parent and child always agree on where the state lives, and nothing touches
the real filesystem outside temp dirs.
"""
import asyncio
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

try:
    import mcp  # noqa: F401
    HAS_MCP = True
except ImportError:
    HAS_MCP = False

PLUGIN_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SERVER_SCRIPT = os.path.join(PLUGIN_ROOT, "mcp_server", "server.py")

sys.path.insert(0, PLUGIN_ROOT)
sys.path.insert(0, os.path.join(PLUGIN_ROOT, "hooks"))

import hook_state  # noqa: E402


async def _call_get_spawn_context(cwd, plugin_data_dir):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    env = dict(os.environ)
    env["CLAUDE_PLUGIN_DATA"] = plugin_data_dir
    params = StdioServerParameters(command=sys.executable, args=[SERVER_SCRIPT], env=env)
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            result = await session.call_tool(
                "get_spawn_context", {"agent_type": "agent-tdd", "cwd": cwd}
            )
            return tools, result


@unittest.skipUnless(HAS_MCP, "mcp package not installed (pip install -r mcp_server/requirements.txt)")
class TestSpawnContextServer(unittest.TestCase):
    def setUp(self):
        self.plugin_data_dir = tempfile.mkdtemp()
        patcher = patch.object(hook_state, "BASE", os.path.join(self.plugin_data_dir, "sdd-memory"))
        patcher.start()
        self.addCleanup(patcher.stop)

    def _seed_workflow_state(self, last_spawn_context):
        """Write a workflow-state.json + its workflow-state.md marker under
        this test's patched BASE, the same shape active_state_dir() looks
        for, and return the cwd whose project_slug maps to it."""
        cwd = tempfile.mkdtemp()
        feature_dir = os.path.join(hook_state.memory_dir(cwd), "spec", "my-feature")
        os.makedirs(feature_dir, exist_ok=True)
        with open(os.path.join(feature_dir, "workflow-state.md"), "w") as f:
            f.write("marker\n")

        state_path = os.path.join(feature_dir, "workflow-state.json")
        hook_state.save_workflow_state(state_path, {"orchestration": {"last_spawn_context": last_spawn_context}})
        return cwd

    def test_lists_get_spawn_context_tool(self):
        cwd = tempfile.mkdtemp()
        tools, _ = asyncio.run(_call_get_spawn_context(cwd, self.plugin_data_dir))
        self.assertIn("get_spawn_context", [t.name for t in tools.tools])

    def test_no_active_workflow_returns_plain_message(self):
        cwd = tempfile.mkdtemp()  # no workflow-state.md under this cwd's memory_dir
        _, result = asyncio.run(_call_get_spawn_context(cwd, self.plugin_data_dir))
        text = result.content[0].text
        self.assertIn("No active SDD workflow", text)

    def test_no_cached_spawn_context_returns_plain_message(self):
        cwd = self._seed_workflow_state(last_spawn_context=None)
        _, result = asyncio.run(_call_get_spawn_context(cwd, self.plugin_data_dir))
        text = result.content[0].text
        self.assertIn("No spawn context cached yet", text)

    def test_returns_cached_tier1_and_tier2_context(self):
        cwd = self._seed_workflow_state(last_spawn_context={
            "agent_type": "agent-tdd",
            "tier1_context": "=== TIER 1: STABLE CONTEXT ===\nAvailable plugins: agent-isdd, agent-tdd",
            "tier2_context": "=== TIER 2: DESIGN SPECIFICATION ===\n## Requirements\nDo the thing.",
            "error_pattern_context": None,
        })
        _, result = asyncio.run(_call_get_spawn_context(cwd, self.plugin_data_dir))
        text = result.content[0].text
        self.assertIn("TIER 1: STABLE CONTEXT", text)
        self.assertIn("Available plugins: agent-isdd, agent-tdd", text)
        self.assertIn("TIER 2: DESIGN SPECIFICATION", text)
        self.assertIn("Do the thing.", text)


if __name__ == "__main__":
    unittest.main()
