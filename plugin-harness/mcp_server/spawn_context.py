"""Pure-Python core of get_spawn_context, with no `mcp` package dependency.

Split out of server.py so this logic is importable and testable without
pulling in the `mcp` package's import chain -- server.py's only real
third-party dependency (see its own module docstring). This keeps the
harness's own logic in the same "dependency-free by design" category as the
production hooks (before_continue.py, subagent_stop.py), even though the
MCP server wrapper around it necessarily needs `mcp`.

Handles both response shapes design.md calls for:
  - SDD-workflow-active: reads workflow_state["orchestration"]["last_spawn_context"]
    (Tier 1 + Tier 2 + error-pattern context), unchanged from before this feature.
  - Standalone (no active SDD workflow): reads whatever
    orchestrator.hooks.before_continue.handle_standalone_spawn has already
    cached in HarnessContextCache for this project. Read-only, like the SDD
    path -- never calls handle_standalone_spawn itself, since that would
    write to HarnessContextCache and emit telemetry on every read, violating
    get_spawn_context's read-only contract (SECURITY.md).
"""
import os
import sys

_PLUGIN_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PLUGIN_ROOT not in sys.path:
    sys.path.insert(0, _PLUGIN_ROOT)
_HOOKS_DIR = os.path.join(_PLUGIN_ROOT, "hooks")
if _HOOKS_DIR not in sys.path:
    sys.path.insert(0, _HOOKS_DIR)

from hook_state import workflow_state_path, load_workflow_state, project_slug  # noqa: E402
from orchestrator.harness_context_cache import HarnessContextCache  # noqa: E402

_NO_CONTEXT_CACHED_MESSAGE = (
    "No spawn context cached yet for this project (before_continue.py "
    "hasn't run yet this session, or found nothing to cache) — proceed "
    "with your own research."
)


def build_spawn_context_response(agent_type: str, cwd: str) -> str:
    """Return the orchestrator context already computed for this project's
    most recent agent spawn, if any. See server.py's get_spawn_context for
    the full public docstring/contract; this is its pure-Python core.
    """
    state_path = workflow_state_path(cwd)
    if not state_path:
        return _build_standalone_response(cwd)

    workflow_state = load_workflow_state(state_path)
    if not workflow_state:
        return "Workflow state exists but could not be loaded — nothing cached to return."

    last_spawn = workflow_state.get("orchestration", {}).get("last_spawn_context")
    if not last_spawn:
        return _NO_CONTEXT_CACHED_MESSAGE

    parts = [
        last_spawn.get("tier1_context"),
        last_spawn.get("tier2_context"),
        last_spawn.get("error_pattern_context"),
    ]
    joined = "\n\n".join(p for p in parts if p)
    return joined or "Spawn context was cached but is empty — proceed with your own research."


def _build_standalone_response(cwd: str) -> str:
    """No active SDD workflow: read (never build/write) whatever
    handle_standalone_spawn has already cached in HarnessContextCache for
    this project -- mirrors the SDD path's own read-only, no-fresh-compute
    contract.
    """
    cache = HarnessContextCache(project_slug(cwd))
    capability_map = cache.get("capability_map")
    nelly_brief_entry = cache.get("nelly_brief")

    if not capability_map and not nelly_brief_entry:
        return _NO_CONTEXT_CACHED_MESSAGE

    parts = ["=== STANDALONE CONTEXT (source: standalone) ==="]
    if capability_map:
        plugin_list = ", ".join(capability_map.keys())
        parts.append(f"## Capability Map\nAvailable plugins: {plugin_list}")

    brief_text = None
    if isinstance(nelly_brief_entry, dict):
        brief_text = nelly_brief_entry.get("brief_text")
    if brief_text:
        parts.append(f"## Project Context (from Nelly Brief)\n{brief_text}")

    joined = "\n\n".join(parts)
    return joined or "Spawn context was cached but is empty — proceed with your own research."
