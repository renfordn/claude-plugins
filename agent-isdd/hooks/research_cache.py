"""Pure helper for validating research/cache.md's file_summaries against the working tree.

Used by agent-tdd's Research Validation phase (and, in a future slice, design-author's reuse
decision) to determine which cached file summaries are stale -- i.e. the file's current git blob
hash no longer matches the git_hash recorded when the summary was captured -- versus which are
still valid and safe to reuse as-is without re-research.

Kept dependency-free (stdlib only), mirroring diff_fingerprint.py's pattern of shelling out to
`git` via subprocess rather than doing a full `git diff`.
"""
import subprocess
import time


def _current_blob_hash(repo_root, path, timeout=10):
    """Return `git hash-object <path>`'s output for path (relative to repo_root), or None.

    None means "cannot verify" -- e.g. the file no longer exists, isn't readable, or git itself
    errors -- never a fabricated hash that could coincidentally equal a stored one.
    """
    try:
        result = subprocess.run(
            ["git", "hash-object", path],
            cwd=repo_root,
            capture_output=True,
            timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError):
        return None

    if result.returncode != 0:
        return None

    return result.stdout.decode("utf-8", errors="replace").strip()


def classify_summaries(file_summaries, project_root, deadline_s=None):
    """Split file_summaries into still_applicable / needs_recheck / unknown (input order kept).

    still_applicable: recorded git_hash equals the current blob hash.
    needs_recheck: current hash is known and differs from the recorded one.
    unknown: no path, no recorded hash, or the current hash can't be determined.
    deadline_s: optional overall time budget in seconds (None = unlimited); once spent, the
    remaining summaries are unknown and each git call's timeout is min(10, remaining).
    Never mutates the input.
    """
    result = {"still_applicable": [], "needs_recheck": [], "unknown": []}
    end = None if deadline_s is None else time.monotonic() + deadline_s
    for summary in file_summaries:
        path = summary.get("path")
        recorded_hash = summary.get("git_hash")
        timeout = 10
        if end is not None:
            remaining = end - time.monotonic()
            if remaining <= 0:
                result["unknown"].append(summary)
                continue
            timeout = min(10, remaining)
        current_hash = _current_blob_hash(project_root, path, timeout) if path else None
        if current_hash is None or not recorded_hash:
            result["unknown"].append(summary)
        elif current_hash == recorded_hash:
            result["still_applicable"].append(summary)
        else:
            result["needs_recheck"].append(summary)
    return result


def find_stale_summaries(file_summaries, project_root):
    """Return the subset of file_summaries whose recorded git_hash is stale.

    A summary is stale when its `git_hash` field doesn't match `git hash-object <path>`'s
    current output for `path` (resolved relative to project_root) -- including when the file's
    current hash can't be determined at all (e.g. deleted, unreadable, or a git error), since
    that's "cannot confirm cached data is safe to reuse", not "confirmed valid".

    file_summaries: list of dicts per the file_summary schema in INTEROP.md (path, git_hash,
    plus other fields this function ignores). project_root: git repo root the paths are
    relative to.

    Returns a new list in the same order as the input; never mutates file_summaries. Returns
    an empty list, without error, when file_summaries is empty.
    """
    file_summaries = list(file_summaries)
    classified = classify_summaries(file_summaries, project_root)
    flagged = {id(x) for x in classified["needs_recheck"] + classified["unknown"]}
    return [summary for summary in file_summaries if id(summary) in flagged]
