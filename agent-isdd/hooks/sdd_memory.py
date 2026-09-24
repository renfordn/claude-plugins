#!/usr/bin/env python3
"""Per-feature spec-artifact scaffolding for the SDD plugin.

Per-feature spec artifacts (workflow-state.md, workflow-state.json, requirements/, design/,
tasks/, recap/) live under <root>/sdd-memory/<project-slug>/spec/<feature-slug>/ — see
spec_dir() below. <root> is the user's `shared_memory_root` plugin option when set (one store for
every plugin identity and machine pointed at it), else ${CLAUDE_PLUGIN_DATA}. Note: sdd-memory is shared between agent-isdd and plugin-harness via
symlink coordination (Task 3.1). They are plugin-generated state, not source, so they never live
in the repo itself; see references/artifact-templates.md and skills/workflow-manager/SKILL.md's
"Scaffolding" section.

Cross-feature, goal-bearing, and cross-project memory (what used to live in
PROJECT-MEMORY.md, TDD-MEMORY.md, scholar-memory.md, GLOBAL-MEMORY.md,
GLOBAL-PROMOTION-LOG.md, all owned by the now-removed memory-orchestrator agent) is no
longer this module's concern — that responsibility moved to the agent-nelly plugin's
`agent-nelly` subagent. This module only ever scaffolds per-feature state.

Importable API: memory_dir, spec_dir, ensure_dir.
CLI:
  --path [CWD]      print (creating if needed) the memory dir for a project
  --spec-path SLUG [CWD]  print (creating if needed) spec/<SLUG>/ under the memory dir

Note: this module never reads or writes MEMORY.md (or PROJECT-MEMORY.md/TDD-MEMORY.md/
scholar-memory.md/GLOBAL-MEMORY.md) -- per requirements.md's Ubiquitous rule, sdd shall
never touch those files again; agent-nelly owns that tier now. ensure_dir()/--path only
ever creates the bare directory.

Do not run this module's CLI (`python3 hooks/sdd_memory.py --path|--spec-path ...`) by hand
from a plain shell, or via a Bash tool call, during interactive session work -- see
path_resolution.py's "identity-split hazard" docstring. BASE is resolved once at import time
from `${CLAUDE_PLUGIN_DATA}` (and CLAUDE_PLUGIN_OPTION_SHARED_MEMORY_ROOT), which a manual
invocation never has set, so a hand-run scaffold
can silently land under a different plugin identity's data dir than whichever one this
project's real, registered hooks resolve to -- invisible to every other hook in this plugin
until reconciled by hand. Let real hooks (or a skill that only ever calls through them, the way
hooks.json does) scaffold and discover this state.
"""
import json
import os
import re
import sys

# path_resolution.py lives alongside this file (a per-plugin copy -- see its own
# docstring for why it isn't imported from a monorepo-relative shared/ directory).
_this_dir = os.path.dirname(os.path.abspath(__file__))
if _this_dir not in sys.path:
    sys.path.insert(0, _this_dir)
from path_resolution import (  # noqa: E402
    get_plugin_data_dir, get_legacy_subdir_path, get_memory_root, get_shared_memory_root,
    ensure_shared_root_scaffold,
)

# BASE holds the syncable per-feature spec state (spec/<feature>/, DOC-AUDIT-STATE.md, ...): the
# user's shared_memory_root option when set, else ${CLAUDE_PLUGIN_DATA}. LOCAL_BASE is always
# ${CLAUDE_PLUGIN_DATA} and holds machine-local session markers (last-stop.json, snapshots/) --
# see local_state_dir(). The two are the same directory when no shared root is configured.
SHARED_ROOT = get_shared_memory_root()
_plugin_data_dir = get_plugin_data_dir("agent-isdd")
BASE = get_legacy_subdir_path(get_memory_root("agent-isdd"), "sdd-memory")
LOCAL_BASE = get_legacy_subdir_path(_plugin_data_dir, "sdd-memory")

# Written into agent-isdd's own ${CLAUDE_PLUGIN_DATA} so plugin-harness (whose hooks never see
# agent-isdd's userConfig) can follow the same resolved location -- see write_base_pointer().
BASE_POINTER_NAME = "sdd-memory-location.json"


def project_slug(cwd):
    """Deterministic collision-resistant slug from an absolute project path."""
    absp = os.path.abspath(cwd)
    slug = re.sub(r"[^A-Za-z0-9]+", "-", absp).strip("-").lower()
    return slug or "root"


def memory_dir(cwd):
    return os.path.join(BASE, project_slug(cwd))


def local_state_dir(cwd):
    """Machine-local per-project dir for session markers (last-stop.json, snapshots/).

    Always under ${CLAUDE_PLUGIN_DATA}, even when a shared memory root is configured: these
    record what happened in *this* machine's sessions, so syncing them would make one machine's
    Stop look like another's clean resume. Equal to memory_dir(cwd) with no shared root.
    """
    return os.path.join(LOCAL_BASE, project_slug(cwd))


def write_base_pointer():
    """Record the resolved BASE in ${CLAUDE_PLUGIN_DATA}/sdd-memory-location.json.

    plugin-harness reads this (via its sibling-data-dir lookup) so its hooks use the same
    sdd-memory as agent-isdd's, shared root or not. Rewritten only when the value changes.
    """
    path = os.path.join(_plugin_data_dir, BASE_POINTER_NAME)
    record = {"sdd_memory": BASE, "shared_memory_root": SHARED_ROOT}
    try:
        with open(path, "r", encoding="utf-8") as fh:
            if json.load(fh) == record:
                return path
    except (OSError, ValueError):
        pass
    os.makedirs(_plugin_data_dir, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(record, fh)
    os.replace(tmp, path)
    return path


def ensure_shared_root():
    """Scaffold the shared memory root (.gitignore/.gitattributes) when one is configured."""
    if SHARED_ROOT:
        ensure_shared_root_scaffold(SHARED_ROOT)


def spec_dir(cwd, slug=None):
    """spec/ (or spec/<slug>/) under the project's memory dir, creating it if needed.

    Per-feature spec artifacts are plugin-generated state, not source, so they live
    here rather than in the repo — see references/artifact-templates.md.
    """
    d = os.path.join(memory_dir(cwd), "spec")
    if slug:
        if "/" in slug or "\\" in slug or slug in (".", ".."):
            raise ValueError(f"invalid feature slug: {slug!r}")
        d = os.path.join(d, slug)
    os.makedirs(d, exist_ok=True)
    return d


def ensure_dir(cwd):
    d = memory_dir(cwd)
    os.makedirs(d, exist_ok=True)
    return d


def main(argv):
    if not argv:
        print(memory_dir(os.getcwd()))
        return
    cmd = argv[0]
    rest = [a for a in argv[1:] if not a.startswith("--")]
    cwd = rest[0] if rest else os.getcwd()

    if cmd == "--path":
        print(ensure_dir(cwd))
    elif cmd == "--spec-path":
        positional = [a for a in argv[1:] if not a.startswith("--")]
        slug = positional[0] if positional else None
        spec_cwd = positional[1] if len(positional) > 1 else os.getcwd()
        print(spec_dir(spec_cwd, slug))
    else:
        print(memory_dir(cwd))


if __name__ == "__main__":
    main(sys.argv[1:])
