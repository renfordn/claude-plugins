#!/usr/bin/env python3
"""PreToolUse Write|Edit|MultiEdit|NotebookEdit: deny production edits for an open slice until its
confirmed Red, confirmed coverage or a bypass is logged after the slice's start in the same
worktree (R9). The worktree comes from the edited file's directory, not cwd. The evidence log is
tail-read in reverse to the latest start for that worktree; open_slice/unlocked then run on that
tail only. Fails open on any error (silent allow).

Nested repos and submodules are their own worktrees with their own slices: an edit inside one is
judged against that worktree's log, so it is allowed unless a slice is open there (intended)."""
import datetime
import json
import os
import shlex
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_PLUGIN = os.path.dirname(_HERE)
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(_PLUGIN, "scripts"))

import tdd_check  # noqa: E402  (plugin-local scripts/ dir, added above)

CHUNK = 64 * 1024
# Entries are appended with at=now() on one machine, so `at` is effectively non-decreasing in file
# order. The reverse scan relies on that append-time ordering to stop early (see _tail_entries).
STOP_AFTER = datetime.timedelta(hours=5)  # > the 4h staleness window in tdd_check


def _reverse_lines(fh):
    """Yield the file's lines last-to-first, reading backwards in chunks (linear: the partial first
    line of each chunk is carried into the next read instead of re-splitting the whole buffer)."""
    pos = fh.seek(0, os.SEEK_END)
    carry = b""
    while pos > 0:
        lo = max(0, pos - CHUNK)
        fh.seek(lo)
        lines = (fh.read(pos - lo) + carry).split(b"\n")
        pos = lo
        if lo > 0:
            carry = lines[0]
            lines = lines[1:]
        else:
            carry = b""
        for ln in reversed(lines):
            yield ln


def _tail_entries(path, worktree, now=None):
    """Parsed entries from the latest `start` of `worktree` to EOF, read backwards; [] if none.

    Stops early, returning [] (no open start), at the first parsable `at` older than now-5h: any
    earlier start would be stale anyway (4h rule), assuming append-time ordering of `at`.
    """
    now = now or datetime.datetime.now()
    rev = []
    with open(path, "rb") as fh:
        for ln in _reverse_lines(fh):
            if not ln.strip():
                continue
            obj = tdd_check._parse_line(ln)
            if obj is None:
                continue
            rev.append(obj)
            try:
                if now - datetime.datetime.fromisoformat(obj.get("at")) > STOP_AFTER:
                    return []
            except (ValueError, TypeError):
                pass
            if obj.get("phase") == "start" and obj.get("worktree") == worktree:
                rev.reverse()
                return rev
    return []


def _decide(payload):
    import path_kinds

    ti = payload.get("tool_input") or {}
    target = ti.get("file_path") or ti.get("notebook_path")
    if not target or not isinstance(target, str):
        return None
    base = payload.get("cwd") if isinstance(payload.get("cwd"), str) else os.getcwd()
    target = os.path.abspath(os.path.join(base, os.path.expanduser(target)))
    d = os.path.dirname(target)
    while d and not os.path.isdir(d):
        parent = os.path.dirname(d)
        if parent == d:
            return None
        d = parent
    worktree = tdd_check._worktree(d)
    if not worktree:
        return None
    rel = path_kinds.relative_to(target, worktree)
    if rel is None or not rel or path_kinds.kind("/".join(rel)) != "prod":
        return None
    path = tdd_check.evidence_path(d)
    if not path or not os.path.isfile(path):
        return None
    entries = _tail_entries(path, worktree)
    start = tdd_check.open_slice(entries, worktree)
    if start is None or tdd_check.unlocked(entries, worktree):
        return None
    title = start.get("slice") or "<slice title>"
    check = shlex.quote(os.path.join(_PLUGIN, "scripts", "tdd_check.py"))
    pre = "cd %s && python3 %s" % (shlex.quote(worktree), check)
    q = shlex.quote(title)
    ids = "".join(" " + shlex.quote(a) for a in tdd_check.cli_id_args(start))
    if start.get("kind") in tdd_check.COVERAGE_KINDS:
        unlock = ("Run the characterization test, then `<P> coverage --slice %s%s --mutant \"<cmd>\" "
                  "-- <test cmd>` (a confirmed coverage unlocks this slice)." % (q, ids))
    else:
        unlock = "Write the failing test, then `<P> red --slice %s%s -- <test cmd>`." % (q, ids)
    return (
        "Red-first guard: slice \"%s\" is open with no unlock yet, so production edits are blocked. "
        "Prefix <P> = `%s`. %s No testable behavior: `<P> bypass --slice %s%s --reason \"<why>\"`. "
        "If no slice should be open here (e.g. the slice stopped early): `<P> done --slice %s%s`."
        % (title, pre, unlock, q, ids, q, ids))


def main():
    try:
        payload = json.load(sys.stdin)
        if not isinstance(payload, dict):
            return 0
        reason = _decide(payload)
        if reason:
            print(json.dumps({"hookSpecificOutput": {
                "hookEventName": "PreToolUse", "permissionDecision": "deny",
                "permissionDecisionReason": reason}}))
    except Exception as exc:  # fail open
        print("red_first_guard: %s" % exc, file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
