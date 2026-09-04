#!/usr/bin/env python3
"""Per-feature spec-artifact scaffolding for the SDD plugin.

Per-feature spec artifacts (workflow-state.md, workflow-state.json, requirements/, design/,
tasks/, recap/) live under ~/.claude/sdd-memory/<project-slug>/spec/<feature-slug>/ — see
spec_dir() below. They are plugin-generated state, not source, so they never live in the repo
itself; see references/artifact-templates.md and skills/workflow-manager/SKILL.md's
"Scaffolding" section.

Cross-feature, goal-bearing, and cross-project memory (what used to live in
PROJECT-MEMORY.md, TDD-MEMORY.md, scholar-memory.md, GLOBAL-MEMORY.md,
GLOBAL-PROMOTION-LOG.md, all owned by the now-removed memory-orchestrator agent) is no
longer this module's concern — that responsibility moved to the agent-nelly plugin's
`nelly-orchestrator` subagent. This module only ever scaffolds per-feature state.

Importable API: memory_dir, spec_dir, ensure_dir.
CLI:
  --path [CWD]      print (creating if needed) the memory dir for a project
  --spec-path SLUG [CWD]  print (creating if needed) spec/<SLUG>/ under the memory dir

Note: this module never reads or writes MEMORY.md (or PROJECT-MEMORY.md/TDD-MEMORY.md/
scholar-memory.md/GLOBAL-MEMORY.md) -- per requirements.md's Ubiquitous rule, sdd shall
never touch those files again; agent-nelly owns that tier now. ensure_dir()/--path only
ever creates the bare directory.
"""
import os
import re
import sys

BASE = os.path.join(os.path.expanduser("~"), ".claude", "sdd-memory")


def project_slug(cwd):
    """Deterministic collision-resistant slug from an absolute project path."""
    absp = os.path.abspath(cwd)
    slug = re.sub(r"[^A-Za-z0-9]+", "-", absp).strip("-").lower()
    return slug or "root"


def memory_dir(cwd):
    return os.path.join(BASE, project_slug(cwd))


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
