#!/usr/bin/env python3
"""Shared state utilities for the agent-tdd plugin.

Owns:
  - TDD memory directory derivation (${CLAUDE_PLUGIN_DATA}/agent-tdd-state/<project-slug>/)
  - tdd-progress.json read/write (slice tracking)

Intentionally self-contained: slug algorithm is copied verbatim from
agent-isdd/hooks/sdd_memory.py rather than imported, to avoid a cross-plugin
dependency. The two modules must stay in sync if the slug algorithm ever changes.
"""
import json
import os
import re
import subprocess
import sys

# path_resolution.py lives alongside this file (a per-plugin copy -- see its own
# docstring for why it isn't imported from a monorepo-relative shared/ directory).
_this_dir = os.path.dirname(os.path.abspath(__file__))
if _this_dir not in sys.path:
    sys.path.insert(0, _this_dir)
from path_resolution import get_plugin_data_dir, get_legacy_subdir_path

# Resolve BASE directory using ${CLAUDE_PLUGIN_DATA} env var with fallback
_plugin_data_dir = get_plugin_data_dir("agent-tdd")
BASE = get_legacy_subdir_path(_plugin_data_dir, "agent-tdd-state")


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


def project_slug(cwd):
    """Deterministic collision-resistant slug from the project path (git toplevel of cwd).
    Algorithm is identical to agent-isdd/hooks/sdd_memory.py — kept in sync manually.
    """
    absp = _repo_root(cwd)
    slug = re.sub(r"[^A-Za-z0-9]+", "-", absp).strip("-").lower()
    return slug or "root"


def tdd_memory_dir(cwd):
    return os.path.join(BASE, project_slug(cwd))


def read_tdd_progress(cwd):
    """Read tdd-progress.json. Returns {"slices": []} on missing or malformed file."""
    path = os.path.join(tdd_memory_dir(cwd), "tdd-progress.json")
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, dict) or not isinstance(data.get("slices"), list):
            return {"slices": []}
        return data
    except (OSError, json.JSONDecodeError, ValueError):
        return {"slices": []}


def write_tdd_progress(cwd, data):
    """Write tdd-progress.json, creating parent dirs as needed."""
    d = tdd_memory_dir(cwd)
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, "tdd-progress.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
        fh.write("\n")

