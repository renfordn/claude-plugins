#!/usr/bin/env python3
"""Shared helper: fingerprint the currently staged diff of this plugin's own
skills/agents/commands/hooks directories, plus INTEROP.md wherever it lives.

Used by commit_audit_gate.py to decide whether doc-consistency-auditor has
already run against exactly what's about to be committed, and by the auditor
skill itself to record what it audited. Deliberately narrow: only the paths
this plugin's own responsibility-consistency (and, now, cross-plugin interop
drift) concerns cover, not the whole repo -- an unrelated staged change
(README, CHANGELOG, spec/) should never force a re-audit.

This module implements diff fingerprinting for the doc-consistency-auditor's own
project-level marker (DOC-AUDIT-STATE.md) specifically -- not a generic,
plugin-wide diff-fingerprint utility. `workflow-state.json` carries no
diff-fingerprint field of its own; that concept belonged to the now-external
`code-reviewer` plugin's REVIEW-STATE.md tracking, which this plugin does not
own.
"""
import glob
import hashlib
import os
import subprocess

TRACKED_DIRS = ("skills/", "agents/", "commands/", "hooks/")


def _interop_paths(repo_root):
    """INTEROP.md path(s) relevant to a re-audit trigger, relative to repo_root.

    Two shapes, detected by what's actually on disk (never hardcoded, so a
    new plugin's INTEROP.md is picked up without touching this file):
      - Single-plugin repo (this plugin checked out standalone): just its
        own root `INTEROP.md`, if present.
      - Monorepo (this plugin as one sibling among several, e.g.
        `agent-tdd/INTEROP.md`, `code-reviewer/INTEROP.md`): every
        `*/INTEROP.md` one level down, since class-5 cross-plugin drift
        findings depend on all of them together, not just this plugin's own.
    Both can apply at once (e.g. auditing from the monorepo root while this
    plugin also has its own INTEROP.md) -- paths are deduped by the caller
    via git's own diff, so listing both here is harmless.
    """
    paths = []
    if os.path.isfile(os.path.join(repo_root, "INTEROP.md")):
        paths.append("INTEROP.md")
    for hit in glob.glob(os.path.join(repo_root, "*/INTEROP.md")):
        paths.append(os.path.relpath(hit, repo_root))
    return paths


def _tracked_dir_paths(repo_root):
    """TRACKED_DIRS path(s) relevant to a re-audit trigger, relative to repo_root.

    **Corrected 2026-09-24**: this used to be just `TRACKED_DIRS` itself, passed straight
    to `git diff --cached --`, which only ever matched when `repo_root` IS a single
    plugin's own directory (`skills/` existing directly under it). `commit_audit_gate.py`'s
    own `_looks_like_this_plugin` explicitly supports running from the monorepo root too
    (this repo, when >= 2 sibling plugin dirs carry INTEROP.md) -- but in that mode, none of
    `skills/`, `agents/`, `commands/`, `hooks/` exist at `repo_root` itself, so every staged
    change under e.g. `agent-isdd/skills/workflow-manager/SKILL.md` was silently invisible to
    `compute()`, `current_fp` came back `None`, and the gate's `if current_fp is None: allow(...)`
    branch let the commit through with NO audit enforcement at all. Mirrors `_interop_paths`'s
    already-correct dual-shape handling: the bare dir name for the single-plugin case, plus a
    `*/<dir>/` glob one level down for the monorepo case. Both can apply at once, same as
    `_interop_paths` -- paths are deduped by the caller via git's own diff.
    """
    paths = []
    for d in TRACKED_DIRS:
        if os.path.isdir(os.path.join(repo_root, d)):
            paths.append(d)
        for hit in glob.glob(os.path.join(repo_root, "*", d)):
            paths.append(os.path.relpath(hit, repo_root) + "/")
    return paths


def compute(repo_root):
    """sha256 hex digest of `git diff --cached -- <tracked paths>` in repo_root.

    Tracked paths = `_tracked_dir_paths`'s dual-shape (single-plugin or monorepo)
    resolution of TRACKED_DIRS plus whatever INTEROP.md file(s) `_interop_paths` finds --
    both computed fresh per call so a plugin added or removed since the last run is
    reflected immediately.

    Returns None -- never a fabricated/empty-string hash -- when: repo_root
    isn't a git repo, git itself errors, or nothing is staged under the
    tracked paths. Callers must treat None as "cannot verify", not as a
    value that could ever equal a real fingerprint.
    """
    tracked = _tracked_dir_paths(repo_root) + _interop_paths(repo_root)

    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--"] + tracked,
            cwd=repo_root,
            capture_output=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None

    if result.returncode != 0:
        return None

    diff_bytes = result.stdout
    if not diff_bytes.strip():
        return None

    return hashlib.sha256(diff_bytes).hexdigest()
