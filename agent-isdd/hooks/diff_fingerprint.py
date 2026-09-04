#!/usr/bin/env python3
"""Shared helper: fingerprint the currently staged diff of this plugin's own
skills/agents/commands/hooks directories.

Used by commit_audit_gate.py to decide whether doc-consistency-auditor has
already run against exactly what's about to be committed, and by the auditor
skill itself to record what it audited. Deliberately narrow: only the four
directories this plugin's own responsibility-consistency concerns cover, not
the whole repo -- an unrelated staged change (README, CHANGELOG, spec/)
should never force a re-audit.

This module implements diff fingerprinting for the doc-consistency-auditor's own
project-level marker (DOC-AUDIT-STATE.md) specifically -- not a generic,
plugin-wide diff-fingerprint utility. `workflow-state.json` carries no
diff-fingerprint field of its own; that concept belonged to the now-external
`code-reviewer` plugin's REVIEW-STATE.md tracking, which this plugin does not
own.
"""
import hashlib
import subprocess

TRACKED_PATHS = ("skills/", "agents/", "commands/", "hooks/")


def compute(repo_root):
    """sha256 hex digest of `git diff --cached -- <TRACKED_PATHS>` in repo_root.

    Returns None -- never a fabricated/empty-string hash -- when: repo_root
    isn't a git repo, git itself errors, or nothing is staged under the
    tracked paths. Callers must treat None as "cannot verify", not as a
    value that could ever equal a real fingerprint.
    """
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--"] + list(TRACKED_PATHS),
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
