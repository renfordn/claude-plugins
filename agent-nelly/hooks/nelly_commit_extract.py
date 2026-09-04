#!/usr/bin/env python3
"""PostToolUse hook: scan Bash tool output for `git commit` success
signatures and auto-write a draft `inferred`-confidence `technique` entry
per commit, so every commit seeds a memory entry without the user ever
running a nelly-memory command by hand.

Sibling to nelly_auto_extract.py (which does the same for test/error
signals) rather than a change to it -- the detection target (a successful
`git commit`, not a failure) and the entry type it writes (`technique`, not
`error-prevention`) are different enough that keeping them in separate files
avoids tangling two unrelated regimes of signal-detection regexes. Both
hooks are wired to the same PostToolUse Bash matcher in hooks/hooks.json and
run independently per Bash call.

Pure Python stdlib only -- no subprocess calls to git, no network, no LLM.
Everything is parsed out of the compact stdout Claude's own `git commit`
Bash call already produced (the `[branch hash] subject` header line, the
`N file(s) changed` summary line, and any `create mode`/`delete mode`/
`rename` lines) -- this hook never shells out to git itself to double-check
or enrich what it read.

Fires on every Bash completion, so it must be fast, silent unless it
actually writes something, and never break the user's bash flow. The entire
body runs under one broad try/except -- any failure is swallowed and
treated as a silent no-op, never a crash or stderr spew.

Set env NELLY_GATE=off (or 0/false/disabled, case-insensitive) to disable
entirely, same convention as the other Nelly gate hooks.

On a dedup hit, delegates to nelly_auto_extract._bump_seen_count_and_maybe_promote
-- same auto-confirmation-after-N-occurrences logic that module documents in
full, shared here rather than duplicated since `git-pattern-<hash>` slugs are
already keyed by commit hash (so a dedup hit here is rarer than in the
test/error-signal hook, but the mechanism is identical).
"""
import json
import os
import re
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import nelly_memory  # noqa: E402
import build_index  # noqa: E402
from nelly_auto_extract import _entry_exists, _bump_seen_count_and_maybe_promote  # noqa: E402

_MAX_DESCRIPTION_LEN = 140

_COMMIT_HEADER_RE = re.compile(
    r"^\[(?P<branch>\S+)(?:\s+\(root-commit\))?\s+(?P<hash>[0-9a-f]{4,40})\]\s+(?P<subject>.+)$",
    re.M,
)
_FILES_CHANGED_RE = re.compile(r"^\s*(\d+)\s+files?\s+changed\b", re.M)
_CREATE_MODE_RE = re.compile(r"^\s*create mode \d+\s+(\S.*\S|\S)\s*$", re.M)
_DELETE_MODE_RE = re.compile(r"^\s*delete mode \d+\s+(\S.*\S|\S)\s*$", re.M)
_RENAME_RE = re.compile(r"^\s*rename\s+(\S.*?)\s*=>\s*(\S.*?)\s*\(\d+%\)\s*$", re.M)


def detect_commits(stdout):
    """Scan `stdout` for one or more `git commit` success headers.

    Returns a list of dicts (possibly empty) -- one per detected commit, in
    the order they appear -- each shaped
    `{"hash": str, "subject": str, "files_changed": int, "paths": [str,...]}`.
    Never raises; unrecognized/clean output simply yields no matches.
    """
    if not stdout or not stdout.strip():
        return []

    headers = list(_COMMIT_HEADER_RE.finditer(stdout))
    commits = []
    for i, m in enumerate(headers):
        start = m.end()
        end = headers[i + 1].start() if i + 1 < len(headers) else len(stdout)
        segment = stdout[start:end]

        files_m = _FILES_CHANGED_RE.search(segment)
        files_changed = int(files_m.group(1)) if files_m else 0

        paths = []
        for pm in _CREATE_MODE_RE.finditer(segment):
            paths.append(pm.group(1).strip())
        for pm in _DELETE_MODE_RE.finditer(segment):
            paths.append(pm.group(1).strip())
        for pm in _RENAME_RE.finditer(segment):
            paths.append(pm.group(1).strip())
            paths.append(pm.group(2).strip())
        # de-dup while preserving first-seen order
        seen = set()
        deduped_paths = []
        for p in paths:
            if p and p not in seen:
                seen.add(p)
                deduped_paths.append(p)

        commits.append(
            {
                "hash": m.group("hash"),
                "subject": m.group("subject").strip(),
                "files_changed": files_changed,
                "paths": deduped_paths,
            }
        )
    return commits


def _make_slug(commit_hash):
    return f"git-pattern-{commit_hash[:12]}"


def _tags_for_paths(paths):
    tags = set()
    for p in paths:
        parts = p.split("/")
        if len(parts) > 1 and parts[0]:
            tags.add(parts[0])
    return sorted(tags)


def _write_entry(cwd, slug, commit):
    nelly_memory.ensure_entries_dir(cwd)
    path = nelly_memory.entry_path(cwd, slug)

    description = commit["subject"][:_MAX_DESCRIPTION_LEN]
    paths = commit["paths"]
    tags = _tags_for_paths(paths)
    paths_field = ", ".join(paths)
    tags_field = ", ".join(tags)
    paths_line = ", ".join(paths) if paths else "none listed in compact output"

    body = (
        f"Technique: {commit['subject']}\n"
        f"Commit: {commit['hash']} ({commit['files_changed']} file(s) changed)\n"
        f"Paths: {paths_line}\n"
        "Context: Detected automatically from a `git commit` completion in "
        "Bash output.\n"
    )
    content = (
        "---\n"
        f"name: {slug}\n"
        f"description: {description}\n"
        "metadata:\n"
        "  type: technique\n"
        f"  last_referenced: {date.today().isoformat()}\n"
        "  confidence: inferred\n"
        "  seen_count: 1\n"
        f"  commit: {commit['hash']}\n"
        f"  files_changed: {commit['files_changed']}\n"
        f"  paths: [{paths_field}]\n"
        f"tags: [{tags_field}]\n"
        "---\n\n"
        f"{body}"
    )
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)

    nelly_memory.write_index_line(cwd, slug, description, "technique", confidence="inferred")
    build_index.upsert_project_entry(cwd, path)


def _run():
    if os.environ.get("NELLY_GATE", "").lower() in ("off", "0", "false", "disabled"):
        return

    payload = json.load(sys.stdin)
    if payload.get("tool_name") != "Bash":
        return

    tool_response = payload.get("tool_response") or {}
    stdout = tool_response.get("stdout")
    stdout = stdout if isinstance(stdout, str) else ""

    commits = detect_commits(stdout)
    if not commits:
        return

    cwd = payload.get("cwd") or os.getcwd()
    for commit in commits:
        slug = _make_slug(commit["hash"])
        if _entry_exists(cwd, slug):
            result = _bump_seen_count_and_maybe_promote(cwd, slug)
            if result and result[1]:
                print(f"[nelly] promoted to explicit: {slug} (seen {result[0]}x)")
            continue
        _write_entry(cwd, slug, commit)
        print(f"[nelly] commit pattern saved: {slug}")


def main():
    try:
        _run()
    except Exception:
        pass  # never break the user's bash flow
    sys.exit(0)


if __name__ == "__main__":
    main()
