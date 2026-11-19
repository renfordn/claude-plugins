#!/usr/bin/env python3
"""user_led_guard: while `Implementation Mode: user`, deny Write/Edit/MultiEdit/NotebookEdit of
non-test files inside the repo (called via pre_write_dispatch). Test paths, the active spec dir and
paths outside the repo are allowed; mode agent / no workflow is a no-op. Bash writes are not
covered. Fails open on any missing data."""
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


_TEST_DIRS = frozenset(("tests", "__tests__"))


def _is_test_path(parts):
    """Heuristic on the path relative to the repo root. Test files: filename test_*, *_test.<ext>,
    *.spec.<ext>, *.test.<ext>; or any file under a top-level `tests/`, `__tests__/` or `spec/`
    directory, or under `tests/`/`__tests__/` directly beneath a top-level package dir
    (pkg/tests/...). A `spec/` dir deeper in the tree (src/spec/app.py) is NOT a test path."""
    if not parts:
        return False
    if len(parts) > 1 and (parts[0] in _TEST_DIRS or parts[0] == "spec"):
        return True
    if len(parts) > 2 and parts[1] in _TEST_DIRS:
        return True
    name = parts[-1]
    stem = name.rsplit(".", 1)[0] if "." in name else name
    return (name.startswith("test_") or stem.endswith("_test")
            or ".spec." in name or ".test." in name)


def _repo_root(cwd):
    try:
        out = subprocess.run(["git", "-C", cwd, "rev-parse", "--show-toplevel"],
                             capture_output=True, text=True, timeout=3)
        top = out.stdout.strip()
        if out.returncode == 0 and top:
            return os.path.realpath(top)
    except (OSError, subprocess.SubprocessError):
        pass
    return os.path.realpath(cwd)


def _same(a, b):
    try:
        return os.path.samestat(os.stat(a), os.stat(b))
    except OSError:
        return os.path.normcase(a) == os.path.normcase(b)


def _relative_to(path, root):
    """Components of `path` below `root`, matched by file identity (so case-variant spellings on
    case-insensitive filesystems still match); None if path is not inside root."""
    parts = []
    cur = path
    while True:
        if _same(cur, root):
            return list(reversed(parts))
        parent = os.path.dirname(cur)
        if parent == cur:
            return None
        parts.append(os.path.basename(cur))
        cur = parent


def evaluate(payload, state_path=None):
    """Return a deny reason (str) for a non-test edit inside the repo while Implementation Mode is
    user, else None. Paths are resolved (symlinks, `..`) first; repo and memory-dir membership is
    decided by file identity (os.path.samestat), not string prefix. Allowed: paths outside the
    repo, test paths (see _is_test_path) and the active spec dir (dirname of state_path). Only the
    Write/Edit/MultiEdit/NotebookEdit tools' file_path/notebook_path are inspected; Bash writes are
    not covered. Fails open (None) on missing data."""
    if not state_path or not isinstance(payload, dict):
        return None
    from sdd_state import parse_state
    mode = parse_state(state_path).get("implementation mode", "").strip().lower()
    if mode != "user":
        return None
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return None
    raw = tool_input.get("file_path") or tool_input.get("notebook_path")
    if not isinstance(raw, str) or not raw:
        return None
    cwd = payload.get("cwd") or os.getcwd()
    path = os.path.realpath(os.path.join(cwd, os.path.expanduser(raw)))
    rel = _relative_to(path, _repo_root(cwd))
    if rel is None:
        return None
    if _relative_to(path, os.path.dirname(os.path.realpath(state_path))) is not None:
        return None
    if _is_test_path(rel):
        return None
    return ("User-led mode: Claude does not edit production files (%s). Ask the user to make this "
            "change, or ask whether to switch to agent-led (they set `Implementation Mode: agent`)."
            % path)


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
