#!/usr/bin/env python3
"""Record / refresh source evidence on Agent Nelly memory entries (R16, R17).

  record  --cwd DIR --slug S --type T --description D (--body TEXT | --body-file F)
          --paths P... [--symbols ...] --basis observed|inferred|unknown [--unknowns TEXT]
          [--confidence explicit|inferred]
      Hash each path (git blob SHA-1), stamp revision (HEAD or `unknown`) and today's date, write
      the entry via nelly_store.write_entry (expected "missing"), then upsert the index and
      MEMORY.md (the MEMORY.md line is idempotent and also appended on "unchanged", so re-running
      recovers from a lock timeout). Refuses (exit 2) a path that is modified, staged-but-uncommitted
      or untracked: findings on uncommitted code belong in the pending queue
      (`hooks/nelly_pending.py add`).
      A file-relevance entry also gets `files:yes paths:<root-relative>` on its MEMORY.md line;
      paths containing whitespace or ';' are not written to that `paths:` field (index format
      limit) and so never surface in proactive surfacing. Placeholder values (`<...>`) for
      --cwd, --slug, --description and --body are rejected (exit 2).
  stale   --cwd DIR
      Lists the stale entries (oldest stale_since first) as JSON, each with its runnable refresh command.
  refresh --cwd DIR --slug S [--paths P...] [--drop-paths P...] [--confirm-unchanged]
      Under nelly_store.update_entry re-hash only the given paths (each must be in the entry's
      sources), update their hashes, remove them from stale_paths, and drop
      stale/stale_since/stale_paths only when no stale path remains. Refuses paths that are
      modified/staged/untracked (exit 2). `--drop-paths` removes sources whose file is gone from
      both the working tree and HEAD (never the last source: archive the entry instead).
      A stale entry that was not rewritten since it was marked (its description and body still hash
      to `stale_digest`, or the mark has none) is refused (exit 2) unless `--confirm-unchanged` says
      the recheck found the fact still true: refresh re-pins hashes, it never proves a fact. A
      dropped path is also removed from `metadata.files` and the MEMORY.md `paths:` field.
      `revision` and `verified` are stamped (HEAD, today) only when, after the refresh, every
      remaining source's stored hash equals its committed blob at HEAD (outside a repo: when every
      remaining source was re-hashed in this refresh); otherwise they are kept unchanged.

Paths are given relative to --cwd and stored relative to the git toplevel (to --cwd outside git).
Run it with the env prefix and absolute script path shown in the SessionStart line (CLAUDE_PLUGIN_ROOT
is unset in Bash). Prints JSON. Exit codes: 0 ok, 2 usage/validation error, 3 write conflict (sidecar
path in the JSON `path`), 5 plugin data dir unavailable, 75 store lock timeout.
"""
import argparse
import json
import os
import re
import subprocess
import sys
from datetime import date

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(_HERE, "..", "hooks"))
try:
    import build_index  # noqa: E402
    import nelly_freshness  # noqa: E402
    import nelly_frontmatter  # noqa: E402
    import nelly_memory  # noqa: E402
    import nelly_pending  # noqa: E402
    import nelly_store  # noqa: E402
    import shared_slug  # noqa: E402
    from research_digest import blob_hash_file  # noqa: E402
except Exception as _exc:  # CLAUDE_PLUGIN_DATA unset: main reports it cleanly (exit 5)
    _IMPORT_ERROR = _exc
else:
    _IMPORT_ERROR = None

_FM_RE = re.compile(r"^---\n(.*?)\n---", re.S)
_STALE_KEYS = ("stale", "stale_since", "stale_paths", "stale_digest")
_NEEDS_CONFIDENCE = ("error-prevention", "technique")
_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class EvidenceError(Exception):
    """Validation failure; message goes to stderr, exit 2."""


def _git(cwd, *args):
    try:
        return subprocess.run(["git", "--literal-pathspecs", "-C", cwd, *args],
                              capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None


def _head(base):
    r = _git(base, "rev-parse", "HEAD")
    return r.stdout.strip() if r and r.returncode == 0 and r.stdout.strip() else "unknown"


def _base(cwd):
    """Directory sources are relative to: the git toplevel, else cwd, in cwd's own lexical spelling
    (shared_slug.repo_root), so printed --cwd values and the slug match the rest of the plugin."""
    return shared_slug.repo_root(os.path.abspath(cwd))


def _resolve(cwd, base, p, must_exist=True):
    """Validate a path given relative to cwd and return it relative to `base`."""
    if not p or not build_index.is_repo_relative(p):
        raise EvidenceError(f"path '{p}' must be repo-relative (no leading '/', '~' or '..')")
    full = os.path.normpath(os.path.join(os.path.abspath(cwd), p))
    if must_exist and not os.path.isfile(full):
        raise EvidenceError(f"path '{p}' does not exist under {cwd}")
    rel = os.path.relpath(full, base)
    if rel.startswith(".."):  # cwd reached through a symlink from outside the repo
        rel = os.path.relpath(os.path.realpath(full), os.path.realpath(base))
    if rel.startswith(".."):
        raise EvidenceError(f"path '{p}' is outside the repository root {base}")
    return rel.replace(os.sep, "/")


def _check_committed(base, head, paths):
    if head == "unknown":
        return  # no git history to compare against
    bad = []
    for p in paths:
        tracked = _git(base, "ls-files", "--error-unmatch", "--", p)
        status = _git(base, "status", "--porcelain", "--", p)
        if not tracked or tracked.returncode != 0 or not status or status.stdout.strip():
            bad.append(p)
    if bad:
        queue = nelly_pending._cmd("hooks/nelly_pending.py", "add", "--cwd", base, "--summary",
                                   "<one-line finding>", "--paths", *bad)
        raise EvidenceError(
            "uncommitted/untracked/modified: " + ", ".join(bad) + ". Evidence is recorded only against "
            f"committed bytes; queue this finding instead (replace the summary): `{queue}`")


def _in_head(base, p):
    r = _git(base, "cat-file", "-e", f"HEAD:{p}")
    return bool(r) and r.returncode == 0


def _flow_sources(items):
    return "[" + ", ".join(f"{{path: {nelly_frontmatter.quote(s['path'])}, hash: {s['hash']}}}"
                           for s in items) + "]"


def _flow_list(items):
    return nelly_frontmatter.flow_list(items)


def _one_line(text):
    return " ".join(str(text).split())


def _build_entry(a, sources, revision):
    confidence = a.confidence
    if a.type == "technique" and not confidence:
        confidence = "inferred"
    if a.type in _NEEDS_CONFIDENCE and confidence not in ("explicit", "inferred"):
        raise EvidenceError(f"--confidence explicit|inferred is required for type {a.type}")
    a.confidence = confidence
    body = a.body if a.body is not None else open(a.body_file, encoding="utf-8").read()
    lines = ["---", f"name: {nelly_frontmatter.name_scalar(a.slug)}",
             f"description: {nelly_frontmatter.quote_always(_one_line(a.description))}", "metadata:",
             f"  type: {a.type}", f"  last_referenced: {date.today().isoformat()}"]
    if a.type in _NEEDS_CONFIDENCE:
        lines.append(f"  confidence: {confidence}")
    if a.type == "file-relevance":
        lines.append(f"  files: {_flow_list(a.paths)}")
    lines.append(f"  sources: {_flow_sources(sources)}")
    if a.symbols:
        lines.append(f"  symbols: {_flow_list(a.symbols)}")
    lines += [f"  revision: {revision}", f"  verified: {date.today().isoformat()}", f"  basis: {a.basis}"]
    if a.unknowns:
        lines.append(f"  unknowns: {json.dumps(_one_line(a.unknowns))}")
    lines += ["---", "", body.strip(), ""]
    return "\n".join(lines)


def _reject_placeholders(a):
    try:
        for flag, value in (("--cwd", a.cwd), ("--slug", a.slug), ("--description", a.description),
                            ("--body", a.body)):
            nelly_frontmatter.reject_placeholder(flag, value)
    except ValueError as exc:
        raise EvidenceError(str(exc))


def cmd_record(a):
    _reject_placeholders(a)
    if a.type in (*nelly_memory.SUMMARY_TYPES, nelly_memory.DIGEST_TYPE):
        raise EvidenceError(f"--type {a.type} has its own writer (file/folder summaries: agent-nelly's "
                            "summary cache; research-digest: scripts/research_digest.py)")
    if not _SLUG_RE.match(a.slug or "") or build_index.is_conflict_copy(a.slug + ".md"):
        raise EvidenceError(f"invalid slug '{a.slug}': use a kebab-case slug (a-z, 0-9, '-')")
    if a.basis not in ("observed", "inferred", "unknown"):
        raise EvidenceError("--basis must be observed, inferred or unknown")
    cwd = os.path.abspath(a.cwd)
    base = _base(cwd)
    paths = list(dict.fromkeys(_resolve(cwd, base, p) for p in a.paths))
    head = _head(base)
    _check_committed(base, head, paths)
    sources = [{"path": p, "hash": blob_hash_file(os.path.join(base, p))} for p in paths]
    a.paths = paths  # file-relevance `files` use the same root-relative paths
    text = _build_entry(a, sources, head)

    nelly_memory.ensure_entries_dir(cwd, a.type)
    root = nelly_memory.memory_dir(cwd)
    path = nelly_memory.entry_path(cwd, a.slug, a.type)
    with nelly_store.lock(root):  # entry, MEMORY.md line and index record under one hold
        result = nelly_store.write_entry(root, path, text, nelly_store.MISSING)
        if result["status"] == "conflict":
            return 3, {"status": "conflict", "slug": a.slug, "path": result["path"], "entry": path}
        # `paths:` is a whitespace/`;`-delimited index field: only file-relevance entries carry it
        indexed = [p for p in paths if not re.search(r"[\s;]", p)] if a.type == "file-relevance" else []
        nelly_memory.write_index_line(
            cwd, a.slug, _one_line(a.description), a.type,
            confidence=a.confidence if a.type in _NEEDS_CONFIDENCE else None,
            files_present=bool(indexed), paths=indexed or None)
        build_index.upsert_project_entry(cwd, path)
    return 0, {"status": result["status"], "slug": a.slug, "path": path, "revision": head,
               "sources": sources}


# --- refresh: line-level frontmatter surgery via nelly_frontmatter (other lines stay byte-identical) ---

def _all_current(base, head, sources, new_hashes):
    """True when every remaining source's stored hash is its committed blob at HEAD (outside a
    repo: every remaining source was re-hashed in this refresh)."""
    if head == "unknown":
        return set(new_hashes) >= {s["path"] for s in sources}
    for s in sources:
        r = _git(base, "rev-parse", f"HEAD:{s['path']}")
        if not r or r.returncode != 0 or r.stdout.strip() != s["hash"]:
            return False
    return True


def _refresh_text(old, a, base, head, paths, drops):
    if old is None:
        raise EvidenceError(f"no entry '{a.slug}' to refresh")
    m = _FM_RE.match(old)
    if not m:
        raise EvidenceError(f"entry '{a.slug}' has no parseable frontmatter")
    block = m.group(1)
    rec = build_index.parse_evidence(block)
    sources = rec.get("sources")
    if not sources:
        raise EvidenceError(f"entry '{a.slug}' has no sources to refresh")
    if (rec.get("stale") is True and not a.confirm_unchanged
            and rec.get("stale_digest") in (None, nelly_frontmatter.content_digest(old))):
        stale_on = ', '.join(rec.get('stale_paths') or [])
        if rec.get("stale_digest") is None:
            raise EvidenceError(
                f"entry '{a.slug}' was marked stale before rewrite tracking, so refresh cannot tell "
                f"whether it was rewritten; if you already rewrote it, or it is still true after "
                f"rechecking {stale_on}, rerun with --confirm-unchanged (otherwise rewrite or archive it).")
        raise EvidenceError(
            f"entry '{a.slug}' is stale and has not been rewritten since it was marked: refresh only "
            f"re-pins hashes, it does not prove the fact. Recheck {stale_on}"
            " against the source: if the fact changed, rewrite the entry's body/description first (or "
            "archive it), then run refresh; if it still holds exactly as written, re-run with "
            "--confirm-unchanged.")
    known = {s["path"] for s in sources}
    unknown = [p for p in paths + drops if p not in known]
    if unknown:
        raise EvidenceError("path(s) not in the entry's sources: " + ", ".join(unknown))
    for p in drops:
        if os.path.lexists(os.path.join(base, p)) or (head != "unknown" and _in_head(base, p)):
            raise EvidenceError(f"cannot drop '{p}': it still exists in the working tree or HEAD "
                                f"(use --paths to re-hash it)")
    new_hashes = {p: blob_hash_file(os.path.join(base, p)) for p in paths}
    sources = [dict(s, hash=new_hashes.get(s["path"], s["hash"])) for s in sources
               if s["path"] not in drops]
    if not sources:
        raise EvidenceError("cannot drop the last source; archive the entry instead")
    gone = set(paths) | set(drops)
    remaining = [p for p in (rec.get("stale_paths") or []) if p not in gone]

    lines = block.split("\n")
    try:
        nelly_frontmatter.set_key(lines, "sources", _flow_sources(sources))
        files = build_index._inline_list(block, "files") if drops else None
        if files and any(f in drops for f in files):
            nelly_frontmatter.set_key(lines, "files", _flow_list([f for f in files if f not in drops]))
        if _all_current(base, head, sources, new_hashes):
            nelly_frontmatter.set_key(lines, "revision", head, anchor="sources")
            nelly_frontmatter.set_key(lines, "verified", date.today().isoformat(), anchor="revision")
        if remaining:
            nelly_frontmatter.set_key(lines, "stale_paths", _flow_list(remaining))
        else:
            for k in _STALE_KEYS:
                nelly_frontmatter.set_key(lines, k, None)
    except ValueError as exc:
        raise EvidenceError(f"entry '{a.slug}' frontmatter cannot be edited: {exc}")
    return old[:m.start(1)] + "\n".join(lines) + old[m.end(1):]


def _find_entry(cwd, slug):
    for t in (None, "file-summary"):
        p = nelly_memory.entry_path(cwd, slug, t)
        if os.path.isfile(p):
            return p
    return nelly_memory.entry_path(cwd, slug)  # missing: update_entry hands fn(None), which errors


def cmd_refresh(a):
    if not a.paths and not a.drop_paths:
        raise EvidenceError("refresh needs --paths and/or --drop-paths")
    cwd = os.path.abspath(a.cwd)
    base = _base(cwd)
    paths = list(dict.fromkeys(_resolve(cwd, base, p) for p in a.paths))
    drops = list(dict.fromkeys(_resolve(cwd, base, p, must_exist=False) for p in a.drop_paths))
    if set(paths) & set(drops):
        raise EvidenceError("a path cannot be both refreshed and dropped")
    head = _head(base)
    _check_committed(base, head, paths)
    root = nelly_memory.memory_dir(cwd)
    path = _find_entry(cwd, a.slug)
    with nelly_store.lock(root):  # entry, MEMORY.md line and index record under one hold
        status = nelly_store.update_entry(root, path,
                                          lambda old: _refresh_text(old, a, base, head, paths, drops))
        if drops:
            _drop_memory_paths(root, a.slug, drops)
        build_index.upsert_project_entry(cwd, path)
    return 0, {"status": status, "slug": a.slug, "path": path, "revision": head,
               "paths": paths, "dropped": drops}


_PATHS_FIELD_RE = re.compile(r"( paths:)([^\s\]]*)")


def _drop_memory_paths(root, slug, drops):
    """Remove dropped paths from the entry's MEMORY.md `paths:` field (the `files:yes paths:` pair
    goes when none is left). Caller holds the store lock."""
    mem = os.path.join(root, "MEMORY.md")
    try:
        with open(mem, encoding="utf-8") as fh:
            lines = fh.readlines()
    except OSError:
        return
    marker = f"](entries/{slug}.md)"
    out = []
    for ln in lines:
        m = _PATHS_FIELD_RE.search(ln) if marker in ln else None
        if m:
            kept = [p for p in m.group(2).split(";") if p and p not in drops]
            if kept:
                ln = ln[:m.start()] + m.group(1) + ";".join(kept) + ln[m.end():]
            else:
                ln = (ln[:m.start()] + ln[m.end():]).replace(" files:yes", "")
        out.append(ln)
    if out != lines:
        nelly_store.atomic_write(mem, "".join(out))


def cmd_stale(a):
    base = _base(os.path.abspath(a.cwd))
    records = build_index._read_index(os.path.join(nelly_memory.memory_dir(base), build_index.INDEX_FILENAME))
    return 0, nelly_freshness.stale_listing(
        base, [r for r in records if isinstance(r, dict) and r.get("slug")])


def _parser():
    ap = argparse.ArgumentParser(prog="nelly_evidence.py", description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("record")
    r.add_argument("--cwd", required=True)
    r.add_argument("--slug", required=True)
    r.add_argument("--type", required=True)
    r.add_argument("--description", required=True)
    g = r.add_mutually_exclusive_group(required=True)
    g.add_argument("--body")
    g.add_argument("--body-file")
    r.add_argument("--paths", nargs="+", required=True)
    r.add_argument("--symbols", nargs="*", default=[])
    r.add_argument("--basis", required=True)
    r.add_argument("--unknowns")
    r.add_argument("--confidence", choices=("explicit", "inferred"))
    f = sub.add_parser("refresh")
    f.add_argument("--cwd", required=True)
    f.add_argument("--slug", required=True)
    f.add_argument("--paths", nargs="*", default=[])
    f.add_argument("--drop-paths", nargs="*", default=[], help="remove sources whose file is gone")
    f.add_argument("--confirm-unchanged", action="store_true",
                   help="the recheck found a stale entry's fact still true (required unless it was rewritten)")
    t = sub.add_parser("stale")
    t.add_argument("--cwd", required=True)
    return ap


def main(argv=None):
    if _IMPORT_ERROR is not None:
        print(f"nelly_evidence: {_IMPORT_ERROR}", file=sys.stderr)
        return 5
    args = _parser().parse_args(argv)
    try:
        code, out = {"record": cmd_record, "refresh": cmd_refresh, "stale": cmd_stale}[args.cmd](args)
    except EvidenceError as exc:
        print(f"nelly_evidence: {exc}", file=sys.stderr)
        return 2
    except nelly_store.StoreLocked as exc:
        print(f"nelly_evidence: memory store is locked, retry shortly ({exc})", file=sys.stderr)
        return 75
    except OSError as exc:
        print(f"nelly_evidence: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(out))
    return code


if __name__ == "__main__":
    sys.exit(main())
