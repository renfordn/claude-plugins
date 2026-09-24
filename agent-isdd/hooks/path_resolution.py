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
of going through the actual hook chain -- so get_plugin_data_dir() raises
PluginDataDirUnavailable there instead of guessing a path that may not match whichever
identity's hooks are actually registered this session. When it used to guess, any state written that way (or read by a script invoked that way) could
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


class PluginDataDirUnavailable(RuntimeError):
    """CLAUDE_PLUGIN_DATA is not set, so this process can't know its plugin's data directory."""


def get_plugin_data_dir(plugin_name: str) -> str:
    """Resolve the plugin data directory from ${CLAUDE_PLUGIN_DATA}.

    Args:
        plugin_name: Name of the plugin (e.g., "agent-nelly"), used only in the error message.

    Returns:
        The value of CLAUDE_PLUGIN_DATA. The directory may not exist yet; the caller creates it.

    Raises:
        PluginDataDirUnavailable: CLAUDE_PLUGIN_DATA is unset or empty.

    Claude Code sets CLAUDE_PLUGIN_DATA for hook subprocesses and substitutes
    ${CLAUDE_PLUGIN_DATA} in skill/command content. There is deliberately no fallback: the real
    directory is ~/.claude/plugins/data/<plugin>-<marketplace>/ (per install identity), so any
    guessed path can silently read or write the wrong identity's state. A script run by hand
    must be given the variable explicitly, e.g.
    `CLAUDE_PLUGIN_DATA="${CLAUDE_PLUGIN_DATA}" python3 "${CLAUDE_PLUGIN_ROOT}/hooks/<script>.py"`
    from skill/command content. Tests set it to a temp dir.
    """
    data_dir = os.environ.get("CLAUDE_PLUGIN_DATA")
    if not data_dir:
        raise PluginDataDirUnavailable(
            f"{plugin_name}: CLAUDE_PLUGIN_DATA is not set. Run this through Claude Code "
            f"(hook, or a skill/command that passes CLAUDE_PLUGIN_DATA=\"${{CLAUDE_PLUGIN_DATA}}\"), "
            f"or set CLAUDE_PLUGIN_DATA to this plugin's data directory yourself."
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
        # memory_path = ${CLAUDE_PLUGIN_DATA}/agent-nelly-memory/
    """
    return os.path.join(plugin_data_dir, legacy_name)


# --- shared memory root (keep this block byte-identical in every copy of this file) ---

# userConfig key `shared_memory_root` (declared in agent-nelly's and agent-isdd's plugin.json).
# Claude Code exports it to hook processes as CLAUDE_PLUGIN_OPTION_<KEY uppercased>; skill/agent
# content that runs a hook script by hand passes it through the same way it passes
# CLAUDE_PLUGIN_DATA: CLAUDE_PLUGIN_OPTION_SHARED_MEMORY_ROOT="${user_config.shared_memory_root}".
SHARED_MEMORY_ROOT_ENV = "CLAUDE_PLUGIN_OPTION_SHARED_MEMORY_ROOT"

# Written into a shared root the first time a plugin uses it (never overwritten afterwards).
# nelly-index.json is derived from entries/ (rebuilt at SessionStart), so syncing it would only
# produce conflicts; the append-only files merge cleanly as a union of both sides' lines.
SHARED_ROOT_GITIGNORE = (
    "# Derived or machine-local files -- regenerated per machine, never synced.\n"
    "nelly-index.json\n"
    "hotspots.json\n"
    "last-stop.json\n"
    "snapshots/\n"
    ".DS_Store\n"
    "*.conflict-*\n"
)
SHARED_ROOT_GITATTRIBUTES = (
    "# Append-only files: keep both machines' lines on a git merge instead of conflicting.\n"
    "MEMORY.md merge=union\n"
    "GLOBAL-MEMORY.md merge=union\n"
    "*HISTORY*.md merge=union\n"
    "*.jsonl merge=union\n"
)


def get_shared_memory_root():
    """The user-configured shared memory root, or None when it isn't configured.

    Unset, empty, or an unsubstituted `${user_config.shared_memory_root}` placeholder all mean
    "not configured" -- callers then fall back to ${CLAUDE_PLUGIN_DATA}. A configured value must
    be absolute after `~`/`$VAR` expansion; a relative one raises PluginDataDirUnavailable rather
    than being resolved against whatever cwd the hook happens to run in.
    """
    raw = (os.environ.get(SHARED_MEMORY_ROOT_ENV) or "").strip()
    if not raw or raw.startswith("${user_config."):
        return None
    root = os.path.expanduser(os.path.expandvars(raw))
    if not os.path.isabs(root):
        raise PluginDataDirUnavailable(
            f"{SHARED_MEMORY_ROOT_ENV}={raw!r} is not an absolute path. Set the plugin's "
            f"shared_memory_root option to an absolute directory, or clear it to use "
            f"${{CLAUDE_PLUGIN_DATA}}."
        )
    return os.path.normpath(root)


def get_memory_root(plugin_name: str) -> str:
    """Directory that holds this plugin's syncable memory subdir (e.g. agent-nelly-memory/).

    The shared memory root when configured -- the same directory for every plugin identity and
    every machine that points at it -- otherwise ${CLAUDE_PLUGIN_DATA} (raises
    PluginDataDirUnavailable when that is unset too). Subdir names are the same in both places,
    so scripts/merge_plugin_data.py can fold an existing data dir into a shared root as-is.
    """
    return get_shared_memory_root() or get_plugin_data_dir(plugin_name)


def ensure_shared_root_scaffold(root: str) -> None:
    """Create `root` plus its .gitignore/.gitattributes if missing. Never overwrites either."""
    os.makedirs(root, exist_ok=True)
    for name, content in ((".gitignore", SHARED_ROOT_GITIGNORE),
                          (".gitattributes", SHARED_ROOT_GITATTRIBUTES)):
        path = os.path.join(root, name)
        if not os.path.exists(path):
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(content)

# --- end shared memory root ---
