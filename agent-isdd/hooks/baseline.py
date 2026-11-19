#!/usr/bin/env python3
"""baseline hook (release-2 contract stub). No active workflow or no decision: exit 0, no output
(fail open). Later slices fill in `evaluate`."""
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import sdd_state  # noqa: E402


EMPTY = {"branch_changed": [], "head_moved": [], "files_changed": []}
BUDGET = 3.0  # total seconds across all git calls in one record/diff


def empty():
    return {k: [] for k in EMPTY}


def _git(cwd, deadline, *args):
    """Run git within the shared deadline; stdout text, or None on any failure (fail open)."""
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        return None
    try:
        r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True,
                           timeout=remaining)
    except (OSError, subprocess.SubprocessError, ValueError):
        return None
    return r.stdout if r.returncode == 0 else None


def _snapshot(cwd, deadline):
    """(branch, head, {dirty_path: blob_hash|None}) or None if any git call fails."""
    head = _git(cwd, deadline, "rev-parse", "HEAD")
    branch = _git(cwd, deadline, "rev-parse", "--abbrev-ref", "HEAD")
    status = _git(cwd, deadline, "status", "--porcelain", "-z", "--untracked-files=normal")
    if head is None or branch is None or status is None:
        return None
    paths = []
    entries = status.split("\0")
    i = 0
    while i < len(entries):
        e = entries[i]
        i += 1
        if len(e) <= 3:
            continue
        paths.append(e[3:])
        if e[0] in "RC" or e[1] in "RC":  # the source path follows; keep both
            if i < len(entries) and entries[i]:
                paths.append(entries[i])
            i += 1
    dirty = {}
    for path in sorted(set(paths)):
        if os.path.isfile(os.path.join(cwd, path)):
            h = _git(cwd, deadline, "hash-object", "--", path)
            if h is None:
                return None
            dirty[path] = h.strip()
        else:
            dirty[path] = None
    return branch.strip(), head.strip(), dirty


def record(cwd, state_json):
    """Record branch/head/dirty files (with per-file blob hashes) into workflow-state.json.
    Fails open."""
    try:
        snap = _snapshot(cwd, time.monotonic() + BUDGET)
        if snap is None:
            return None
        branch, head, dirty = snap
        sdd_state.write_baseline(state_json, branch, head, sorted(dirty))

        def add_hashes(d):
            b = dict(d.get("baseline") or {})
            b["dirty_hashes"] = dirty
            return dict(d, baseline=b)

        sdd_state.update_json(state_json, add_hashes)
    except Exception:
        pass
    return None


def diff(cwd, state_json):
    """Changes since the recorded baseline: branch_changed [old, new], head_moved [old, new],
    files_changed (committed since baseline head, newly dirty, or pre-dirty files whose content
    changed or that are clean now). "incomplete": True when the committed range could not be
    diffed. Fails open to empty."""
    try:
        base = sdd_state.read_baseline(state_json)
        if not base:
            return empty()
        deadline = time.monotonic() + BUDGET
        snap = _snapshot(cwd, deadline)
        if snap is None:
            return empty()
        out = empty()
        branch, head, dirty = snap
        if base.get("branch") != branch:
            out["branch_changed"] = [base.get("branch"), branch]
        old_dirty = base.get("dirty_files") or []
        old_hashes = base.get("dirty_hashes") or {}
        files = set(dirty) - set(old_dirty)
        for p in old_dirty:
            if p not in dirty or (p in old_hashes and old_hashes[p] != dirty[p]):
                files.add(p)
        old_head = base.get("head")
        if old_head and old_head != head:
            out["head_moved"] = [old_head, head]
            committed = _git(cwd, deadline, "diff", "--name-only", "--no-renames", old_head, head)
            if committed is None:
                out["incomplete"] = True
            else:
                files |= {ln for ln in committed.splitlines() if ln.strip()}
        out["files_changed"] = sorted(files)
        return out
    except Exception:
        return empty()


def evaluate(payload):
    """Hook entry. Stub: no-op, returns None."""
    return None


def main():
    try:
        payload = json.load(sys.stdin)
    except (ValueError, OSError):
        payload = {}
    try:
        evaluate(payload if isinstance(payload, dict) else {})
    except Exception:
        pass
    sys.exit(0)


if __name__ == "__main__":
    main()
