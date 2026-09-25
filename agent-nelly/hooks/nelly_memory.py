#!/usr/bin/env python3
"""Core path-resolution primitives for Agent Nelly's independent memory store.

Memory lives under <root>/agent-nelly-memory/<project-slug>/, where <root> is the user's
`shared_memory_root` plugin option when set (one store for every plugin identity and machine
pointed at it) and ${CLAUDE_PLUGIN_DATA} otherwise — a NEW root,
structurally independent from SDD's sdd-memory/. Every other file in
this plugin resolves paths by calling into this module; nothing hand-computes a
path under BASE (see hooks/nelly_slug_guard.py, Phase 4).

Phase 2 of the module: project_slug, memory_dir, ensure_dir, read_index,
global_dir, read_global_index. Phase 3 (this revision) adds the entry-file
API — entry_path, archive_path, list_entries — and the CLI dispatch surface
(--path, --global-path, --summary, --entries-path, --summary-entries-path).

ensure_entries_dir(cwd) exists because entry_path()/archive_path() are pure
path-string builders with no directory-creation side effect, and ensure_dir()
only creates the top-level project dir + MEMORY.md, never entries/. Any
write-back that creates or overwrites entries/<name>.md MUST call
ensure_entries_dir(cwd) first (see agent-nelly.md's "Recording a new
fact" and "Import" sections) — this was previously missing, which let the
MEMORY.md index get a new line while the entry file itself silently never
got created.
"""
import os
import re
import sys

# Import shared utilities
from shared_slug import get_project_slug

# path_resolution.py lives alongside this file (a per-plugin copy -- see its own
# docstring for why it isn't imported from a monorepo-relative shared/ directory).
_this_dir = os.path.dirname(os.path.abspath(__file__))
if _this_dir not in sys.path:
    sys.path.insert(0, _this_dir)
from path_resolution import (  # noqa: E402
    get_plugin_data_dir, get_legacy_subdir_path, get_memory_root, get_shared_memory_root,
    ensure_shared_root_scaffold,
)

# BASE holds the syncable store (MEMORY.md, entries/, archive/, global/): the user's
# shared_memory_root option when set, else ${CLAUDE_PLUGIN_DATA}. LOCAL_BASE is always
# ${CLAUDE_PLUGIN_DATA} and holds machine-local churn (hotspots.json) that must never be synced
# -- see local_state_dir(). The two are the same directory when no shared root is configured.
SHARED_ROOT = get_shared_memory_root()
BASE = get_legacy_subdir_path(get_memory_root("agent-nelly"), "agent-nelly-memory")
LOCAL_BASE = get_legacy_subdir_path(get_plugin_data_dir("agent-nelly"), "agent-nelly-memory")


# Backward compatibility: alias to shared implementation
def project_slug(cwd):
    """Deterministic collision-resistant slug from an absolute project path.

    Delegated to shared_slug.get_project_slug() for consolidation across
    agent-nelly, agent-isdd, and agent-tdd.
    """
    return get_project_slug(cwd)


def memory_dir(cwd):
    return os.path.join(BASE, project_slug(cwd))


def local_state_dir(cwd):
    """Machine-local per-project dir for high-churn state (hotspots.json).

    Always under ${CLAUDE_PLUGIN_DATA}, even when a shared memory root is configured:
    hotspots.json is rewritten on every Read/Write, so syncing it would make every machine
    rewrite the same file constantly. Equal to memory_dir(cwd) when no shared root is set.
    """
    return os.path.join(LOCAL_BASE, project_slug(cwd))


def ensure_shared_root():
    """Scaffold the shared memory root (.gitignore/.gitattributes) when one is configured."""
    if SHARED_ROOT:
        ensure_shared_root_scaffold(SHARED_ROOT)


def _write_index_header(index_path, lines):
    if not os.path.exists(index_path):
        with open(index_path, "w", encoding="utf-8") as fh:
            fh.write(lines)


def ensure_dir(cwd):
    d = memory_dir(cwd)
    os.makedirs(d, exist_ok=True)
    index = os.path.join(d, "MEMORY.md")
    _write_index_header(
        index,
        f"# Agent Nelly Memory Index\n\n"
        f"Project: {os.path.abspath(cwd)}\n\n"
        f"One line per memory entry: `- [Title](file.md) — hook`\n\n",
    )
    return d


def read_index(cwd):
    index = os.path.join(memory_dir(cwd), "MEMORY.md")
    try:
        with open(index, "r", encoding="utf-8") as fh:
            return fh.read().strip()
    except OSError:
        return ""


def global_dir():
    """The single cross-project tier, sibling to every per-project dir under BASE.

    Unlike memory_dir(), this takes no cwd — there is exactly one global/
    directory, not one per project.
    """
    d = os.path.join(BASE, "global")
    os.makedirs(d, exist_ok=True)
    index = os.path.join(d, "GLOBAL-MEMORY.md")
    _write_index_header(
        index,
        "# Agent Nelly Global Memory\n\n"
        "Cross-project facts promoted from per-project memory.\n\n",
    )
    return d


def read_global_index():
    index = os.path.join(global_dir(), "GLOBAL-MEMORY.md")
    try:
        with open(index, "r", encoding="utf-8") as fh:
            return fh.read().strip()
    except OSError:
        return ""


# file-summary/folder-summary entries nest one level deeper than every other entry type, under
# entries/<SUMMARY_SUBDIR>/ instead of directly under entries/ -- they're a path-keyed cache
# (one entry per file/folder, overwritten in place, never archived or promoted -- see "File &
# Folder Summary Cache" in agents/agent-nelly.md), not a fact, so keeping them out of the flat
# entries/ listing every other type shares (user/feedback/project/reference/file-relevance/
# error-prevention/technique) makes that listing legible again as "things Nelly was told", not
# "things Nelly was told, plus one row per cached file in the repo".
SUMMARY_SUBDIR = "file-folder-summary"
SUMMARY_TYPES = ("file-summary", "folder-summary")


def _sanitize_name(name):
    """Reduce name to a single safe path segment — never lets '..' or a
    separator (either '/' or '\\', regardless of host OS) escape the
    directory entry_path()/archive_path() build it under.
    """
    parts = re.split(r"[\\/]+", str(name))
    candidates = [p for p in parts if p not in ("", ".", "..")]
    return candidates[-1] if candidates else "unnamed"


def entry_path(cwd, name, entry_type=None):
    """Resolve an entry's file path. `entry_type` of "file-summary"/"folder-summary" nests the
    path under entries/<SUMMARY_SUBDIR>/ (see SUMMARY_SUBDIR above); every other type (including
    the default, `entry_type=None`, used by every existing caller that predates this parameter)
    stays directly under entries/, unchanged.
    """
    base = os.path.join(memory_dir(cwd), "entries")
    if entry_type in SUMMARY_TYPES:
        base = os.path.join(base, SUMMARY_SUBDIR)
    return os.path.join(base, _sanitize_name(name) + ".md")


def ensure_entries_dir(cwd, entry_type=None):
    """Guarantee `<memory_dir>/entries/` (or, for `entry_type` "file-summary"/"folder-summary",
    `<memory_dir>/entries/<SUMMARY_SUBDIR>/`) exists before anything writes into it.

    ensure_dir() only creates the top-level project dir + MEMORY.md — it never
    touches entries/. Without this, a Write to entry_path(cwd, name) has no
    guarantee its parent directory exists, which was the root cause of a bug
    where the MEMORY.md index got a new line while entries/<name>.md was
    never actually created on disk. Every write-back path that writes a new
    or overwritten entry file must call this first, exactly as the file-move
    mechanism already does `mkdir -p` for archive/ before moving into it.
    """
    ensure_dir(cwd)
    d = os.path.join(memory_dir(cwd), "entries")
    os.makedirs(d, exist_ok=True)
    if entry_type in SUMMARY_TYPES:
        d = os.path.join(d, SUMMARY_SUBDIR)
        os.makedirs(d, exist_ok=True)
    return d


def archive_path(cwd, name):
    return os.path.join(memory_dir(cwd), "archive", _sanitize_name(name) + ".md")


# `file-summary`/`folder-summary` entry type character cap (see
# references/nelly-entry.template.md and nelly_summary_guard.py, which
# enforces this structurally on every Write to an entries/*.md file of
# either type). 240 chars keeps a whole screenful of cached summaries
# scannable at once -- the entire point of the file/folder summary cache is
# a smaller place to look first instead of grepping the whole repo.
SUMMARY_CHAR_LIMIT = 240


def truncate_summary(text, limit=SUMMARY_CHAR_LIMIT):
    """Deterministically cap a file-summary/folder-summary `description` at
    `limit` characters.

    Returns `text` (stripped of leading/trailing whitespace) unchanged when
    it already fits. Otherwise truncates to `limit - 1` characters and
    appends a single `…` character (not three ASCII dots), so the result is
    always exactly `limit` characters long, never `limit + 2`.
    """
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def resolve_repo_relative(cwd, path):
    """Resolve a stored repo-relative path back to an absolute path anchored
    at cwd. Pure path resolution — no entry-file I/O. Used by
    agent-nelly's prose logic (via Bash/Glob, not by any hook) during
    `/nelly-memory prune`'s file-existence check for `file-relevance` entries
    whose `metadata.files` paths are stored relative to cwd (never absolute,
    since a project can be checked out at different absolute paths across
    machines/worktrees).

    Raises ValueError if `path` is itself absolute — os.path.join would
    otherwise silently discard `cwd` and return `path` unchanged, masking a
    metadata.files entry that violated the never-absolute invariant instead
    of surfacing it.
    """
    if os.path.isabs(path):
        raise ValueError(f"resolve_repo_relative: path must be repo-relative, got absolute path {path!r}")
    return os.path.normpath(os.path.join(cwd, path))


def write_index_line(cwd, name, hook, type, confidence=None, files_present=False, paths=None):
    """Append and return a field-annotated `MEMORY.md` index line.

    Title is derived from `name` (the entry's filename stem, kebab-case by
    convention — see entry_path()) by replacing hyphens with spaces and
    title-casing, matching the shape already used by hand-authored index
    lines elsewhere in this module's tests/docs (e.g. `some-test-fact` ->
    `Some Test Fact`). The link target is always `entries/<name>.md`, the
    same location entry_path(cwd, name) resolves to.

    `type` is required (no default) and always appears in the trailing
    `` `[...]` `` field block; `confidence`/`files_present`/`paths` are
    optional and each contribute their own `confidence:`/`files:`/`paths:`
    fragment to that same block only when provided/true/non-empty — never
    emitted at all otherwise. `paths` is a list of repo-relative path
    strings joined with `;` (a single repo-relative path can't contain a
    semicolon but could contain a comma). Old lines with no block remain
    valid (see parse_index_line_fields()).
    """
    d = ensure_dir(cwd)
    title = name.replace("-", " ").replace("_", " ").title()
    fields = [f"type:{type}"]
    if confidence is not None:
        fields.append(f"confidence:{confidence}")
    if files_present:
        fields.append("files:yes")
    if paths:
        fields.append(f"paths:{';'.join(paths)}")
    line = f"- [{title}](entries/{name}.md) — {hook} `[{' '.join(fields)}]`"

    index = os.path.join(d, "MEMORY.md")
    with open(index, "a", encoding="utf-8") as fh:
        fh.write(line + "\n")
    return line


_INDEX_LINE_FIELD_BLOCK_RE = re.compile(
    r"`\[type:(?P<type>\S+)(?: confidence:(?P<confidence>\S+))?(?: files:(?P<files>\S+))?"
    r"(?: paths:(?P<paths>\S+))?\]`\s*$"
)


def parse_index_line_fields(line):
    """Parse a `MEMORY.md` index line's optional trailing field block.

    Returns a dict with keys `type`/`confidence`/`files`/`paths`. Old-format
    lines (no trailing `` `[...]` `` block) return all-`None` — "unknown",
    never an error and never mistaken for an explicit exclusion signal.
    `paths`, when present, is split on `;` into a list of repo-relative path
    strings; when absent it is `None` (falls back to no-match downstream,
    never an error).
    """
    match = _INDEX_LINE_FIELD_BLOCK_RE.search(line)
    if not match:
        return {"type": None, "confidence": None, "files": None, "paths": None}
    paths = match.group("paths")
    return {
        "type": match.group("type"),
        "confidence": match.group("confidence"),
        "files": match.group("files"),
        "paths": paths.split(";") if paths is not None else None,
    }


def list_entries(cwd):
    d = os.path.join(memory_dir(cwd), "entries")
    try:
        names = os.listdir(d)
    except OSError:
        return []
    return sorted(n[:-3] for n in names if n.endswith(".md"))


def _extract_cwd_arg(argv, flag):
    if flag in argv:
        idx = argv.index(flag)
        if idx + 1 < len(argv):
            return argv[idx + 1]
    return os.getcwd()


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)

    if "--global-path" in argv:
        print(global_dir())
        return

    if "--summary" in argv:
        cwd = _extract_cwd_arg(argv, "--summary")
        idx = read_index(cwd)
        if re.search(r"^\s*-\s*\[", idx, re.M):
            print(idx)
        return

    if "--path" in argv:
        cwd = _extract_cwd_arg(argv, "--path")
        print(ensure_dir(cwd))
        return

    if "--entries-path" in argv:
        cwd = _extract_cwd_arg(argv, "--entries-path")
        print(ensure_entries_dir(cwd))
        return

    if "--summary-entries-path" in argv:
        cwd = _extract_cwd_arg(argv, "--summary-entries-path")
        print(ensure_entries_dir(cwd, entry_type="file-summary"))
        return

    cwd = argv[0] if argv else os.getcwd()
    print(memory_dir(cwd))


if __name__ == "__main__":
    main()
