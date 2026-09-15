"""Shared helpers for plugin-orchestrator's hook entrypoints.

Locates and persists the same workflow-state.json that agent-isdd scaffolds and
agent-tdd reads, so the orchestrator's PreToolUse/SubagentStop hooks mutate the
one shared per-feature state file rather than an orchestrator-private copy.

Resolves ${CLAUDE_PLUGIN_DATA} env var for official storage location. Since this
plugin shares sdd-memory with agent-isdd, symlink logic is coordinated in Task 3.1.
"""
import glob
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from orchestrator.state_store import FileStateStore  # noqa: E402

# Add shared directory to path for path_resolution import
_shared_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'shared')
if _shared_dir not in sys.path:
    sys.path.insert(0, _shared_dir)
from path_resolution import get_plugin_data_dir, get_legacy_subdir_path

# Resolve BASE directory using ${CLAUDE_PLUGIN_DATA} env var with fallback
_plugin_data_dir = get_plugin_data_dir("plugin-orchestrator")
_default_base = get_legacy_subdir_path(_plugin_data_dir, "sdd-memory")


def _ensure_sdd_memory_coordination():
    """Coordinate sdd-memory access with agent-isdd via symlink or registry.

    Both agent-isdd and plugin-orchestrator need access to the same sdd-memory
    directory for workflow state coordination. This function:
    1. Checks if plugin-orchestrator's sdd-memory path exists
    2. If not, tries to create a symlink to agent-isdd's sdd-memory
    3. If symlink fails, creates a registry file with path metadata

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
        isdd_plugin_data = get_plugin_data_dir("agent-isdd")
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
            isdd_plugin_data = get_plugin_data_dir("agent-isdd")
            isdd_sdd_memory = get_legacy_subdir_path(isdd_plugin_data, "sdd-memory")

            registry = {
                "owner": "agent-isdd",
                "actual_path": isdd_sdd_memory,
                "created": True
            }
            import json
            with open(registry_path, "w", encoding="utf-8") as f:
                json.dump(registry, f)
    except (OSError, json.JSONDecodeError):
        pass

    return orch_sdd_memory


# Call coordination at module import time
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
