#!/usr/bin/env python3
"""SessionStart helper: mark entries whose sources changed as stale, never delete (R17).

Conservative: only entries that carry `sources` and are not already stale are checked, oldest
`verified` first, resuming after a rotation cursor (freshness-cursor.json in the machine-local
state dir) so a time budget never starves the later entries. A changed or missing source file
(or any hash error) is a stale path. Marking only adds `stale`, `stale_since`, `stale_paths`
inside `metadata:` and refreshes that entry's index record; nothing is deleted or moved, and
only `nelly_evidence.py refresh` clears the flag. Marking also stores `stale_digest` (hash of
the entry's description and body at that moment): refresh uses it to tell whether the entry was
rewritten since. The index is updated once per scan. Any per-entry error, including StoreLocked,
skips that entry (fail open). Contract: INTEROP.md "Source evidence, staleness, capture and
safe writes"."""
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))

import build_index  # noqa: E402
import nelly_frontmatter  # noqa: E402
import nelly_pending  # noqa: E402
import nelly_store  # noqa: E402
import shared_slug  # noqa: E402
from nelly_memory import local_state_dir, memory_dir  # noqa: E402
from research_digest import blob_hash_file  # noqa: E402

CURSOR_FILE = "freshness-cursor.json"
NAMED_CAP = 5
_STALE_KEYS = ("stale", "stale_since", "stale_paths", "stale_digest")


def _repo_root(cwd):
    """The repo root in cwd's own lexical spelling (so printed --cwd values and the memory-dir
    slug match what the model's `--cwd` resolves to), or None outside a repo."""
    try:
        return shared_slug.repo_root(cwd, require_git=True)
    except Exception:
        return None


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


def _mark_text(text, paths, today):
    """Replace the stale keys (whole extent, incl. block-list items) and add the new ones at the end
    of the `metadata:` block; every other line stays identical. Returns None when there is no
    frontmatter `metadata:` block."""
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return None
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        return None
    fm_lines = lines[1:end]
    try:
        for key in _STALE_KEYS:
            nelly_frontmatter.set_key(fm_lines, key, None)
        nelly_frontmatter.set_key(fm_lines, "stale", "true")
        nelly_frontmatter.set_key(fm_lines, "stale_since", today)
        nelly_frontmatter.set_key(fm_lines, "stale_paths", nelly_frontmatter.flow_list(paths))
        nelly_frontmatter.set_key(fm_lines, "stale_digest", nelly_frontmatter.content_digest(text))
    except ValueError:
        return None
    return "".join([lines[0]] + fm_lines + lines[end:])


def _gone(repo_root, rel):
    """True when `rel` is missing from the working tree and from HEAD (safe to --drop-paths)."""
    if os.path.lexists(os.path.join(repo_root, *rel.split("/"))):
        return False
    try:
        proc = subprocess.run(["git", "-C", repo_root, "--literal-pathspecs", "cat-file", "-e",
                               f"HEAD:{rel}"], capture_output=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return False
    return proc.returncode != 0


def _refresh_cmd(repo_root, slug, paths):
    """Runnable `nelly_evidence.py refresh` for one marked entry (absolute path, env prefix):
    sources gone from the working tree and HEAD go under --drop-paths, the rest under --paths."""
    drops = [p for p in paths if _gone(repo_root, p)]
    keep = [p for p in paths if p not in drops]
    args = ["refresh", "--cwd", repo_root, "--slug", slug]
    if keep:
        args += ["--paths", *keep]
    if drops:
        args += ["--drop-paths", *drops]
    return nelly_pending._cmd("scripts/nelly_evidence.py", *args)


def _mark_stale(mem, record, paths, today, timeout):
    """Mark one entry under the store lock (bounded wait). Returns (update_entry status, entry path)."""
    path = os.path.join(mem, record["file_path"])
    with nelly_store.lock(mem, timeout=timeout):
        status = nelly_store.update_entry(
            mem, path, lambda old: _mark_text(old, paths, today) if old else None)
    return status, path


def stale_cmd(repo_root):
    """Runnable `nelly_evidence.py stale` (lists every stale entry with its refresh command)."""
    return nelly_pending._cmd("scripts/nelly_evidence.py", "stale", "--cwd", repo_root)


def _record_paths(record):
    return list(record.get("stale_paths") or [x.get("path") for x in record["sources"] if x.get("path")])


def stale_listing(repo_root, records):
    """[{slug, stale_since, stale_paths, command}] for stale sourced entries, oldest stale_since first."""
    stale = [r for r in records if r.get("sources") and r.get("stale") is True
             and r.get("type") != "research-digest"]
    stale.sort(key=lambda r: (str(r.get("stale_since") or ""), str(r["slug"])))
    return [{"slug": r["slug"], "stale_since": r.get("stale_since") or "",
             "stale_paths": list(r.get("stale_paths") or []),
             "command": _refresh_cmd(repo_root, r["slug"], _record_paths(r))} for r in stale]


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

    already = [r for r in records if r.get("sources") and r.get("stale") is True
               and r.get("type") != "research-digest"]
    already_stale = len(already)
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
    marked, marked_paths = [], []
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
                status, epath = _mark_stale(mem, record, paths, today, wait)
                if status == "written":
                    marked.append((record["slug"], paths))
                    marked_paths.append(epath)
        except Exception:  # StoreLocked included: skip this entry, fail open
            continue
    if finished:
        _save_cursor(cursor_path, None)  # full pass done: next scan starts from the oldest
    elif last_key:
        _save_cursor(cursor_path, last_key)

    if marked_paths:
        try:
            build_index.upsert_project_entries(cwd, marked_paths)  # one index write for the scan
        except Exception:  # StoreLocked included: the next index rebuild picks the marks up
            pass

    lines = []
    if marked:
        named = [f"{slug} ({', '.join(paths)})" for slug, paths in marked[:NAMED_CAP]]
        if len(marked) > NAMED_CAP:
            named.append(f"+{len(marked) - NAMED_CAP} more")
        lines.append(f"{len(marked)} memory entries marked stale (sources changed): {', '.join(named)}.")
    if marked or already:
        todo = [(r["slug"], str(r.get("stale_since") or ""), _record_paths(r)) for r in already]
        todo += [(slug, today, paths) for slug, paths in marked]
        todo.sort(key=lambda t: (t[1], t[0]))
        lines.append("Stale entries, oldest first. Recheck each source: if the fact changed, rewrite the "
                     "entry (body/description) or archive it first, then run its refresh command; if it "
                     "still holds as written, add --confirm-unchanged to the command:")
        for slug, _since, paths in todo[:NAMED_CAP]:
            lines.append(f"  {slug}: {_refresh_cmd(repo_root, slug, paths)}")
        if len(todo) > NAMED_CAP:
            lines.append(f"  +{len(todo) - NAMED_CAP} more stale entries: list them with "
                         f"{stale_cmd(repo_root)}")
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
