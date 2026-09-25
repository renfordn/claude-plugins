"""Shared project slug utility for consolidating duplicated logic across plugins.

The project_slug() function is copy-pasted in:
- agent-nelly/hooks/nelly_memory.py
- agent-isdd/hooks/sdd_memory.py
- agent-tdd/hooks/tdd_state.py

This module consolidates the canonical implementation.
"""

import os
import re
import subprocess
from typing import Optional


def _repo_root(cwd):
    """The git toplevel containing cwd, or cwd itself outside a repo (or if git is missing).

    git reports the toplevel as a realpath, so prefer the lexical ancestor of cwd that resolves
    to it: that keeps cwd's spelling (e.g. /tmp vs /private/tmp on macOS) and so the slug. When
    cwd was reached through a symlink from outside the repo, no ancestor matches and git's
    toplevel is used. A linked worktree is its own toplevel, so it keeps its own slug.
    """
    absp = os.path.abspath(cwd)
    env = {k: v for k, v in os.environ.items() if k not in ("GIT_DIR", "GIT_WORK_TREE")}
    try:
        proc = subprocess.run(["git", "-C", absp, "rev-parse", "--show-toplevel"],
                              capture_output=True, text=True, timeout=5, env=env)
    except (OSError, subprocess.SubprocessError):
        return absp
    top = proc.stdout.strip()
    if proc.returncode != 0 or not top:
        return absp
    real_top = os.path.realpath(top)
    d = absp
    while True:
        if os.path.realpath(d) == real_top:
            return d
        parent = os.path.dirname(d)
        if parent == d:
            return top
        d = parent


def get_project_slug(cwd: Optional[str] = None) -> str:
    """Deterministic collision-resistant slug from the project path: the git toplevel of cwd,
    so a session whose cwd drifts into a repo subdirectory still maps to the repo's store.

    Args:
        cwd: Working directory (default: current working directory)

    Returns:
        A slug derived from the repo root (or cwd outside a repo) by replacing non-alphanumeric
        characters with hyphens, lowercased.

    Examples:
        /srv/code/plugins/agent-nelly → srv-code-plugins-agent-nelly
        /tmp/project → tmp-project
    """
    if cwd is None:
        cwd = os.getcwd()

    absp = _repo_root(cwd)
    slug = re.sub(r"[^A-Za-z0-9]+", "-", absp).strip("-").lower()
    return slug or "root"
