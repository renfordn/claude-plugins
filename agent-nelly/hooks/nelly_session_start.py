#!/usr/bin/env python3
"""SessionStart hook: announce Agent Nelly's independent memory root for this
project and surface a condensed view of what's already stored there.

Scope is deliberately narrow — memory only. This hook does NOT scan for or
surface workflow/session-lifecycle state (no interruption-note/snapshot
handling, no active-workflow surfacing); that is SDD-specific behavior owned
by spec-driven-development's own session_start.py, not this plugin.

Entries are surfaced via a compact, token-bounded brief built purely from
nelly-index.json (scripts/build_index.py's pre-index) -- no entry-file
re-reads, no LLM call. Explicit-confidence error-prevention entries sort
first (highest signal), then the rest by recency, capped at 5. Falls back to
a plain slug listing only when the index hasn't been built yet.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from nelly_memory import memory_dir, read_index, read_global_index, list_entries  # noqa: E402

INDEX_FILENAME = "nelly-index.json"
HOTSPOTS_FILENAME = "hotspots.json"
_BRIEF_CAP = 5
_DESC_TRUNCATE = 60
_HOTSPOTS_CAP = 3
_HOTSPOTS_MIN_COUNT = 1


def _read_intent(cwd):
    """Return the project's `Intent:` line from MEMORY.md verbatim, or an
    explicit not-yet-captured placeholder. Never invents an Intent — nothing
    in this plugin writes one yet (known, non-blocking gap).
    """
    idx = read_index(cwd)
    m = re.search(r"^Intent:.*$", idx, re.M)
    if m:
        return m.group(0).strip()
    return "Intent: not yet captured"


def _read_global_memory():
    """Condensed (name + description only) index of GLOBAL-MEMORY.md's entries.

    Deliberately never includes full entry bodies -- the global tier can grow
    across many projects over time, and session-start context must stay
    token-bounded regardless of how large it gets. Returns "" when there are
    no real entries yet (silent-when-empty, matches this hook's additive-only
    convention).
    """
    idx = read_global_index()
    if not idx:
        return ""
    lines = []
    for block in re.findall(r"^---\n(.*?)\n---", idx, re.M | re.S):
        name_m = re.search(r"^name:\s*(.+)$", block, re.M)
        desc_m = re.search(r"^description:\s*(.+)$", block, re.M)
        if name_m and desc_m:
            lines.append(f"- {name_m.group(1).strip()}: {desc_m.group(1).strip()}")
    return "\n".join(lines)


def _read_project_index(cwd):
    """Read nelly-index.json (built by scripts/build_index.py) for pure,
    zero-LLM-cost record data -- no entry-file re-reads. Missing/malformed
    index (not yet built, or JSON corrupt) -> empty list, treated by the
    caller as "fall back to the plain entries list", never as an error.
    """
    path = os.path.join(memory_dir(cwd), INDEX_FILENAME)
    try:
        with open(path, "r", encoding="utf-8") as fh:
            records = json.load(fh)
    except (OSError, json.JSONDecodeError, ValueError):
        return []
    return records if isinstance(records, list) else []


def _read_hotspots(cwd):
    """Top hotspot files from hotspots.json (written by
    hooks/nelly_hotspot_tracker.py's PostToolUse hook), by descending touch
    count. Only files that still exist on disk are considered -- a deleted
    file is silently skipped rather than surfaced as a stale hotspot. Files
    with count <= _HOTSPOTS_MIN_COUNT are excluded (a single touch isn't a
    "hotspot"). Missing/malformed hotspots.json -> empty list, same
    silent-fallback convention as _read_project_index().
    """
    path = os.path.join(memory_dir(cwd), HOTSPOTS_FILENAME)
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError, ValueError):
        return []
    files = data.get("files") if isinstance(data, dict) else None
    if not isinstance(files, dict):
        return []

    candidates = []
    for rel_path, info in files.items():
        if not isinstance(info, dict):
            continue
        count = info.get("count")
        if not isinstance(count, int) or count <= _HOTSPOTS_MIN_COUNT:
            continue
        abspath = rel_path if os.path.isabs(rel_path) else os.path.join(cwd, rel_path)
        if not os.path.isfile(abspath):
            continue
        candidates.append((rel_path, count))

    candidates.sort(key=lambda item: item[1], reverse=True)
    return candidates[:_HOTSPOTS_CAP]


def _format_hotspots(hotspots):
    if not hotspots:
        return None
    parts = [f"{path} ({count} edits)" for path, count in hotspots]
    return "Hot files: " + ", ".join(parts)


def _format_brief(records):
    """Compact, token-bounded brief from index records alone: entry-type
    counts, then up to _BRIEF_CAP most-relevant entries. Explicit-confidence
    error-prevention entries always sort first (highest-signal, per index
    guidance elsewhere in this plugin -- e.g. nelly_proactive_surface.py),
    then everything else by recency (mtime desc), capped at _BRIEF_CAP total.

    Returns None for an empty record list so the caller can fall back to the
    plain entries listing (e.g. before the index has ever been built).
    """
    if not records:
        return None

    error_prevention = sum(1 for r in records if r.get("type") == "error-prevention")
    technique = sum(1 for r in records if r.get("type") == "technique")

    explicit_ep = [
        r for r in records
        if r.get("type") == "error-prevention" and r.get("confidence") == "explicit"
    ]
    explicit_ep.sort(key=lambda r: r.get("mtime") or 0, reverse=True)
    explicit_slugs = {r.get("slug") for r in explicit_ep}

    rest = [r for r in records if r.get("slug") not in explicit_slugs]
    rest.sort(key=lambda r: r.get("mtime") or 0, reverse=True)

    top = (explicit_ep + rest)[:_BRIEF_CAP]

    lines = [
        f"[nelly] Project memory: {len(records)} entries "
        f"({error_prevention} error-prevention, {technique} technique)"
    ]
    for i, r in enumerate(top):
        desc = (r.get("description") or "")[:_DESC_TRUNCATE]
        entry_line = f"{r.get('slug')} — {desc}"
        lines.append(("Recent: " if i == 0 else "        ") + entry_line)
    lines.append("Run /nelly-memory view for full context.")
    return "\n".join(lines)


def main():
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        payload = {}

    cwd = payload.get("cwd") or os.getcwd()
    lines = []

    # Always tell the session where this project's independent memory lives,
    # so downstream tooling can use the literal absolute path. Reads/writes
    # under this path are auto-approved by hooks/nelly_memory_permission.py.
    mem = memory_dir(cwd)
    lines.append(f"Agent Nelly memory for this project: {mem}")

    lines.append(_read_intent(cwd))

    brief = _format_brief(_read_project_index(cwd))
    if brief:
        lines.append(brief)
    else:
        # Index not built yet (or empty) -- fall back to the plain listing
        # rather than staying silent about entries that do exist.
        entries = list_entries(cwd)
        if entries:
            lines.append(f"Durable entries ({len(entries)}): " + ", ".join(entries))

    hotspots_line = _format_hotspots(_read_hotspots(cwd))
    if hotspots_line:
        lines.append(hotspots_line)

    global_mem = _read_global_memory()
    if global_mem:
        lines.append("")
        lines.append("Global cross-project memory (condensed — see GLOBAL-MEMORY.md for full entries):")
        lines.append(global_mem)

    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "SessionStart",
        "additionalContext": "\n".join(lines),
    }}))
    sys.exit(0)


if __name__ == "__main__":
    main()
