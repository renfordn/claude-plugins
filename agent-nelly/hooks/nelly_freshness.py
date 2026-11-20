#!/usr/bin/env python3
"""SessionStart helper: mark entries whose sources changed as stale, never delete (R17).

Conservative: only entries that carry `sources` and are not already stale are checked, oldest
`verified` first, resuming after a rotation cursor (freshness-cursor.json in the machine-local
state dir) so a time budget never starves the later entries. A changed or missing source file
(or any hash error) is a stale path. Marking only adds `stale`, `stale_since`, `stale_paths`
inside `metadata:` and refreshes that entry's index record; nothing is deleted or moved, and
only `nelly_evidence.py refresh` clears the flag. Any per-entry error, including StoreLocked,
skips that entry (fail open). Contract: INTEROP.md "Source evidence, staleness, capture and
safe writes"."""
import json
import os
import re
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))

import build_index  # noqa: E402
import nelly_store  # noqa: E402
from nelly_memory import local_state_dir, memory_dir  # noqa: E402
from research_digest import blob_hash_file  # noqa: E402

CURSOR_FILE = "freshness-cursor.json"
NAMED_CAP = 5
_STALE_KEYS = ("stale", "stale_since", "stale_paths")


def _repo_root(cwd):
    try:
        proc = subprocess.run(["git", "-C", cwd, "rev-parse", "--show-toplevel"],
                              capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return None
    root = proc.stdout.strip()
    return root if proc.returncode == 0 and root else None


def _load_cursor(path):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            cur = json.load(fh)
        return [str(cur.get("verified") or ""), str(cur.get("slug") or "")]
    except (OSError, ValueError, AttributeError):
        return None


def _save_cursor(path, key):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        nelly_store.atomic_write(path, json.dumps(
            {"verified": key[0], "slug": key[1]} if key else {}) + "\n")
    except OSError:
        pass


def _key(record):
    return [str(record.get("verified") or ""), str(record.get("slug") or "")]


def _stale_paths(repo_root, sources, hashes):
    stale = []
    for src in sources:
        rel = src.get("path")
        if not rel:
            continue
        try:
            if rel not in hashes:
                hashes[rel] = blob_hash_file(os.path.join(repo_root, *rel.split("/")))
            current = hashes[rel]
            if not src.get("hash") or current is None or current != src["hash"]:
                stale.append(rel)
        except Exception:
            stale.append(rel)
    return stale


_META_RE = re.compile(r"^metadata:[ \t]*(#.*)?\r?$")
_PLAIN_RE = re.compile(r"[A-Za-z0-9_./@+=~-]+")


def _q(value):
    """Plain scalar when safe, else double-quoted (escaping backslash and quote) so build_index's
    inline-list parser round-trips it."""
    if _PLAIN_RE.fullmatch(value):
        return value
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _indent(line):
    return len(line) - len(line.lstrip())


def _mark_text(text, paths, today):
    """Add stale keys after the last line of the `metadata:` block. Pre-existing stale keys
    (whole extent, incl. block-list items) are replaced; every other line stays identical.
    Returns None when there is no frontmatter `metadata:` block."""
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return None
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        return None
    meta = next((i for i in range(1, end) if _META_RE.match(lines[i].rstrip("\n"))), None)
    if meta is None:
        return None
    last = meta
    for i in range(meta + 1, end):
        if lines[i].strip() and not lines[i][0].isspace():
            break
        if lines[i].strip():
            last = i
    first = next((i for i in range(meta + 1, last + 1) if lines[i].strip()), None)
    indent = lines[first][:_indent(lines[first])] if first is not None else "  "
    ci = len(indent)

    removed = set()
    i = meta + 1
    while i <= last:
        line = lines[i]
        key, _, rest = line.strip().partition(":")
        if line.strip() and _indent(line) == ci and key in _STALE_KEYS:
            removed.add(i)
            j = i + 1
            while j <= last and lines[j].strip() and (
                    _indent(lines[j]) > ci
                    or (_indent(lines[j]) == ci and lines[j].strip().startswith("-") and not rest.strip())):
                removed.add(j)
                j += 1
            i = j
        else:
            i += 1
    kept_last = max(k for k in range(meta, last + 1)
                    if k not in removed and (k == meta or lines[k].strip()))
    nl = "\r\n" if lines[meta].endswith("\r\n") else "\n"
    if not lines[kept_last].endswith("\n"):
        lines[kept_last] += nl
    new = [f"{indent}stale: true{nl}", f"{indent}stale_since: {today}{nl}",
           f"{indent}stale_paths: [{', '.join(_q(p) for p in paths)}]{nl}"]
    out = []
    for k, line in enumerate(lines):
        if k not in removed:
            out.append(line)
        if k == kept_last:
            out.extend(new)
    return "".join(out)


def _mark_stale(cwd, mem, record, paths, today, timeout):
    """Mark one entry under the store lock (bounded wait). Returns update_entry's status."""
    path = os.path.join(mem, record["file_path"])
    with nelly_store.lock(mem, timeout=timeout):
        status = nelly_store.update_entry(
            mem, path, lambda old: _mark_text(old, paths, today) if old else None)
        if status == "written":
            build_index.upsert_project_entry(cwd, path)
    return status


def scan(cwd, budget=1.5):
    """Return SessionStart lines about entries newly marked stale (and the stale total)."""
    start = time.monotonic()
    try:
        repo_root = _repo_root(cwd)
        if not repo_root:
            return []
        mem = memory_dir(cwd)
        records = [r for r in build_index._read_index(os.path.join(mem, build_index.INDEX_FILENAME))
                   if isinstance(r, dict) and r.get("slug") and r.get("file_path")]
    except Exception:
        return []

    already_stale = sum(1 for r in records if r.get("sources") and r.get("stale") is True
                        and r.get("type") != "research-digest")
    candidates = sorted((r for r in records if r.get("sources") and r.get("stale") is not True
                                  and r.get("type") != "research-digest"),
                        key=_key)
    cursor_path = os.path.join(local_state_dir(cwd), CURSOR_FILE)
    cursor = _load_cursor(cursor_path)
    if cursor is not None:
        after = [r for r in candidates if _key(r) > cursor]
        candidates = after if after else candidates  # past the end -> wrap to the oldest

    today = time.strftime("%Y-%m-%d")
    hashes = {}
    marked = []
    last_key = None
    finished = True
    for record in candidates:
        if time.monotonic() - start >= budget:
            finished = False
            break
        last_key = _key(record)
        try:
            paths = _stale_paths(repo_root, record["sources"], hashes)
            if paths:
                wait = max(0.05, budget - (time.monotonic() - start))
                if _mark_stale(cwd, mem, record, paths, today, wait) == "written":
                    marked.append((record["slug"], paths))
        except Exception:  # StoreLocked included: skip this entry, fail open
            continue
    if finished:
        _save_cursor(cursor_path, None)  # full pass done: next scan starts from the oldest
    elif last_key:
        _save_cursor(cursor_path, last_key)

    lines = []
    if marked:
        named = [f"{slug} ({', '.join(paths)})" for slug, paths in marked[:NAMED_CAP]]
        if len(marked) > NAMED_CAP:
            named.append(f"+{len(marked) - NAMED_CAP} more")
        lines.append(f"{len(marked)} memory entries marked stale (sources changed): "
                     f"{', '.join(named)}. Recheck the source, then run "
                     f"scripts/nelly_evidence.py refresh <slug> --paths ...")
    total = already_stale + len(marked)
    if total > 0:
        lines.append(f"{total} memory entries are stale in total.")
    return lines


def main():
    try:
        json.load(sys.stdin)
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
