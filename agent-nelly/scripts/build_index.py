#!/usr/bin/env python3
"""Builds/updates nelly-index.json -- a compact pre-index of a memory store's
entries, so nelly-orchestrator can match relevance from one JSON read instead
of opening every entries/*.md file.

Two store shapes this script indexes, each getting its own nelly-index.json
alongside the store's own content:
  - Per-project: <memory_dir>/entries/*.md -> <memory_dir>/nelly-index.json
  - Global tier: global/GLOBAL-MEMORY.md's inline frontmatter blocks ->
    global/nelly-index.json (single file, not one file per entry).

Each record is intentionally minimal -- no full body content, description
trimmed to its first line:
  {"slug": <name>, "type": <metadata.type|null>,
   "confidence": <metadata.confidence|null>, "description": <str>,
   "tags": [...], "file_path": <path relative to the store dir>,
   "mtime": <float epoch seconds of the source file>,
   "seen_count": <metadata.seen_count|null>}

`seen_count` tracks how many times an auto-extract hook
(hooks/nelly_auto_extract.py, hooks/nelly_commit_extract.py) has written or
re-triggered the same slug -- surfaced here so nelly-orchestrator can see how
close an `inferred` entry is to auto-promotion without opening the entry
file. `null` for entries that don't carry the field (hand-authored entries,
entries predating this field).

Frontmatter is parsed with the same lightweight regex approach already used
throughout hooks/ (nelly_proactive_surface.py, nelly_session_start.py) --
this plugin has no YAML dependency and entry frontmatter is a small, fixed
shape, so a full YAML parser would be pure overhead.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "hooks"))
from nelly_memory import BASE, memory_dir, global_dir  # noqa: E402

INDEX_FILENAME = "nelly-index.json"

_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---", re.S)
_NAME_RE = re.compile(r"^name:\s*(.+)$", re.M)
_DESCRIPTION_RE = re.compile(r"^description:\s*(.+)$", re.M)
_TYPE_RE = re.compile(r"^\s*type:\s*(\S+)", re.M)
_CONFIDENCE_RE = re.compile(r"^\s*confidence:\s*(\S+)", re.M)
_TAGS_RE = re.compile(r"^\s*tags:\s*\[(.*?)\]\s*$", re.M)
_SEEN_COUNT_RE = re.compile(r"^\s*seen_count:\s*(\d+)", re.M)


def _parse_frontmatter_block(block):
    """Parse one `---\\n...\\n---` frontmatter block into an index record's
    fields (minus file_path/mtime, which the caller fills in). Returns None
    when the block has no `name` field -- a record with no slug can't be
    indexed.
    """
    name_m = _NAME_RE.search(block)
    if not name_m:
        return None
    desc_m = _DESCRIPTION_RE.search(block)
    type_m = _TYPE_RE.search(block)
    confidence_m = _CONFIDENCE_RE.search(block)
    tags_m = _TAGS_RE.search(block)
    seen_count_m = _SEEN_COUNT_RE.search(block)

    description = desc_m.group(1).strip().splitlines()[0] if desc_m else ""
    tags = []
    if tags_m:
        tags = [t.strip().strip("'\"") for t in tags_m.group(1).split(",") if t.strip()]

    return {
        "slug": name_m.group(1).strip(),
        "type": type_m.group(1).strip() if type_m else None,
        "confidence": confidence_m.group(1).strip() if confidence_m else None,
        "description": description,
        "tags": tags,
        "seen_count": int(seen_count_m.group(1)) if seen_count_m else None,
    }


def _read_index(index_path):
    try:
        with open(index_path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return []


def _write_index(index_path, records):
    records = sorted(records, key=lambda r: r["slug"])
    with open(index_path, "w", encoding="utf-8") as fh:
        json.dump(records, fh, indent=2)
        fh.write("\n")


def _build_index_for_memory_dir(d):
    """Full rescan of one already-resolved memory-store directory `d` (must
    be a `<memory_dir>` path, e.g. `nelly_memory.memory_dir(cwd)`'s return
    value -- never a raw `cwd`). entries/ is always the source of truth (see
    nelly-orchestrator.md's File-move mechanism), so this is the safety net
    that resyncs the index after an archive-move (Bash `mv`) that no
    Write/Edit hook ever observes.
    """
    entries_dir = os.path.join(d, "entries")
    records = []
    if os.path.isdir(entries_dir):
        for name in sorted(os.listdir(entries_dir)):
            if not name.endswith(".md"):
                continue
            entry_path = os.path.join(entries_dir, name)
            record = _record_for_entry_file(entry_path, os.path.join("entries", name))
            if record:
                records.append(record)
    os.makedirs(d, exist_ok=True)
    _write_index(os.path.join(d, INDEX_FILENAME), records)
    return records


def build_project_index(cwd):
    """Public entry point: resolve `cwd` to its canonical memory_dir, then
    fully rescan it. Never call this with an already-resolved memory-dir
    path -- memory_dir() would re-derive a slug from that path's text and
    resolve somewhere else entirely. Use `_build_index_for_memory_dir(d)`
    directly (see `build_all()`) when `d` is already a memory_dir.
    """
    return _build_index_for_memory_dir(memory_dir(cwd))


def _record_for_entry_file(entry_path, relative_path):
    try:
        with open(entry_path, "r", encoding="utf-8") as fh:
            text = fh.read()
        mtime = os.path.getmtime(entry_path)
    except OSError:
        return None
    m = _FRONTMATTER_RE.search(text)
    if not m:
        return None
    record = _parse_frontmatter_block(m.group(1))
    if not record:
        return None
    record["file_path"] = relative_path
    record["mtime"] = mtime
    return record


def upsert_project_entry(cwd, entry_path):
    """Lightweight update: re-parse exactly one entries/<name>.md file and
    upsert its record into nelly-index.json, without rescanning the whole
    entries/ directory. Used by the PostToolUse hook on a Write/Edit to a
    single entry file -- the common case, and the one worth keeping cheap.

    If entry_path no longer exists (or no longer parses), its record is
    dropped from the index -- this keeps a deleted/malformed entry from
    lingering as a stale index record.

    `cwd` here is a real project cwd (e.g. a hook payload's `cwd`), never an
    already-resolved memory_dir -- same rule as build_project_index() above.
    """
    d = memory_dir(cwd)
    index_path = os.path.join(d, INDEX_FILENAME)
    records = _read_index(index_path)

    name = os.path.basename(entry_path)
    slug = name[:-3] if name.endswith(".md") else name
    records = [r for r in records if r.get("slug") != slug]

    record = _record_for_entry_file(entry_path, os.path.join("entries", name))
    if record:
        records.append(record)

    os.makedirs(d, exist_ok=True)
    _write_index(index_path, records)
    return records


def build_global_index():
    """Full rescan of global/GLOBAL-MEMORY.md's inline frontmatter blocks.
    Unlike a per-project store, the global tier has no per-entry files to
    upsert individually -- every entry lives inside this one file, so a
    "full rebuild" here is already the cheap, minimal operation (one file
    read), not a scan across many files.
    """
    d = global_dir()
    source_path = os.path.join(d, "GLOBAL-MEMORY.md")
    records = []
    try:
        with open(source_path, "r", encoding="utf-8") as fh:
            text = fh.read()
        mtime = os.path.getmtime(source_path)
    except OSError:
        text, mtime = "", None

    for block in re.findall(r"^---\n(.*?)\n---", text, re.M | re.S):
        record = _parse_frontmatter_block(block)
        if not record:
            continue
        record["file_path"] = "GLOBAL-MEMORY.md"
        record["mtime"] = mtime
        records.append(record)

    _write_index(os.path.join(d, INDEX_FILENAME), records)
    return records


def iter_project_dirs():
    if not os.path.isdir(BASE):
        return
    for name in sorted(os.listdir(BASE)):
        if name == "global" or name.startswith("."):
            continue
        path = os.path.join(BASE, name)
        if os.path.isdir(path):
            yield path


def build_all():
    for project_dir in iter_project_dirs():
        # project_dir is already a resolved memory_dir (its own name is the
        # slug) -- rescan it directly rather than routing back through
        # memory_dir(), which would try to re-derive a slug from this path's
        # text and resolve somewhere else entirely.
        _build_index_for_memory_dir(project_dir)
    build_global_index()


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)

    if "--project" in argv:
        idx = argv.index("--project")
        cwd = argv[idx + 1] if idx + 1 < len(argv) else os.getcwd()
        records = build_project_index(cwd)
        print(os.path.join(memory_dir(cwd), INDEX_FILENAME), f"({len(records)} entries)")
        return

    if "--upsert-entry-file" in argv:
        idx = argv.index("--upsert-entry-file")
        entry_path = argv[idx + 1]
        cwd_idx = argv.index("--cwd") if "--cwd" in argv else None
        cwd = argv[cwd_idx + 1] if cwd_idx is not None else os.getcwd()
        records = upsert_project_entry(cwd, entry_path)
        print(os.path.join(memory_dir(cwd), INDEX_FILENAME), f"({len(records)} entries)")
        return

    if "--global" in argv:
        records = build_global_index()
        print(os.path.join(global_dir(), INDEX_FILENAME), f"({len(records)} entries)")
        return

    if "--all" in argv:
        build_all()
        return

    build_all()


if __name__ == "__main__":
    main()
