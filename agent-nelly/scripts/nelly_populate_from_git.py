#!/usr/bin/env python3
"""One-shot (but safely re-runnable) seeder: mines existing `git log` history
across one or more repos and writes an inferred-confidence `technique` entry
per commit, so a brand-new Agent Nelly memory store isn't empty on day one.

Sibling to hooks/nelly_commit_extract.py rather than a change to it -- that
hook parses a *live* `git commit` success message already sitting in a Bash
tool's stdout, so it never shells out to git itself. This script has no such
stdout to read (the commits already happened, possibly in a prior session,
possibly in a repo Claude was never run in at all), so it is the one place
in this plugin that calls `git log` directly. It reuses
nelly_commit_extract's slug pattern (`git-pattern-<hash[:12]>`), tag
derivation, and entry shape so a commit picked up here and one picked up
live by the hook are indistinguishable in the memory store -- and so the
hook's own duplicate check (matched on that same slug) makes re-running this
script after real commits accumulate a safe no-op for anything already
recorded.

Pure Python stdlib plus one `git log` subprocess call per repo -- no LLM, no
network, no token cost. Memory is scoped per-project by cwd (see
hooks/nelly_memory.py's project_slug()), so each repo path passed to this
script seeds that repo's own memory store, exactly as if Claude Code had
been run inside it all along.
"""
import argparse
import os
import subprocess
import sys
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "hooks"))
import nelly_memory  # noqa: E402
import nelly_commit_extract as commit_extract  # noqa: E402
from nelly_auto_extract import _entry_exists  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_index  # noqa: E402

_DEFAULT_LIMIT = 200
_DEFAULT_BASE = "~/Codebase"
_MAX_DEPTH = 2

# Commit boundary is \x00 (never appears in a subject line); hash and
# subject within one commit are split on \x1f. Both are ASCII control
# characters no git subject would ever contain, so no escaping is needed.
_LOG_FORMAT = "%x00%H%x1f%s"


def _parse_log_output(output):
    """Parse `git log --name-only --pretty=format:<_LOG_FORMAT>` output into
    a list of dicts shaped like nelly_commit_extract.detect_commits()'s
    return value: `{"hash", "subject", "files_changed", "paths"}`.

    Never raises on malformed/empty input -- an unparseable chunk (no
    \\x1f separator) is simply skipped.
    """
    commits = []
    for chunk in output.split("\x00"):
        chunk = chunk.strip("\n")
        if not chunk:
            continue
        header, _, rest = chunk.partition("\n")
        if "\x1f" not in header:
            continue
        commit_hash, subject = header.split("\x1f", 1)
        paths = [p.strip() for p in rest.splitlines() if p.strip()]
        commits.append(
            {
                "hash": commit_hash.strip(),
                "subject": subject.strip(),
                "files_changed": len(paths),
                "paths": paths,
            }
        )
    return commits


def get_commits(repo, limit):
    """Run `git log` in `repo` and return up to `limit` commits, most recent
    first. Returns [] on any git failure (not a repo, no commits yet,
    missing git binary) rather than raising -- a bad repo path should not
    abort scanning the rest of --repo's arguments.
    """
    cmd = [
        "git",
        "-C",
        repo,
        "log",
        f"-n{limit}",
        "--name-only",
        f"--pretty=format:{_LOG_FORMAT}",
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return []
    if proc.returncode != 0:
        return []
    return _parse_log_output(proc.stdout)


def discover_repos(base, max_depth=_MAX_DEPTH):
    """Find git repos under `base`, up to `max_depth` directory levels deep.
    A directory containing `.git` is treated as a repo and is not descended
    into further (no nested-repo double counting). Missing `base` yields [].
    """
    repos = []
    if not os.path.isdir(base):
        return repos

    def walk(path, depth):
        if os.path.isdir(os.path.join(path, ".git")):
            repos.append(path)
            return
        if depth >= max_depth:
            return
        try:
            names = sorted(os.listdir(path))
        except OSError:
            return
        for name in names:
            if name.startswith("."):
                continue
            sub = os.path.join(path, name)
            if os.path.isdir(sub):
                walk(sub, depth + 1)

    walk(base, 0)
    return repos


def _write_entry(repo, slug, commit):
    nelly_memory.ensure_entries_dir(repo)
    path = nelly_memory.entry_path(repo, slug)

    description = commit["subject"][: commit_extract._MAX_DESCRIPTION_LEN]
    paths = commit["paths"]
    tags = commit_extract._tags_for_paths(paths)
    paths_field = ", ".join(paths)
    tags_field = ", ".join(tags)
    paths_line = ", ".join(paths) if paths else "none recorded"

    body = (
        f"Technique: {commit['subject']}\n"
        f"Commit: {commit['hash']} ({commit['files_changed']} file(s) changed)\n"
        f"Paths: {paths_line}\n"
        f"Context: Pre-populated from a git history scan of {repo}.\n"
    )
    content = (
        "---\n"
        f"name: {slug}\n"
        f"description: {description}\n"
        "metadata:\n"
        "  type: technique\n"
        f"  last_referenced: {date.today().isoformat()}\n"
        "  confidence: inferred\n"
        f"  commit: {commit['hash']}\n"
        f"  files_changed: {commit['files_changed']}\n"
        f"  paths: [{paths_field}]\n"
        f"tags: [{tags_field}]\n"
        "---\n\n"
        f"{body}"
    )
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)

    nelly_memory.write_index_line(repo, slug, description, "technique", confidence="inferred")
    build_index.upsert_project_entry(repo, path)


def populate_repo(repo, limit, dry_run):
    """Scan one repo's commit history and write (or, if `dry_run`, just
    count) an inferred `technique` entry per not-yet-recorded commit.

    Returns (populated, skipped) -- `populated` counts commits that got (or,
    under --dry-run, would get) a new entry; `skipped` counts commits that
    already have one, matched via nelly_auto_extract._entry_exists() against
    the same `git-pattern-<hash[:12]>` slug the live commit hook writes, so
    re-running this after real commits land is a safe no-op for anything
    already recorded.
    """
    repo = os.path.abspath(repo)
    populated = 0
    skipped = 0
    for commit in get_commits(repo, limit):
        slug = commit_extract._make_slug(commit["hash"])
        if _entry_exists(repo, slug):
            skipped += 1
            continue
        if not dry_run:
            _write_entry(repo, slug, commit)
        populated += 1
    return populated, skipped


def _build_arg_parser():
    parser = argparse.ArgumentParser(
        description="Seed Agent Nelly memory with inferred technique entries mined from existing git commit history."
    )
    parser.add_argument(
        "--repo",
        action="append",
        dest="repos",
        metavar="PATH",
        help="Path to a git repo to scan (repeatable). Defaults to auto-discovering repos under "
        "$NELLY_REPO_BASE (or ~/Codebase) up to 2 directory levels deep.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=_DEFAULT_LIMIT,
        help=f"Max commits to scan per repo, most recent first (default {_DEFAULT_LIMIT}).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview counts without writing entries or rebuilding the index.",
    )
    return parser


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    args = _build_arg_parser().parse_args(argv)

    repos = args.repos
    if not repos:
        base = os.path.expanduser(os.environ.get("NELLY_REPO_BASE") or _DEFAULT_BASE)
        repos = discover_repos(base)
        if not repos:
            print(f"[nelly] no git repos found under {base}")
            return

    any_written = False
    for repo in repos:
        populated, skipped = populate_repo(repo, args.limit, args.dry_run)
        if populated and not args.dry_run:
            any_written = True
        print(f"[nelly] populated {populated} entries from {repo} ({skipped} skipped as duplicates)")

    if any_written:
        build_index.build_all()


if __name__ == "__main__":
    main()
