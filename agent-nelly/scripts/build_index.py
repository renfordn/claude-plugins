#!/usr/bin/env python3
"""Builds/updates nelly-index.json -- a compact pre-index of a memory store's
entries, so agent-nelly can match relevance from one JSON read instead
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
   "seen_count": <metadata.seen_count|null>,
   "files": [...] (metadata.files, `file-relevance`/`file-summary` only,
   `[]` when absent), "folder": <metadata.folder|null> (`folder-summary`
   only), "git_hash": <metadata.git_hash|null> (`file-summary` only)}
plus, on `research-digest` records only (absent from every other record):
  "topic": <str>, "sources": [{"path", "hash"}, ...] (file order),
  "updated": <str, as written>

`type` is normalized: legacy on-disk spellings `file_summary`/`folder_summary`
are indexed as `file-summary`/`folder-summary` (see _TYPE_ALIASES).

`files`/`folder`/`git_hash` exist so lookup_by_path() below can answer "is
there already a cached summary for this path?" from this one JSON file --
without them, a path-based lookup would have to fall back to opening every
entries/*.md file, defeating the reason this pre-index exists at all.

`seen_count` tracks how many times an auto-extract hook
(hooks/nelly_auto_extract.py, hooks/nelly_commit_extract.py) has written or
re-triggered the same slug -- surfaced here so agent-nelly can see how
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
import nelly_frontmatter  # noqa: E402
import nelly_store  # noqa: E402  (scripts/ is this file's own dir)
from nelly_memory import (  # noqa: E402
    BASE, memory_dir, global_dir, SUMMARY_SUBDIR, DIGEST_SUBDIR, DIGEST_TYPE,
)

INDEX_FILENAME = "nelly-index.json"

_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---", re.S)
_NAME_RE = re.compile(r"^name:\s*(.+)$", re.M)
_DESCRIPTION_RE = re.compile(r"^description:\s*(.+)$", re.M)
_TYPE_RE = re.compile(r"^\s*type:\s*(\S+)", re.M)
_CONFIDENCE_RE = re.compile(r"^\s*confidence:\s*(\S+)", re.M)
_SEEN_COUNT_RE = re.compile(r"^\s*seen_count:\s*(\d+)", re.M)
_FOLDER_RE = re.compile(r"^\s*folder:\s*(\S+)", re.M)
_GIT_HASH_RE = re.compile(r"^\s*git_hash:\s*(\S+)", re.M)
_TOPIC_RE = re.compile(r"^topic:[ \t]*(.+)$", re.M)
_UPDATED_RE = re.compile(r"^updated:[ \t]*(.+)$", re.M)
_SOURCES_KEY_RE = re.compile(r"^([ \t]*)sources:[ \t]*$")
_EVIDENCE_SCALARS = ("revision", "verified", "basis", "unknowns", "stale_since", "stale_digest")
_EVIDENCE_SCALAR_RES = {k: re.compile(r"^[ \t]*" + k + r":[ \t]*(\S.*)$", re.M) for k in _EVIDENCE_SCALARS}
_SOURCES_FLOW_RE = re.compile(r"^[ \t]*sources:[ \t]*\[(.*)\][ \t]*$", re.M)
_STALE_RE = re.compile(r"^[ \t]*stale:[ \t]*(\S+)", re.M)
_SOURCES_PRESENT_RE = re.compile(r"^[ \t]*sources:", re.M)
_LIST_ITEM_RE = re.compile(r"^[ \t]*-(?:[ \t]|$)")
_SOURCE_FIELD_RE = re.compile(r"^[ \t]*(?:-[ \t]*)?(path|hash):[ \t]*(.*?)[ \t]*$")

# iCloud Drive's conflict duplicate of `<name>.md` is `<name> <N>.md` (space + digits).
_CONFLICT_COPY_RE = re.compile(r" \d+\.md$")

# entries/ subdirectories the index descends into (one level, no deeper).
_INDEXED_SUBDIRS = (SUMMARY_SUBDIR, DIGEST_SUBDIR)

# Legacy spellings some older writers used on disk; normalized at index time so
# lookup_by_path()'s exact `file-summary`/`folder-summary` match finds them without
# rewriting the entry files themselves.
_TYPE_ALIASES = {"file_summary": "file-summary", "folder_summary": "folder-summary"}


def is_conflict_copy(name):
    """True for an iCloud conflict copy (`fact 2.md`, `fact 12.md`); False for ordinary names
    that merely contain digits (`v2.md`, `fact-2.md`). Such copies are never indexed or scanned.
    """
    return bool(_CONFLICT_COPY_RE.search(name))


def _scalar(value):
    """Strip whitespace and one pair of matching surrounding quotes from a frontmatter scalar;
    inside double quotes an escaped backslash or quote is unescaped (the inverse of
    nelly_frontmatter.quote)."""
    return nelly_frontmatter.unquote(value)


def _split_inline(text):
    """Split on top-level commas, honoring quotes and {}/[] nesting; returns stripped parts."""
    parts, buf, quote, depth = [], [], None, 0
    escaped = False
    for ch in text:
        if quote:
            buf.append(ch)
            if escaped:
                escaped = False
            elif ch == "\\" and quote == '"':
                escaped = True
            elif ch == quote:
                quote = None
        elif ch in "'\"":
            quote = ch
            buf.append(ch)
        elif ch in "{[":
            depth += 1
            buf.append(ch)
        elif ch in "}]":
            depth -= 1
            buf.append(ch)
        elif ch == "," and depth == 0:
            parts.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    parts.append("".join(buf))
    return [p.strip() for p in parts if p.strip()]


def _inline_list(block, key):
    """Value of list key `key` as [str, ...], or None when the key is absent. Handles the
    flow form `key: [a, "b, c"]` and the block form (`key:` then `- item` lines)."""
    lines = block.splitlines()
    key_re = re.compile(r"^([ \t]*)" + re.escape(key) + r":[ \t]*(.*?)[ \t]*$")
    for i, line in enumerate(lines):
        m = key_re.match(line)
        if not m:
            continue
        rest = m.group(2)
        if rest.startswith("[") and rest.endswith("]"):
            return [_scalar(t) for t in _split_inline(rest[1:-1])]
        if rest:
            return None
        indent = len(m.group(1).expandtabs())
        items = []
        for nxt in lines[i + 1:]:
            if not nxt.strip():
                continue
            nindent = len(nxt) - len(nxt.lstrip())
            if not _LIST_ITEM_RE.match(nxt) or nindent < indent:
                break
            items.append(_scalar(nxt.strip()[1:]))
        return [x for x in items if x]
    return None


def _parse_flow_sources(inner):
    items = []
    for part in _split_inline(inner):
        if part.startswith("{") and part.endswith("}"):
            item = {"path": None, "hash": None}
            for kv in _split_inline(part[1:-1]):
                k, _, v = kv.partition(":")
                if k.strip() in item:
                    item[k.strip()] = _scalar(v) or None
            items.append(item)
    return [i for i in items if i["path"]]


def _parse_sources(block):
    """Parse a research-digest `sources:` list into [{"path", "hash"}, ...] in file order.
    The block runs from the `sources:` line to the next top-level key; blank lines, indented
    lines and `- ` items (zero-indent allowed) belong to it. Every `- ` line starts a new item;
    `path:`/`hash:` may come in either order. Items without a path are dropped; a path with no
    hash gets `hash: None`."""
    flow_m = _SOURCES_FLOW_RE.search(block)
    if flow_m:
        return _parse_flow_sources(flow_m.group(1))
    lines = block.splitlines()
    start = next((i for i, ln in enumerate(lines) if _SOURCES_KEY_RE.match(ln)), None)
    if start is None:
        return []
    key_indent = len(_SOURCES_KEY_RE.match(lines[start]).group(1).expandtabs())
    items = []
    for line in lines[start + 1:]:
        indent = len(line) - len(line.lstrip())
        if line.strip() and indent <= key_indent and not _LIST_ITEM_RE.match(line):
            break  # next sibling key
        if _LIST_ITEM_RE.match(line):
            items.append({"path": None, "hash": None})
        field_m = _SOURCE_FIELD_RE.match(line)
        if field_m:
            if not items:
                items.append({"path": None, "hash": None})
            items[-1][field_m.group(1)] = _scalar(field_m.group(2)) or None
    return [i for i in items if i["path"]]


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
    seen_count_m = _SEEN_COUNT_RE.search(block)
    folder_m = _FOLDER_RE.search(block)
    git_hash_m = _GIT_HASH_RE.search(block)

    description = _scalar(desc_m.group(1).strip().splitlines()[0]) if desc_m else ""
    entry_type = type_m.group(1).strip() if type_m else None
    entry_type = _TYPE_ALIASES.get(entry_type, entry_type)
    tags = _inline_list(block, "tags") or []
    files = _inline_list(block, "files") or []

    record = {
        "slug": _scalar(name_m.group(1)),
        "type": entry_type,
        "confidence": confidence_m.group(1).strip() if confidence_m else None,
        "description": description,
        "tags": tags,
        "seen_count": int(seen_count_m.group(1)) if seen_count_m else None,
        "files": files,
        "folder": folder_m.group(1).strip() if folder_m else None,
        "git_hash": git_hash_m.group(1).strip() if git_hash_m else None,
    }
    if entry_type == DIGEST_TYPE:
        # Digest-only fields; other records stay minimal (see module docstring).
        topic_m = _TOPIC_RE.search(block)
        updated_m = _UPDATED_RE.search(block)
        record["topic"] = _scalar(topic_m.group(1)) if topic_m else None
        record["sources"] = _parse_sources(block)
        record["updated"] = _scalar(updated_m.group(1)) if updated_m else None
    _add_evidence(record, block)
    return record


def _add_evidence(record, block):
    """Add evidence/stale keys to `record`, each only when present in the frontmatter."""
    if "sources" not in record and _SOURCES_PRESENT_RE.search(block):
        record["sources"] = _parse_sources(block)
    symbols = _inline_list(block, "symbols")
    if symbols is not None:
        record["symbols"] = symbols
    for key in ("revision", "verified", "basis", "unknowns"):
        m = _EVIDENCE_SCALAR_RES[key].search(block)
        if m and _scalar(m.group(1)):
            record[key] = _scalar(m.group(1))
    m = _STALE_RE.search(block)
    if m:
        record["stale"] = _scalar(m.group(1)).lower() == "true"
    m = _EVIDENCE_SCALAR_RES["stale_since"].search(block)
    if m and _scalar(m.group(1)):
        record["stale_since"] = _scalar(m.group(1))
    m = _EVIDENCE_SCALAR_RES["stale_digest"].search(block)
    if m and _scalar(m.group(1)):
        record["stale_digest"] = _scalar(m.group(1))
    stale_paths = _inline_list(block, "stale_paths")
    if stale_paths is not None:
        record["stale_paths"] = stale_paths


def parse_evidence(block):
    """Public: the evidence/stale fields of one frontmatter block as a dict (see _add_evidence)."""
    record = {}
    _add_evidence(record, block)
    return record


def is_repo_relative(path):
    """Public: True when `path` is a repo-relative path: not absolute (POSIX, Windows drive or
    backslash), not starting with `~`, and without a `..` segment."""
    p = str(path)
    return not (p.startswith(("/", "~", "\\")) or os.path.isabs(p)
                or re.match(r"^[A-Za-z]:[\\/]", p) is not None
                or ".." in re.split(r"[\\/]+", p))


def _is_store_artifact(path, d):
    """conflicts/ sidecars and the .nelly.lock file are never index records."""
    rel = os.path.relpath(path, d)
    return os.path.basename(path) == ".nelly.lock" or "conflicts" in rel.split(os.sep)[:-1]


def _read_index(index_path):
    try:
        with open(index_path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return []


def _write_index(index_path, records):
    nelly_store.atomic_write(index_path, nelly_store.serialize_index(records))


def _build_index_for_memory_dir(d):
    """Full rescan of one already-resolved memory-store directory `d` (must
    be a `<memory_dir>` path, e.g. `nelly_memory.memory_dir(cwd)`'s return
    value -- never a raw `cwd`). entries/ is always the source of truth (see
    agent-nelly.md's File-move mechanism), so this is the safety net
    that resyncs the index after an archive-move (Bash `mv`) that no
    Write/Edit hook ever observes.

    Also descends one level into entries/<SUMMARY_SUBDIR>/ and entries/<DIGEST_SUBDIR>/ --
    file-summary/folder-summary and research-digest entries live there instead of directly
    under entries/ (see nelly_memory.SUMMARY_SUBDIR/DIGEST_SUBDIR) -- but no deeper than that: any other subdirectory under entries/ is not a recognized entry
    kind and is skipped, same as a non-.md file at the top level.
    """
    with nelly_store.lock(d):
        return _scan_and_write(d)


def _scan_and_write(d):
    entries_dir = os.path.join(d, "entries")
    records = []
    if os.path.isdir(entries_dir):
        for name in sorted(os.listdir(entries_dir)):
            full = os.path.join(entries_dir, name)
            if os.path.isdir(full):
                if name not in _INDEXED_SUBDIRS:
                    continue
                for sub_name in sorted(os.listdir(full)):
                    if not sub_name.endswith(".md") or is_conflict_copy(sub_name):
                        continue
                    record = _record_for_entry_file(
                        os.path.join(full, sub_name), os.path.join("entries", name, sub_name)
                    )
                    if record:
                        records.append(record)
                continue
            if not name.endswith(".md") or is_conflict_copy(name):
                continue
            record = _record_for_entry_file(full, os.path.join("entries", name))
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
    return upsert_project_entries(cwd, [entry_path])


def upsert_project_entries(cwd, entry_paths):
    """upsert_project_entry for several entry files under ONE index lock and write (a scan that
    marks many entries stale must not rewrite nelly-index.json once per entry)."""
    d = memory_dir(cwd)
    drop, parse = set(), []  # conflict copies -> drop their records; entries -> re-parse
    for entry_path in entry_paths:
        if _is_store_artifact(entry_path, d):
            continue
        relative = os.path.relpath(entry_path, d)
        if is_conflict_copy(os.path.basename(entry_path)):
            # An iCloud conflict copy is never an entry of its own: drop any record that points
            # at it and leave the original's record alone.
            drop.add(relative)
        else:
            parse.append((entry_path, relative))
    if not drop and not parse:
        return _read_index(os.path.join(d, INDEX_FILENAME))

    def apply(records):
        # Parsed inside the store lock so a concurrent writer's newer text can't be overwritten
        # by a record parsed from an older read.
        kept = [r for r in records if r.get("file_path") not in drop]
        for path, relative in parse:
            name = os.path.basename(path)
            # relpath (not a hardcoded "entries"/name join) so this also works for entries nested
            # one level deeper, e.g. entries/<SUMMARY_SUBDIR>/name.md for a file/folder summary.
            slug = name[:-3] if name.endswith(".md") else name
            record = _record_for_entry_file(path, relative)
            kept = [r for r in kept if r.get("slug") != slug]
            if record:
                kept.append(record)
        return kept

    return nelly_store.upsert_index(d, apply)


def lookup_by_path(cwd, path):
    """Fast cache lookup for one repo-relative path, answered entirely from
    the project's nelly-index.json -- no entries/*.md file is opened. This is
    the read side of the file/folder summary cache: before Glob/Grep-ing the
    whole repo for a targeted change, a caller checks here first for an
    already-cached `file-summary`/`folder-summary` entry covering the path.

    `path` must be repo-relative with forward slashes, matching how
    `files`/`folder` are stored on file-summary/folder-summary entries --
    never resolved against `cwd`, mirroring resolve_repo_relative()'s own
    never-absolute invariant for `metadata.files`.

    Returns {"file": <record|None>, "folders": [<record>, ...]}:
      - "file": the `file-summary` record whose `files` list contains `path`
        exactly (one entry per file, so at most one match).
      - "folders": every `folder-summary` record whose `folder` is `path`
        itself or an ancestor directory of it, most specific (longest
        `folder` value) first -- callers wanting the nearest folder summary
        read index 0; a coarser ancestor summary is still useful context.
    """
    if os.path.isabs(path):
        raise ValueError(f"lookup_by_path: path must be repo-relative, got absolute path {path!r}")
    norm = path.rstrip("/")
    index_path = os.path.join(memory_dir(cwd), INDEX_FILENAME)
    records = _read_index(index_path)

    file_record = None
    folder_records = []
    for record in records:
        rtype = record.get("type")
        if rtype == "file-summary" and norm in (record.get("files") or []):
            file_record = record
        elif rtype == "folder-summary":
            folder = (record.get("folder") or "").rstrip("/")
            if folder and (norm == folder or norm.startswith(folder + "/")):
                folder_records.append(record)

    folder_records.sort(key=lambda r: len(r.get("folder") or ""), reverse=True)
    return {"file": file_record, "folders": folder_records}


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

    if "--lookup-path" in argv:
        idx = argv.index("--lookup-path")
        path = argv[idx + 1]
        cwd_idx = argv.index("--cwd") if "--cwd" in argv else None
        cwd = argv[cwd_idx + 1] if cwd_idx is not None else os.getcwd()
        result = lookup_by_path(cwd, path)
        print(json.dumps(result, indent=2))
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
