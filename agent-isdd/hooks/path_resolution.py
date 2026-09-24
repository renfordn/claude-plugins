#!/usr/bin/env python3
"""Per-plugin copy of shared/path_resolution.py, from the Claude-Plugins monorepo.

Duplicated deliberately, not imported cross-directory: a marketplace-installed plugin package
contains only this plugin's own subdirectory, never the monorepo's sibling shared/ folder --
`sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "shared"))` resolved
fine inside the dev checkout but raised ModuleNotFoundError for every real install (found
2026-09-16, affected every plugin depending on it since the ${CLAUDE_PLUGIN_DATA} migration).
Keep this file's content in sync with shared/path_resolution.py and the other plugins' copies
if you change the resolution logic -- shared/ remains the canonical source for whole-repo
testing (see shared/test_path_resolution.py), this is the one that actually ships.

Identity-split hazard (found 2026-09-24, debugging a false commit-gate denial): Claude Code can
load the SAME plugin under more than one identity in the same install -- e.g. this monorepo's
local checkout as `agent-isdd@inline` versus a marketplace install as `agent-isdd@renfordn-
plugins` (see ~/.claude.json's `pluginUsage` map). Each identity gets its OWN `${CLAUDE_PLUGIN_DATA}`
injected into ITS registered hook subprocesses (e.g. `.../plugins/data/agent-isdd-inline/` vs.
`.../plugins/data/agent-isdd/`) -- real hook invocations for a given session consistently see
whichever identity's env var is wired up, so every registered hook agrees with every other
registered hook within one session. The env var is NEVER injected into a plain manual
subprocess -- e.g. a Bash tool call running `python3 hooks/sdd_memory.py ...` directly, instead
of going through the actual hook chain -- so that call silently falls back to the bare,
non-suffixed guess below, which may not match whichever identity's hooks are actually
registered this session. Any state written that way (or read by a script invoked that way) can
silently diverge from what real hooks see; a discovery-based hook (one that locates its own
state via get_plugin_data_dir()/memory_dir()/active_state_file() rather than being handed an
explicit path in its own PreToolUse/PostToolUse/SubagentStop payload) that finds nothing under
its resolved path can't tell "no workflow is active" apart from "the workflow is one directory
over" -- see e.g. hooks/design_spec_gate.py and hooks/commit_audit_gate.py, both of which fall
through (no decision / no active workflow) rather than erroring when this happens, which for a
gate hook means a silent allow, not just a stale-looking read.

Rule of thumb: NEVER invoke hooks/*.py (or any script that imports this module) directly from a
plain shell during interactive session work -- e.g. `python3 hooks/sdd_memory.py --spec-path
...` typed by a human, or run via a Bash tool call, outside the real registered hook chain. Any
inspection or scaffolding that needs the *actual* active identity's data dir must go through a
real hook invocation (or a skill/command that itself only ever calls into these hooks the same
way hooks.json does), never a bare interactive invocation of this module's callers.
"""
import os
import sys


def get_plugin_data_dir(plugin_name: str) -> str:
    """Resolve plugin data directory using ${CLAUDE_PLUGIN_DATA} env var.

    Args:
        plugin_name: Name of the plugin (e.g., "agent-nelly")

    Returns:
        Absolute path to plugin data directory. Never None.

    Behavior:
        - If CLAUDE_PLUGIN_DATA env var is set (Claude Code runtime): returns that path
        - If unset (local dev/testing, OR a manual/direct invocation outside the real hook
          chain -- see this module's docstring): returns ~/.claude/plugins/data/{plugin_name}/,
          and prints a one-line warning to stderr so anyone watching (or reading logs) can see
          that this process is not resolving via a real hook's env var and this guessed path may
          not match whichever plugin identity's hooks are actually registered this session.

    The returned path may not exist; caller is responsible for creation. The env var
    is set by Claude Code to ensure data persists across updates and is cleaned on uninstall.
    """
    data_dir = os.environ.get("CLAUDE_PLUGIN_DATA")
    if not data_dir:
        # Fallback: local development, testing, or a manual/direct invocation outside the real
        # hook chain (Claude Code didn't set the env var for this process). This guess can
        # silently diverge from whatever identity's hooks are actually registered this session
        # -- see the identity-split hazard in this module's docstring -- so warn loudly rather
        # than silently guessing. Non-fatal: callers (including tests, which rely on this exact
        # fallback under a temp HOME) still get a usable path back.
        print(
            f"path_resolution: CLAUDE_PLUGIN_DATA is not set; falling back to a guessed data "
            f"dir for '{plugin_name}'. This is expected for local dev/tests, but if this "
            f"process is meant to be a real Claude Code hook, its env var wasn't injected -- "
            f"and if this is a manual/direct script invocation, the guessed path below may not "
            f"match whichever plugin identity's hooks are actually registered this session "
            f"(see path_resolution.py's module docstring). Never treat this path as "
            f"authoritative for gate/state decisions without confirming it matches the active "
            f"identity's ${{CLAUDE_PLUGIN_DATA}}.",
            file=sys.stderr,
        )
        data_dir = os.path.join(
            os.path.expanduser("~"),
            ".claude",
            "plugins",
            "data",
            plugin_name
        )
    return data_dir


def get_legacy_subdir_path(plugin_data_dir: str, legacy_name: str) -> str:
    """Join plugin data directory with legacy subdir name.

    Args:
        plugin_data_dir: Base plugin data directory (from get_plugin_data_dir)
        legacy_name: Legacy subdir name (e.g., "agent-nelly-memory")

    Returns:
        Joined absolute path: {plugin_data_dir}/{legacy_name}/

    Example:
        data_dir = get_plugin_data_dir("agent-nelly")
        memory_path = get_legacy_subdir_path(data_dir, "agent-nelly-memory")
        # memory_path = ~/.claude/plugins/data/agent-nelly/agent-nelly-memory/
    """
    return os.path.join(plugin_data_dir, legacy_name)
