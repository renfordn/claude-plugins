#!/usr/bin/env python3
"""Bloat cleanup for Agent Nelly's memory store, run by nelly_weekly_consolidate.py.

Two deterministic passes, no LLM:

1. Orphaned worktree stores. A project slug comes from the absolute path, so every git worktree
   (`<repo>/.claude/worktrees/<name>`) gets its own store, which outlives the worktree. A store
   whose slug contains `-claude-worktrees-` is merged into its parent repo's store (the slug
   prefix before that marker) once the worktree path no longer exists on this machine AND
   nothing in the store changed for WORKTREE_IDLE_DAYS -- the idle check matters with a shared
   memory root, where a worktree that's missing here may be live on another machine.
   Entries move across (renamed `<name>--<worktree>.md` on a clash with different content),
   index lines are unioned into the parent's MEMORY.md, logs are appended, and the worktree
   store is removed.

2. Session-handoff rollup. nelly_session_end.py writes one `session-handoff-<date>-<time>`
   entry per editing session and nothing ever retires them. Per project, the newest
   HANDOFF_KEEP stay as entries; older ones that are at least HANDOFF_MIN_AGE_DAYS old become
   one line each in SESSION-HISTORY.md (append-only, union-merged by git) and their entry
   files and index lines are removed.

Both passes append what they did to the project's CONSOLIDATION-LOG.md.
"""
import datetime
import filecmp
import os
import re
import shutil
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "hooks"))
from nelly_memory import BASE  # noqa: E402
from shared_slug import get_project_slug  # noqa: E402

WORKTREE_MARKER = "-claude-worktrees-"
WORKTREE_IDLE_DAYS = 14
HANDOFF_KEEP = 5
HANDOFF_MIN_AGE_DAYS = 14

SESSION_HISTORY_NAME = "SESSION-HISTORY.md"
SESSION_HISTORY_HEADER = (
    "# Session History\n\n"
    "One line per past session, rolled up from `session-handoff-*` entries by the weekly "
    "consolidation (scripts/nelly_cleanup.py). Append-only.\n\n"
)
CONSOLIDATION_LOG_HEADER = (
    "# Consolidation Log\n\n"
    "Append-only history of consolidation-related actions taken against this "
    "project's memory store.\n\n"
    "## Log\n"
)
# Derived or machine-local -- never carried from a worktree store into its parent.
_DROP_ON_MERGE = {"nelly-index.json", "hotspots.json"}

_HANDOFF_RE = re.compile(r"^session-handoff-(\d{4}-\d{2}-\d{2})-(\d{2})(\d{2})(?:-\d+)?\.md$")
_PROJECT_RE = re.compile(r"^Project:\s*(.+)$", re.M)
_DESCRIPTION_RE = re.compile(r"^description:\s*(.+)$", re.M)
_LAST_COMMIT_RE = re.compile(r"^Last commit:\s*(.+)$", re.M)


def _now_stamp():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _read(path):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return ""


def _append(path, text, header=""):
    new = not os.path.exists(path)
    with open(path, "a", encoding="utf-8") as fh:
        if new and header:
            fh.write(header)
        fh.write(text)


def _log_action(project_dir, action, lines):
    body = f"\n### {_now_stamp()}\n- Action: {action}\n" + "".join(f"- {ln}\n" for ln in lines)
    body += "- Trigger: scheduled weekly consolidation (scripts/nelly_cleanup.py)\n"
    _append(os.path.join(project_dir, "CONSOLIDATION-LOG.md"), body, CONSOLIDATION_LOG_HEADER)


def _newest_mtime(d):
    newest = 0.0
    for root, _, files in os.walk(d):
        for f in files:
            if f in _DROP_ON_MERGE or f == ".DS_Store" or f.endswith((".lock", ".tmp")):
                continue  # derived/machine-local churn, not real activity
            try:
                newest = max(newest, os.path.getmtime(os.path.join(root, f)))
            except OSError:
                pass
    return newest


def _idle_days(d, today):
    newest = _newest_mtime(d)
    if not newest:
        return None
    return (today - datetime.date.fromtimestamp(newest)).days


def _index_lines(text):
    return [ln for ln in text.splitlines() if ln.startswith("- [")]


def _remove_index_lines_for(memory_md, filenames):
    text = _read(memory_md)
    if not text:
        return
    pats = [f"](entries/{name})" for name in filenames]
    kept = [ln for ln in text.splitlines(keepends=True) if not any(p in ln for p in pats)]
    with open(memory_md, "w", encoding="utf-8") as fh:
        fh.writelines(kept)


def _handoff_line(entry_path, date, hhmm, suffix=""):
    text = _read(entry_path)
    desc_m = _DESCRIPTION_RE.search(text)
    desc = desc_m.group(1).strip() if desc_m else "(no description)"
    desc = re.sub(r"^Session ended -- ", "", desc)
    commit_m = _LAST_COMMIT_RE.search(text)
    commit = f" Last commit: {commit_m.group(1).strip()}." if commit_m else ""
    return f"- {date} {hhmm[:2]}:{hhmm[2:]}{suffix} — {desc}{commit}\n"


# ---------------------------------------------------------------------------
# Session-handoff rollup
# ---------------------------------------------------------------------------

def roll_up_session_handoffs(project_dir, today, keep=HANDOFF_KEEP,
                             min_age_days=HANDOFF_MIN_AGE_DAYS, dry_run=False):
    """Returns the list of handoff filenames rolled up (or that would be, on a dry run)."""
    entries_dir = os.path.join(project_dir, "entries")
    try:
        names = os.listdir(entries_dir)
    except OSError:
        return []
    handoffs = []
    for name in names:
        m = _HANDOFF_RE.match(name)
        if m:
            handoffs.append((m.group(1), m.group(2) + m.group(3), name))
    handoffs.sort(reverse=True)  # newest first; the timestamp sorts lexically
    candidates = []
    for date, hhmm, name in handoffs[keep:]:
        try:
            age = (today - datetime.date.fromisoformat(date)).days
        except ValueError:
            continue
        if age >= min_age_days:
            candidates.append((date, hhmm, name))
    if not candidates or dry_run:
        return [name for _, _, name in candidates]

    history = os.path.join(project_dir, SESSION_HISTORY_NAME)
    lines = [_handoff_line(os.path.join(entries_dir, name), date, hhmm)
             for date, hhmm, name in sorted(candidates)]
    _append(history, "".join(lines), SESSION_HISTORY_HEADER)
    for _, _, name in candidates:
        os.remove(os.path.join(entries_dir, name))
    _remove_index_lines_for(os.path.join(project_dir, "MEMORY.md"), [n for _, _, n in candidates])
    _log_action(project_dir, "rolled-up-session-handoffs", [
        f"Entries: {len(candidates)} session-handoff entries older than {min_age_days} days "
        f"(newest {keep} kept)",
        f"Summary: one line each appended to {SESSION_HISTORY_NAME}; entry files removed",
    ])
    return [name for _, _, name in candidates]


# ---------------------------------------------------------------------------
# Orphaned worktree stores
# ---------------------------------------------------------------------------

def _worktree_parts(slug):
    if WORKTREE_MARKER not in slug:
        return None
    parent, label = slug.split(WORKTREE_MARKER, 1)
    if not parent or not label:
        return None
    return parent, label


def _worktree_path(store_dir):
    m = _PROJECT_RE.search(_read(os.path.join(store_dir, "MEMORY.md")))
    return m.group(1).strip() if m else None


def find_orphaned_worktree_stores(base, today, idle_days=WORKTREE_IDLE_DAYS):
    """Return (store_dir, parent_slug, label, skip_reason) for every worktree store.

    skip_reason is None for stores that should be merged now.
    """
    out = []
    try:
        slugs = sorted(os.listdir(base))
    except OSError:
        return out
    for slug in slugs:
        store = os.path.join(base, slug)
        parts = _worktree_parts(slug)
        if not parts or not os.path.isdir(store):
            continue
        parent, label = parts
        path = _worktree_path(store)
        if path and "/.claude/worktrees/" in path:
            # `<repo>/.claude/worktrees/<name>[/<sub>]` belongs to `<repo>[/<sub>]`.
            repo, rest = path.split("/.claude/worktrees/", 1)
            sub = rest.split("/", 1)[1] if "/" in rest else ""
            parent = get_project_slug(repo + ("/" + sub if sub else ""))
            label = rest.split("/", 1)[0]
        reason = None
        if path and os.path.exists(path):
            reason = "worktree still exists on this machine"
        else:
            idle = _idle_days(store, today)
            if idle is not None and idle < idle_days:
                reason = f"changed {idle} day(s) ago (waits until {idle_days} idle)"
        out.append((store, parent, label, reason))
    return out


def _unique_dest(dest_dir, name, label):
    stem, ext = os.path.splitext(name)
    candidate = f"{stem}--{label}{ext}"
    n = 2
    while os.path.exists(os.path.join(dest_dir, candidate)):
        candidate = f"{stem}--{label}-{n}{ext}"
        n += 1
    return candidate


def _ensure_parent_store(parent_dir, worktree_path):
    os.makedirs(os.path.join(parent_dir, "entries"), exist_ok=True)
    index = os.path.join(parent_dir, "MEMORY.md")
    if not os.path.exists(index):
        project = "unknown"
        if worktree_path and "/.claude/worktrees/" in worktree_path:
            repo, rest = worktree_path.split("/.claude/worktrees/", 1)
            project = repo + ("/" + rest.split("/", 1)[1] if "/" in rest else "")
        with open(index, "w", encoding="utf-8") as fh:
            fh.write(
                f"# Agent Nelly Memory Index\n\nProject: {project}\n\n"
                f"One line per memory entry: `- [Title](file.md) — hook`\n\n"
            )


def merge_worktree_store(store, parent_slug, label, base=None):
    """Fold one worktree store into its parent repo's store and remove it. Returns a summary."""
    base = base or BASE
    parent_dir = os.path.join(base, parent_slug)
    _ensure_parent_store(parent_dir, _worktree_path(store))
    moved, renamed, dropped, handoffs = [], [], [], []

    # entries/: session handoffs go straight to the parent's history; the rest move across.
    entries = os.path.join(store, "entries")
    renames = {}
    history_lines = []
    for name in sorted(os.listdir(entries)) if os.path.isdir(entries) else []:
        src = os.path.join(entries, name)
        m = _HANDOFF_RE.match(name)
        if m:
            history_lines.append(_handoff_line(src, m.group(1), m.group(2) + m.group(3),
                                               f" (worktree {label})"))
            handoffs.append(name)
            continue
        dest_dir = os.path.join(parent_dir, "entries")
        dest = os.path.join(dest_dir, name)
        if not os.path.exists(dest):
            shutil.move(src, dest)
            moved.append(name)
        elif filecmp.cmp(src, dest, shallow=False):
            dropped.append(name)
        else:
            new_name = _unique_dest(dest_dir, name, label)
            shutil.move(src, os.path.join(dest_dir, new_name))
            renames[name] = new_name
            renamed.append(f"{name} -> {new_name}")
    if history_lines:
        _append(os.path.join(parent_dir, SESSION_HISTORY_NAME), "".join(sorted(history_lines)),
                SESSION_HISTORY_HEADER)

    # MEMORY.md: union the index lines (retargeting renamed entries, skipping handoffs).
    parent_index = os.path.join(parent_dir, "MEMORY.md")
    have = set(_index_lines(_read(parent_index)))
    add = []
    for ln in _index_lines(_read(os.path.join(store, "MEMORY.md"))):
        if any(f"](entries/{h})" in ln for h in handoffs):
            continue
        for old, new in renames.items():
            ln = ln.replace(f"](entries/{old})", f"](entries/{new})")
        if ln not in have:
            add.append(ln)
            have.add(ln)
    if add:
        _append(parent_index, "\n".join(add) + "\n")

    # archive/: move across, renaming on clash.
    archive = os.path.join(store, "archive")
    if os.path.isdir(archive):
        dest_dir = os.path.join(parent_dir, "archive")
        os.makedirs(dest_dir, exist_ok=True)
        for name in sorted(os.listdir(archive)):
            dest_name = name if not os.path.exists(os.path.join(dest_dir, name)) \
                else _unique_dest(dest_dir, name, label)
            shutil.move(os.path.join(archive, name), os.path.join(dest_dir, dest_name))

    # Everything else at the top level: append logs/histories, carry other files across.
    for name in sorted(os.listdir(store)):
        src = os.path.join(store, name)
        if name in ("MEMORY.md", "entries", "archive") or name in _DROP_ON_MERGE:
            continue
        dest = os.path.join(parent_dir, name)
        if os.path.isdir(src):
            if not os.path.exists(dest):
                shutil.move(src, dest)
            else:
                shutil.move(src, os.path.join(parent_dir, _unique_dest(parent_dir, name, label)))
        elif not os.path.exists(dest):
            shutil.move(src, dest)
        elif name.endswith((".md", ".jsonl")):
            _append(dest, f"\n<!-- merged from worktree {label} -->\n" + _read(src))
        else:
            shutil.move(src, os.path.join(parent_dir, _unique_dest(parent_dir, name, label)))

    shutil.rmtree(store)
    summary = {
        "store": os.path.basename(store), "parent": parent_slug, "label": label,
        "moved": moved, "renamed": renamed, "dropped_identical": dropped, "handoffs": handoffs,
        "index_lines_added": len(add),
    }
    _log_action(parent_dir, "merged-worktree-store", [
        f"Source: {os.path.basename(store)} (worktree `{label}`, no longer on disk)",
        f"Entries: {len(moved)} moved, {len(renamed)} renamed on clash, "
        f"{len(dropped)} identical dropped, {len(handoffs)} session handoffs rolled into "
        f"{SESSION_HISTORY_NAME}",
        "Store removed after merge",
    ])
    return summary


def run_cleanup(today, dry_run=False, base=None, idle_days=WORKTREE_IDLE_DAYS):
    """Worktree merges first (so their handoffs join the parent), then handoff rollups."""
    base = base or BASE
    result = {"merged": [], "skipped_worktrees": [], "would_merge": [], "rolled_up": {}}
    for store, parent, label, reason in find_orphaned_worktree_stores(base, today, idle_days):
        if reason:
            result["skipped_worktrees"].append((os.path.basename(store), reason))
        elif dry_run:
            result["would_merge"].append((os.path.basename(store), parent))
        else:
            result["merged"].append(merge_worktree_store(store, parent, label, base))

    for slug in sorted(os.listdir(base)) if os.path.isdir(base) else []:
        d = os.path.join(base, slug)
        if slug == "global" or not os.path.isdir(os.path.join(d, "entries")):
            continue
        rolled = roll_up_session_handoffs(d, today, dry_run=dry_run)
        if rolled:
            result["rolled_up"][slug] = rolled
    return result


def render_cleanup_section(result, dry_run):
    lines = ["## Cleanup", ""]
    verb = "Would merge" if dry_run else "Merged"
    merged = result["would_merge"] if dry_run else [(m["store"], m["parent"]) for m in result["merged"]]
    lines.append(f"- {verb} {len(merged)} orphaned worktree store(s) into their parent repo's store")
    for store, parent in merged:
        lines.append(f"  - `{store}` -> `{parent}`")
    for store, reason in result["skipped_worktrees"]:
        lines.append(f"  - kept `{store}`: {reason}")
    rolled = result["rolled_up"]
    total = sum(len(v) for v in rolled.values())
    verb = "Would roll up" if dry_run else "Rolled up"
    lines.append(f"- {verb} {total} old session-handoff entr{'y' if total == 1 else 'ies'} "
                 f"into {SESSION_HISTORY_NAME} (newest {HANDOFF_KEEP} per project kept)")
    for slug, names in rolled.items():
        lines.append(f"  - `{slug}`: {len(names)}")
    lines.append("")
    return lines
