#!/usr/bin/env python3
"""MCP server bundled with plugin-harness.

Exposes `get_spawn_context`, a read-only pull alternative to
`hooks/before_continue.py`'s context injection. That hook computes Tier 1
(capability map + nelly brief), Tier 2 (design spec), and error-pattern
context on every `Agent`-tool spawn -- but can never inject it into the
spawned subagent's own prompt, because the harness's `updatedInput` merge
for the `Agent` tool is broken (see `hooks/before_continue.py`'s module
docstring and `tests/test_before_continue_cli_contract.py` for the full
history). Today that computed context is simply thrown away.

A subagent has no `Agent` tool and cannot invoke another skill or hook, but
it *can* call an ordinary MCP tool. So instead of trying (and failing) to
push context into a prompt, this lets the subagent pull the exact same
context itself, on its own initiative, the first time it needs orchestration
context.

Registered via this plugin's `mcpServers` field (`.claude-plugin/plugin.json`
or an `.mcp.json` it points to), started automatically alongside the plugin.
Requires the `mcp` package (`pip install "mcp<2"` -- see
`mcp_server/requirements.txt`). Unlike the production hooks
(`before_continue.py`, `subagent_stop.py`), which stay dependency-free by
design (see their own module docstrings / this plugin's README), an MCP
server necessarily needs the protocol implementation, so this is the one
place in the plugin that carries a real third-party dependency.
"""
import os
import sys

_PLUGIN_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _PLUGIN_ROOT)
sys.path.insert(0, os.path.join(_PLUGIN_ROOT, "hooks"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # this dir, for spawn_context

try:
    from mcp.server.fastmcp import FastMCP  # noqa: E402
except ImportError:
    print(
        "plugin-harness's spawn-context MCP server requires the `mcp` package. "
        "Install it with: pip install -r \"" + os.path.join(_PLUGIN_ROOT, "mcp_server", "requirements.txt") + "\"",
        file=sys.stderr,
    )
    sys.exit(1)

from spawn_context import build_spawn_context_response  # noqa: E402

mcp = FastMCP("plugin-harness")


@mcp.tool()
def get_spawn_context(agent_type: str, cwd: str) -> str:
    """Return the orchestrator context already computed for this project's
    most recent agent spawn, if any -- the same Tier 1/Tier 2/error-pattern
    context an orchestrating skill's spawn would otherwise try and fail to
    inject into your prompt (the `Agent` tool's `updatedInput` merge is
    broken in this harness).

    Call this once, early, right after you're spawned. Safe to call more
    than once in the same session -- it only ever reads workflow-state.json
    (or, with no active SDD workflow, HarnessContextCache), never mutates
    it, never creates a checkpoint, and never consumes a pending rollback
    marker (that stays the PreToolUse hook's own one-shot responsibility,
    surfaced via `systemMessage` instead).

    Args:
        agent_type: Your own agent type/name (e.g. "agent-tdd"). Informational
            only -- context is not filtered per agent_type today.
        cwd: The project's working directory, same value your caller's own
            Bash/Read calls use -- needed to locate workflow-state.json (or,
            standalone, to scope the HarnessContextCache lookup).

    Returns:
        The cached Tier 1 + Tier 2 + error-pattern context string (SDD
        workflow active) or the cached standalone capability-map/nelly-brief
        context (no SDD workflow active), or a plain sentence explaining why
        there's nothing to return yet.
    """
    return build_spawn_context_response(agent_type, cwd)


if __name__ == "__main__":
    mcp.run()
