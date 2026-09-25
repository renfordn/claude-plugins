#!/usr/bin/env python3
"""Research-digest cache: a subagent's multi-file findings, stored once per (topic, path set)
and returned on later lookups as `fresh` or `stale` until any file it read changes.

One markdown file per digest under `<memory_dir>/entries/<DIGEST_SUBDIR>/` is the source of
truth (see agents/agent-nelly.md "Research Digest Cache"). Freshness is the git-blob SHA-1 of
each source file's working-tree bytes, computed here so no `git` binary is needed.
"""
import datetime
import hashlib
import json
import os
import posixpath
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "hooks"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from nelly_memory import (  # noqa: E402
    DIGEST_CHAR_LIMIT, DIGEST_MAX_SOURCES, DIGEST_SUBDIR, DIGEST_TYPE,
    atomic_write, ensure_entries_dir, memory_dir, truncate_summary,
)
import build_index  # noqa: E402

_SLUG_MAX = 40
_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


def blob_hash(data):
    """git-blob-compatible SHA-1 of `data` (bytes): same value as `git hash-object`."""
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def blob_hash_file(path):
    """blob_hash of the file at `path`, or None when it is missing or not a regular file."""
    try:
        with open(path, "rb") as fh:
            return blob_hash(fh.read())
    except OSError:
        return None


def _slug(topic):
    slug = _NON_ALNUM_RE.sub("-", topic.lower()).strip("-")[:_SLUG_MAX].rstrip("-")
    return slug or "untitled"


def digest_filename(topic, paths):
    """`digest-<topic slug, <=40>-<12 hex>.md`. The hash covers the full topic and the sorted
    path set, so two keys that slug the same still get different files, and the same key always
    maps to the same file (which is what makes a re-write overwrite in place)."""
    key = topic + "\n" + "\n".join(sorted(paths))
    return f"digest-{_slug(topic)}-{hashlib.sha1(key.encode('utf-8')).hexdigest()[:12]}.md"


def _marker(dropped):
    return f"\n…[truncated {dropped} chars]"


def truncate_digest(text, limit=DIGEST_CHAR_LIMIT):
    """Cap a digest body at `limit` chars, deterministically. Text that fits is returned
    stripped. Otherwise keep whole lines up to the last newline that leaves room for the
    marker (a hard cut when there is none), then append `\\n…[truncated N chars]`."""
    text = text.strip()
    if len(text) <= limit:
        return text
    budget = limit - len(_marker(len(text)))  # worst-case marker width
    cut = text.rfind("\n", 0, budget + 1)
    kept = text[:cut] if cut > 0 else text[:budget]
    return kept + _marker(len(text) - len(kept))


class DigestError(ValueError):
    """A digest request was invalid; nothing was stored."""


def _normalize_paths(paths):
    if not isinstance(paths, list):
        raise DigestError(f"research digest: paths must be a list of strings, got {type(paths).__name__}")
    if not paths:
        raise DigestError("research digest: at least one source path is required")
    normalized = []
    for raw in paths:
        if not isinstance(raw, str):
            raise DigestError(f"research digest: every source path must be a string, got {raw!r}")
        p = raw.strip()
        if not p or "\n" in p or "\\" in p:
            raise DigestError(f"research digest: invalid source path {raw!r}")
        if os.path.isabs(p) or p.startswith("/"):
            raise DigestError(f"research digest: source path must be repo-relative, got absolute path {p!r}")
        if ".." in p.split("/"):
            raise DigestError(f"research digest: source path must not contain '..': {p!r}")
        p = posixpath.normpath(p)
        if p == ".":
            raise DigestError(f"research digest: invalid source path {raw!r}")
        if p not in normalized:
            normalized.append(p)
    if len(normalized) > DIGEST_MAX_SOURCES:
        raise DigestError(
            f"research digest: {len(normalized)} source paths exceeds the {DIGEST_MAX_SOURCES}-path "
            f"limit; split the digest (e.g. by top-level directory)")
    return sorted(normalized)


def _render(name, topic, sources, updated, body):
    lines = ["---", f"name: {name}", f"description: {truncate_summary(topic)}",
             f"type: {DIGEST_TYPE}", f"topic: {topic}", "sources:"]
    for src in sources:  # flat `path`/`hash` items only -- build_index._parse_sources' shape
        lines += [f"  - path: {src['path']}", f"    hash: {src['hash']}"]
    lines += [f"updated: {updated}", "---", body, ""]
    return "\n".join(lines)


def write_digest(cwd, repo_root, topic, summary, paths, now=None):
    """Validate, hash each source under `repo_root`, and atomically write (or overwrite) the
    digest for (topic, path set) under the project's entries/<DIGEST_SUBDIR>/, then upsert its
    index record. Raises DigestError (nothing written) on an empty topic/summary, an absolute
    or `..` path, more than DIGEST_MAX_SOURCES paths, or a source file that doesn't exist."""
    if not isinstance(topic, str) or not topic.strip():
        raise DigestError("research digest: topic is required and must be a non-empty string")
    if not isinstance(summary, str) or not summary.strip():
        raise DigestError("research digest: summary is required and must be a non-empty string")
    topic = " ".join(topic.split())
    norm_paths = _normalize_paths(paths)

    sources, missing = [], []
    for p in norm_paths:
        h = blob_hash_file(os.path.join(repo_root, *p.split("/")))
        if h is None:
            missing.append(p)
        sources.append({"path": p, "hash": h})
    if missing:
        raise DigestError(f"research digest: source file(s) not found under repo root: {', '.join(missing)}")

    body = truncate_digest(summary)
    filename = digest_filename(topic, norm_paths)
    name = filename[:-3]
    updated = now or datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    path = os.path.join(ensure_entries_dir(cwd, entry_type=DIGEST_TYPE), filename)
    atomic_write(path, _render(name, topic, sources, updated, body))
    build_index.upsert_project_entry(cwd, path)
    return {"file": path, "name": name, "topic": topic, "sources": sources,
            "updated": updated, "truncated": body != summary.strip()}


def _read_index_strict(index_path):
    """The index's records, or None when it is missing, unreadable, or not a JSON list.
    (build_index._read_index returns [] for all of those, indistinguishable from empty.)"""
    try:
        with open(index_path, "r", encoding="utf-8") as fh:
            records = json.load(fh)
    except (OSError, ValueError):
        return None
    return records if isinstance(records, list) else None


def _scan_listing(mem_dir):
    """{relative file_path: mtime} for every digest file on disk (conflict copies skipped)."""
    digest_dir = os.path.join(mem_dir, "entries", DIGEST_SUBDIR)
    listing = {}
    try:
        names = sorted(os.listdir(digest_dir))
    except OSError:
        return listing
    for name in names:
        if not name.endswith(".md") or build_index.is_conflict_copy(name):
            continue
        try:
            listing[os.path.join("entries", DIGEST_SUBDIR, name)] = os.path.getmtime(
                os.path.join(digest_dir, name))
        except OSError:
            continue
    return listing


def _digest_records(mem_dir):
    """(records, source): digest records from nelly-index.json when it exactly matches the
    digest files on disk (same file_path -> mtime set), else from scanning the digest dir."""
    listing = _scan_listing(mem_dir)
    index = _read_index_strict(os.path.join(mem_dir, build_index.INDEX_FILENAME))
    if index is not None:
        indexed = [r for r in index if isinstance(r, dict) and r.get("type") == DIGEST_TYPE]
        if {r.get("file_path"): r.get("mtime") for r in indexed} == listing:
            return indexed, "index"
    records = []
    for rel in listing:
        record = build_index._record_for_entry_file(os.path.join(mem_dir, rel), rel)
        if record and record.get("type") == DIGEST_TYPE:
            records.append(record)
    return records, "scan"


def _read_body(path):
    with open(path, "r", encoding="utf-8") as fh:
        text = fh.read()
    m = build_index._FRONTMATTER_RE.search(text)
    return (text[m.end():] if m else text).strip()


def lookup_digests(cwd, repo_root, path):
    """Every digest whose sources include repo-relative `path`, each marked `fresh` (every
    source's current blob hash matches the recorded one) or `stale` with the `changed` paths
    (hash differs, or the file is gone). Ordered fresh first, then newest `updated`.
    Returns {"path", "digests": [...], "source": "index" | "scan"}."""
    if os.path.isabs(path) or str(path).startswith("/"):
        raise DigestError(f"research digest lookup: path must be repo-relative, got absolute path {path!r}")
    norm = posixpath.normpath(str(path).strip())
    mem_dir = memory_dir(cwd)
    records, source = _digest_records(mem_dir)

    digests = []
    for record in records:
        sources = record.get("sources") or []
        if norm not in [s.get("path") for s in sources]:
            continue
        file_path = os.path.join(mem_dir, record["file_path"])
        try:
            summary = _read_body(file_path)
        except OSError:
            continue
        changed = [s["path"] for s in sources
                   if not s.get("hash")
                   or blob_hash_file(os.path.join(repo_root, *s["path"].split("/"))) != s["hash"]]
        digests.append({
            "name": record.get("slug"), "topic": record.get("topic"),
            "status": "stale" if changed else "fresh", "changed": changed,
            "updated": record.get("updated"), "file": file_path, "summary": summary,
        })

    digests.sort(key=lambda d: d["name"] or "")
    digests.sort(key=lambda d: d["updated"] or "", reverse=True)
    digests.sort(key=lambda d: d["status"] != "fresh")
    return {"path": norm, "digests": digests, "source": source}


def _arg(argv, flag, default=None):
    if flag in argv:
        idx = argv.index(flag)
        if idx + 1 < len(argv):
            return argv[idx + 1]
    return default


def _fail(message):
    print(message, file=sys.stderr)
    sys.exit(2)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    command = argv[0] if argv else None
    cwd = _arg(argv, "--cwd", os.getcwd())
    repo_root = _arg(argv, "--repo-root", cwd)

    if command == "write":
        source = _arg(argv, "--json", "-")
        try:
            raw = sys.stdin.read() if source == "-" else open(source, encoding="utf-8").read()
            request = json.loads(raw)
        except (OSError, ValueError) as exc:
            _fail(f"research digest: could not read request JSON: {exc}")
        if not isinstance(request, dict):
            _fail("research digest: request JSON must be an object")
        try:
            # --repo-root (default cwd) is the only repo root; request JSON can't redirect hashing.
            result = write_digest(cwd, repo_root, request.get("topic"),
                                  request.get("summary"), request.get("paths"))
        except DigestError as exc:
            _fail(str(exc))
        print(json.dumps(result, indent=2))
        return

    if command == "lookup" and len(argv) > 1 and not argv[1].startswith("--"):
        try:
            result = lookup_digests(cwd, repo_root, argv[1])
        except DigestError as exc:
            _fail(str(exc))
        print(json.dumps(result, indent=2))
        return

    _fail("usage: research_digest.py write --json <file|-> [--cwd DIR] [--repo-root DIR]\n"
          "       research_digest.py lookup <repo-relative path> [--cwd DIR] [--repo-root DIR]")


if __name__ == "__main__":
    main()
