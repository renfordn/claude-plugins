#!/usr/bin/env python3
"""PreToolUse hook: deterministically match a Write/Edit/MultiEdit target
path against MEMORY.md's `paths:` index field and, on a qualifying match,
emit a short `permissionDecisionReason` nudge.

This hook NEVER invokes nelly-orchestrator and makes no Agent-tool call --
it is a pure, self-contained Python script, same as nelly_slug_guard.py and
nelly_memory_permission.py. It only ever *allows with a reason* or stays
silent; it never denies, since a missing/stale memory entry must never block
the underlying Write/Edit (index/entry drift -> no-match, fail silent).

Safety-critical rule: an `error-prevention` entry only surfaces when its
REAL `metadata.confidence` (read from the entry file itself) is `explicit`.
The index line's mirrored `confidence:` field is NOT trusted for this
decision -- it can drift stale relative to the entry file, and trusting it
would risk leaking a lesson that was only `inferred` (noticed unprompted,
not yet confirmed) and is therefore permanently excluded from surfacing.

Tie-break when multiple entries match the same path: emit a reason for the
FIRST match found while scanning MEMORY.md top-to-bottom, then stop (cap at
exactly one nudge per Write/Edit/MultiEdit). This is the simplest correct
choice available without adding a second axis (recency/confidence ranking)
that the index doesn't reliably expose across entry types.

Set env NELLY_GATE=off (or 0/false/disabled, case-insensitive) to disable
entirely.
"""
import hashlib
import json
import os
import re
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from nelly_memory import memory_dir, parse_index_line_fields, resolve_repo_relative  # noqa: E402

_LINE_RE = re.compile(r"^-\s*\[(?P<title>[^\]]+)\]\((?P<link>[^)]+)\)")


def _read_index_cached(cwd):
    """Read MEMORY.md index, caching by mtime in a temp file.
    This hook fires on every Write/Edit/MultiEdit; without a cache, every call
    re-reads MEMORY.md from disk even when nothing has changed. The cache is a
    plain text file under tempdir, keyed by the index path + mtime so it
    automatically invalidates the moment nelly writes a new entry.
    """
    mem = memory_dir(cwd)
    index_path = os.path.join(mem, "MEMORY.md")
    if not os.path.isfile(index_path):
        return ""
    try:
        mtime = os.path.getmtime(index_path)
    except OSError:
        return ""

    cache_key = hashlib.md5(f"{index_path}:{mtime}".encode()).hexdigest()
    cache_path = os.path.join(tempfile.gettempdir(), f"nelly_index_{cache_key}.txt")

    if os.path.isfile(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as fh:
                return fh.read()
        except OSError:
            pass  # cache unreadable -- fall through to direct read

    try:
        with open(index_path, "r", encoding="utf-8") as fh:
            content = fh.read()
    except OSError:
        return ""

    try:
        with open(cache_path, "w", encoding="utf-8") as fh:
            fh.write(content)
    except OSError:
        pass  # cache write failure is non-fatal -- direct read result is still valid

    return content
_DESCRIPTION_RE = re.compile(r"^description:\s*(.+)$", re.M)
_CONFIDENCE_RE = re.compile(r"^\s*confidence:\s*(\S+)", re.M)


def no_decision():
    sys.exit(0)


def emit_allow(reason):
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "allow",
        "permissionDecisionReason": reason,
    }}))
    sys.exit(0)


def _read_entry_file(cwd, link):
    """Open the entry file the index line points to. Returns None on any
    read failure (moved/deleted entry file -> index/entry drift), which
    callers must treat as no-match, never an error.
    """
    path = os.path.join(memory_dir(cwd), link)
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return None


def _description(entry_text):
    m = _DESCRIPTION_RE.search(entry_text)
    return m.group(1).strip() if m else ""


def _real_confidence(entry_text):
    m = _CONFIDENCE_RE.search(entry_text)
    return m.group(1).strip() if m else None


def _path_matches(cwd, paths, target):
    for p in paths:
        try:
            resolved = resolve_repo_relative(cwd, p)
        except ValueError:
            continue
        if resolved == target:
            return True
    return False


def main():
    if os.environ.get("NELLY_GATE", "").lower() in ("off", "0", "false", "disabled"):
        no_decision()

    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        no_decision()

    tool_input = payload.get("tool_input") or {}
    file_path = tool_input.get("file_path") or tool_input.get("path") or ""
    if not file_path:
        no_decision()

    cwd = payload.get("cwd") or os.getcwd()
    abspath = file_path if os.path.isabs(file_path) else os.path.join(cwd, file_path)
    target = os.path.normpath(abspath)

    index = _read_index_cached(cwd)
    if not index:
        no_decision()  # empty/missing memory store -> silent no-op

    for line in index.splitlines():
        fields = parse_index_line_fields(line)
        paths = fields.get("paths")
        if not paths or not _path_matches(cwd, paths, target):
            continue

        m = _LINE_RE.match(line)
        if not m:
            continue  # malformed line -> treat as no-match, never error

        entry_text = _read_entry_file(cwd, m.group("link"))
        if entry_text is None:
            continue  # index/entry drift -> no-match, fail silent

        entry_type = fields.get("type")
        title = m.group("title")
        description = _description(entry_text)

        if entry_type == "error-prevention":
            if _real_confidence(entry_text) != "explicit":
                continue  # inferred (or unknown) confidence -> never surface
            emit_allow(f"{title} — {description} (confidence: explicit)")
        elif entry_type == "file-relevance":
            emit_allow(f"{title} — {description}")
        # Any other/unknown type is out of scope for this slice -> keep
        # scanning rather than surfacing or erroring.

    no_decision()


if __name__ == "__main__":
    main()
