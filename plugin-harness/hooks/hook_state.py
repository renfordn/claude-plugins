"""Shared helpers for plugin-harness's hook entrypoints.

Locates and persists the same workflow-state.json that agent-isdd scaffolds and
agent-tdd reads, so the orchestrator's PreToolUse/SubagentStop hooks mutate the
one shared per-feature state file rather than an orchestrator-private copy.

Follows agent-isdd's resolved sdd-memory: the location agent-isdd records in its own
${CLAUDE_PLUGIN_DATA}/sdd-memory-location.json (which is its shared_memory_root when the user
configured one), else agent-isdd's ${CLAUDE_PLUGIN_DATA}/sdd-memory via the symlink/registry
coordination below.
"""
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from orchestrator.state_store import FileStateStore  # noqa: E402

# path_resolution.py lives alongside this file (a per-plugin copy -- see its own
# docstring for why it isn't imported from a monorepo-relative shared/ directory).
_this_dir = os.path.dirname(os.path.abspath(__file__))
if _this_dir not in sys.path:
    sys.path.insert(0, _this_dir)
from path_resolution import (  # noqa: E402
    PluginDataDirUnavailable, get_plugin_data_dir, get_legacy_subdir_path,
    get_sibling_plugin_data_dir,
)

# Resolve BASE directory using ${CLAUDE_PLUGIN_DATA} env var with fallback
_plugin_data_dir = get_plugin_data_dir("plugin-harness")
_default_base = get_legacy_subdir_path(_plugin_data_dir, "sdd-memory")


def _ensure_sdd_memory_coordination():
    """Coordinate sdd-memory access with agent-isdd via symlink or registry.

    Both agent-isdd and plugin-harness need access to the same sdd-memory
    directory for workflow state coordination. This function:
    1. Checks if plugin-harness's sdd-memory path exists
    2. If not, tries to create a symlink to agent-isdd's sdd-memory
    3. If symlink fails, creates a registry file with path metadata

    Resolving agent-isdd's directory here MUST go through
    get_sibling_plugin_data_dir(), not get_plugin_data_dir("agent-isdd") -- the
    latter ignores the name argument whenever ${CLAUDE_PLUGIN_DATA} is set and
    just returns *this plugin's own* data dir, so every real (marketplace)
    install was symlinking (or registering) plugin-harness's own empty
    directory back onto itself instead of pointing at agent-isdd's actual
    sdd-memory. Only the env-var-unset dev/test fallback ever exercised the
    correct path, which is why this went unnoticed by the test suite. See
    path_resolution.py's get_sibling_plugin_data_dir() docstring for the fix.

    Returns:
        The actual sdd-memory path (or None if coordination fails completely).
    """
    orch_sdd_memory = _default_base

    # If symlink already exists, we're good
    if os.path.islink(orch_sdd_memory):
        return orch_sdd_memory

    # If directory already exists (not a symlink), use it as-is
    if os.path.isdir(orch_sdd_memory):
        return orch_sdd_memory

    # Neither symlink nor directory exists; try to create symlink to agent-isdd's
    try:
        isdd_plugin_data = get_sibling_plugin_data_dir("plugin-harness", "agent-isdd")
        isdd_sdd_memory = get_legacy_subdir_path(isdd_plugin_data, "sdd-memory")

        # Only create symlink if agent-isdd's sdd-memory exists
        if os.path.isdir(isdd_sdd_memory):
            os.symlink(isdd_sdd_memory, orch_sdd_memory)
            return orch_sdd_memory
    except (OSError, NotImplementedError):
        # Symlink creation failed; fall back to registry file
        pass

    # Fallback: Create registry file so we know where sdd-memory actually is
    try:
        orch_plugin_data = os.path.dirname(_default_base)
        os.makedirs(orch_plugin_data, exist_ok=True)

        registry_path = os.path.join(orch_plugin_data, "sdd-memory-registry.json")

        # Only write registry if it doesn't already exist
        if not os.path.exists(registry_path):
            isdd_plugin_data = get_sibling_plugin_data_dir("plugin-harness", "agent-isdd")
            isdd_sdd_memory = get_legacy_subdir_path(isdd_plugin_data, "sdd-memory")

            registry = {
                "owner": "agent-isdd",
                "actual_path": isdd_sdd_memory,
                "created": True
            }
            with open(registry_path, "w", encoding="utf-8") as f:
                json.dump(registry, f)
    except (OSError, json.JSONDecodeError):
        pass

    return orch_sdd_memory


# Must match agent-isdd/hooks/sdd_memory.py's BASE_POINTER_NAME.
ISDD_BASE_POINTER_NAME = "sdd-memory-location.json"


def _isdd_pointer_base():
    """agent-isdd's resolved sdd-memory, as recorded by its SessionStart hook, or None.

    agent-isdd may be configured with a shared_memory_root (a userConfig option only
    agent-isdd's own hooks receive), in which case its sdd-memory is no longer under its
    ${CLAUDE_PLUGIN_DATA} at all and the symlink coordination below would point at stale
    state. agent-isdd writes its resolved location to ${CLAUDE_PLUGIN_DATA}/
    sdd-memory-location.json (sdd_memory.write_base_pointer()); following that keeps both
    plugins on the same directory. Missing/malformed/non-absolute -> None (fall back).
    """
    try:
        isdd_plugin_data = get_sibling_plugin_data_dir("plugin-harness", "agent-isdd")
        with open(os.path.join(isdd_plugin_data, ISDD_BASE_POINTER_NAME), "r", encoding="utf-8") as fh:
            location = json.load(fh).get("sdd_memory")
    except (OSError, ValueError, AttributeError, PluginDataDirUnavailable):
        return None
    if isinstance(location, str) and os.path.isabs(location):
        return os.path.normpath(location)
    return None


# Resolve at module import time: agent-isdd's recorded location first, else the
# symlink/registry coordination against its ${CLAUDE_PLUGIN_DATA}/sdd-memory.
BASE = _isdd_pointer_base()
if BASE is None:
    _ensure_sdd_memory_coordination()
    BASE = _default_base


def project_slug(cwd):
    absp = os.path.abspath(cwd)
    slug = re.sub(r"[^A-Za-z0-9]+", "-", absp).strip("-").lower()
    return slug or "root"


def memory_dir(cwd):
    return os.path.join(BASE, project_slug(cwd))


def error_registry_path(cwd):
    """Path to the project-wide error-registry.json (persistent, cross-session).

    Shared by the write side (subagent_stop.py, via ErrorLogger.persist_error)
    and the read side (before_continue.py's error-pattern context injection) so
    both hooks agree on the same file without either hardcoding the other's path.
    """
    return os.path.join(memory_dir(cwd), "error-registry.json")


def active_state_dir(cwd):
    """Directory of the most recently modified workflow-state.md under memory_dir(cwd), or None."""
    pattern = os.path.join(memory_dir(cwd), "spec", "*", "workflow-state.md")
    files = glob.glob(pattern)
    if not files:
        return None
    files.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    return os.path.dirname(files[0])


def workflow_state_path(cwd):
    """Path to the active feature's workflow-state.json, or None if no SDD workflow is active."""
    feature_dir = active_state_dir(cwd)
    if not feature_dir:
        return None
    return os.path.join(feature_dir, "workflow-state.json")


def _state_store_for(path):
    """Build a FileStateStore + workflow_id addressing the exact given path.

    FileStateStore addresses files by (directory, workflow_id) -> "<workflow_id>.json"
    within that directory; the workflow_id here is just the path's basename
    minus ".json", so the file written is the exact path the caller gave us.
    """
    directory = os.path.dirname(path) or "."
    workflow_id = os.path.basename(path)
    if workflow_id.endswith(".json"):
        workflow_id = workflow_id[: -len(".json")]
    return FileStateStore(directory), workflow_id


def load_workflow_state(path):
    """Load workflow-state.json into a dict, tolerant of a missing or malformed file."""
    try:
        store, workflow_id = _state_store_for(path)
        return store.get(workflow_id)
    except (OSError, ValueError):
        return {}


def save_workflow_state(path, data):
    """Write workflow-state.json back to disk (atomic write, advisory lock)."""
    store, workflow_id = _state_store_for(path)
    store.save(workflow_id, data)
