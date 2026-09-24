#!/usr/bin/env python3
"""Unattended bloat cleanup for agent-isdd's per-feature SDD state (no LLM, no prompts).

Two passes over sdd_memory.BASE (the shared_memory_root option when set, else
${CLAUDE_PLUGIN_DATA}/sdd-memory):

1. Orphaned worktree stores. A project slug comes from the absolute path, so a git worktree
   (`<repo>/.claude/worktrees/<name>`) gets its own `<repo-slug>-claude-worktrees-<name>...`
   store that outlives it. Once nothing in such a store changed for IDLE_DAYS, its spec/
   features move into the parent repo's store (renamed `<feature>--<worktree>` on a clash),
   RUN-LOG.jsonl and DOC-AUDIT-HISTORY.md are appended to the parent's, the worktree's own
   DOC-AUDIT-STATE.md snapshot is dropped, and the store is removed. (SDD stores record no
   project path, so unlike agent-nelly there is no "does the worktree still exist" check --
   idleness alone decides.)

2. Completed features. `Workflow Status: Complete` only means SDD planning handed off --
   implementation often keeps going against tasks.md for days. So a feature is condensed only
   once it is Complete AND nothing in its folder changed for IDLE_DAYS. It becomes one
   `completed/<feature>.md` summary (goal, success signals, decisions, open follow-ups,
   commits, final state), and requirements/, design/, tasks/, recap/, intent/ and
   workflow-state.* are deleted.

Every action is appended to the project's CLEANUP-LOG.md, and a report is written to
`<BASE>/cleanup-reports/YYYY-MM-DD.md`. Each summary starts as `nelly_recorded: no`; the next
session in that project sees it via hooks/session_start.py, passes it to agent-nelly as
`new facts` (a scheduled session can't -- agent-nelly's slug guard only allows writes to the
session's own project), and flips the flag to `yes`.

Usage:
    CLAUDE_PLUGIN_DATA=... [CLAUDE_PLUGIN_OPTION_SHARED_MEMORY_ROOT=...] \\
        python3 sdd_cleanup.py [--dry-run] [--idle-days N]
"""
import argparse
import datetime
import os
import re
import shutil
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "hooks"))
from sdd_memory import BASE  # noqa: E402

IDLE_DAYS = 14
WORKTREE_MARKER = "-claude-worktrees-"
COMPLETED_DIR = "completed"
REPORT_DIR_NAME = "cleanup-reports"
MAX_ITEM_CHARS = 300
CLEANUP_LOG_HEADER = (
    "# SDD Cleanup Log\n\n"
    "Append-only record of what scripts/sdd_cleanup.py condensed, merged, or removed.\n"
)
# Files a worktree store's state is appended to (not replaced) in the parent's store.
_APPEND_ON_MERGE = ("RUN-LOG.jsonl", "DOC-AUDIT-HISTORY.md", "CLEANUP-LOG.md")
# A worktree's own point-in-time snapshots -- the parent keeps its own.
_DROP_ON_MERGE = ("DOC-AUDIT-STATE.md", "last-stop.json", "snapshots")

_FIELD_RE = r"^-\s*{}:\s*(.+)$"
_COMMIT_RE = re.compile(r"`([0-9a-f]{7,12})`")


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


def _log(project_dir, action, lines):
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    body = f"\n### {stamp}\n- Action: {action}\n" + "".join(f"- {ln}\n" for ln in lines)
    _append(os.path.join(project_dir, "CLEANUP-LOG.md"), body, CLEANUP_LOG_HEADER)


def _field(text, name):
    m = re.search(_FIELD_RE.format(re.escape(name)), text, re.M | re.I)
    return m.group(1).strip() if m else ""


def _section(text, heading):
    """Body of `## heading` up to the next `## ` heading."""
    m = re.search(r"^##\s+" + re.escape(heading) + r"\s*$(.*?)(?=^##\s|\Z)", text, re.M | re.S | re.I)
    return m.group(1).strip() if m else ""


def _bullets(body, unchecked_only=False):
    items = []
    for ln in body.splitlines():
        s = ln.strip()
        if unchecked_only:
            if not s.startswith("- [ ]"):
                continue
            s = s[len("- [ ]"):].strip()
        elif s.startswith("- "):
            s = re.sub(r"^- (\[[ x]\] )?", "", s)
        else:
            continue
        if len(s) > MAX_ITEM_CHARS:
            s = s[:MAX_ITEM_CHARS].rstrip() + "…"
        items.append(s)
    return items


# Written by hooks on every tool call or subagent stop (plugin-harness telemetry/state sync,
# hooks/subagent_report.py, file locks) -- into whichever feature looks newest, even a Complete
# one -- so they say nothing about whether anyone is still working on it.
_BOOKKEEPING = ("workflow-state.json", "hook_telemetry_log.jsonl", "subagent-reports.md", ".DS_Store")


def _newest_mtime(d):
    newest = 0.0
    for root, _, files in os.walk(d):
        for f in files:
            if f in _BOOKKEEPING or f.endswith((".lock", ".tmp")):
                continue
            try:
                newest = max(newest, os.path.getmtime(os.path.join(root, f)))
            except OSError:
                pass
    return newest


def _idle_days(d, today):
    newest = _newest_mtime(d)
    return None if not newest else (today - datetime.date.fromtimestamp(newest)).days


def _dir_stats(d):
    count = size = 0
    for root, _, files in os.walk(d):
        for f in files:
            count += 1
            try:
                size += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return count, size


# ---------------------------------------------------------------------------
# Completed-feature summaries
# ---------------------------------------------------------------------------

def build_summary(feature_dir, project_slug, today):
    """Condense one feature folder into the text of completed/<feature>.md."""
    slug = os.path.basename(feature_dir)
    state = _read(os.path.join(feature_dir, "workflow-state.md"))
    recap = _read(os.path.join(feature_dir, "recap", "recap.md"))
    intent = _read(os.path.join(feature_dir, "intent", "intent.md"))

    title = _field(state, "Title") or slug
    goal = _section(intent, "Feature Goal") or _field(state, "Goal") or "(not recorded)"
    signals = _bullets(_section(intent, "Success Signals"))
    decisions = _bullets(_section(recap, "Decisions Made"))
    open_items = _bullets(_section(recap, "Open Items"), unchecked_only=True)
    commits = sorted(set(_COMMIT_RE.findall(recap)))
    last_updated = _field(state, "Date") or ""
    next_action = _field(state, "Next Action")
    files, size = _dir_stats(feature_dir)

    def block(heading, items):
        if not items:
            return ""
        return f"## {heading}\n\n" + "".join(f"- {i}\n" for i in items) + "\n"

    return (
        "---\n"
        f"feature: {slug}\n"
        f"title: {title}\n"
        f"project_slug: {project_slug}\n"
        "status: complete\n"
        f"last_updated: {last_updated}\n"
        f"summarized: {today.isoformat()}\n"
        "source: agent-isdd scripts/sdd_cleanup.py\n"
        "nelly_recorded: no\n"
        "---\n\n"
        f"# {title}\n\n"
        f"## Goal\n\n{goal}\n\n"
        + block("Success signals", signals)
        + block("Decisions", decisions)
        + block("Open follow-ups at close", open_items)
        + (f"## Commits\n\n{', '.join(f'`{c}`' for c in commits)}\n\n" if commits else "")
        + (f"## Final state\n\n{next_action}\n\n" if next_action and next_action != "None" else "")
        + f"_Condensed from {files} files ({size // 1024} KB): requirements, design, tasks, "
        "recap, intent and workflow state were removed after this summary was written._\n"
    )


def find_completed_features(base, today, idle_days=IDLE_DAYS):
    """Yield (project_dir, feature_dir, skip_reason); skip_reason None means condense now."""
    for project in sorted(os.listdir(base)) if os.path.isdir(base) else []:
        spec = os.path.join(base, project, "spec")
        if not os.path.isdir(spec):
            continue
        for feature in sorted(os.listdir(spec)):
            fdir = os.path.join(spec, feature)
            state = _read(os.path.join(fdir, "workflow-state.md"))
            if not state or _field(state, "Workflow Status").lower() != "complete":
                continue
            idle = _idle_days(fdir, today)
            reason = None
            if idle is not None and idle < idle_days:
                reason = f"changed {idle} day(s) ago (waits until {idle_days} idle)"
            yield os.path.join(base, project), fdir, reason


def condense_feature(project_dir, feature_dir, today):
    project_slug = os.path.basename(project_dir)
    slug = os.path.basename(feature_dir)
    out_dir = os.path.join(project_dir, COMPLETED_DIR)
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, f"{slug}.md")
    tmp = out + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(build_summary(feature_dir, project_slug, today))
    os.replace(tmp, out)  # summary is on disk before anything is removed
    files, size = _dir_stats(feature_dir)
    shutil.rmtree(feature_dir)
    _log(project_dir, "condensed-completed-feature", [
        f"Feature: {slug}",
        f"Summary: {COMPLETED_DIR}/{slug}.md",
        f"Removed: {files} files ({size // 1024} KB) of requirements/design/tasks/recap/intent/state",
    ])
    return out


# ---------------------------------------------------------------------------
# Orphaned worktree stores
# ---------------------------------------------------------------------------

def _unique(dest_dir, name, label):
    stem, ext = os.path.splitext(name)
    candidate, n = f"{stem}--{label}{ext}", 2
    while os.path.exists(os.path.join(dest_dir, candidate)):
        candidate, n = f"{stem}--{label}-{n}{ext}", n + 1
    return candidate


def find_worktree_stores(base, today, idle_days=IDLE_DAYS):
    """Yield (store_dir, parent_slug, label, skip_reason) for every worktree store."""
    for slug in sorted(os.listdir(base)) if os.path.isdir(base) else []:
        store = os.path.join(base, slug)
        if WORKTREE_MARKER not in slug or not os.path.isdir(store):
            continue
        parent, label = slug.split(WORKTREE_MARKER, 1)
        if not parent or not label:
            continue
        idle = _idle_days(store, today)
        reason = None
        if idle is not None and idle < idle_days:
            reason = f"changed {idle} day(s) ago (waits until {idle_days} idle)"
        yield store, parent, label, reason


def merge_worktree_store(store, parent_slug, label, base=None):
    base = base or BASE
    parent_dir = os.path.join(base, parent_slug)
    os.makedirs(parent_dir, exist_ok=True)
    features = []

    spec = os.path.join(store, "spec")
    if os.path.isdir(spec):
        dest_spec = os.path.join(parent_dir, "spec")
        os.makedirs(dest_spec, exist_ok=True)
        for feature in sorted(os.listdir(spec)):
            name = feature if not os.path.exists(os.path.join(dest_spec, feature)) \
                else _unique(dest_spec, feature, label)
            shutil.move(os.path.join(spec, feature), os.path.join(dest_spec, name))
            features.append(name)

    for name in sorted(os.listdir(store)):
        src = os.path.join(store, name)
        if name == "spec" or name in _DROP_ON_MERGE:
            continue
        dest = os.path.join(parent_dir, name)
        if not os.path.exists(dest):
            shutil.move(src, dest)
        elif name in _APPEND_ON_MERGE and os.path.isfile(src):
            _append(dest, _read(src))
        else:
            shutil.move(src, os.path.join(parent_dir, _unique(parent_dir, name, label)))

    shutil.rmtree(store)
    _log(parent_dir, "merged-worktree-store", [
        f"Source: {os.path.basename(store)} (worktree `{label}`)",
        f"Features moved into spec/: {', '.join(features) if features else 'none'}",
        "Store removed after merge",
    ])
    return {"store": os.path.basename(store), "parent": parent_slug, "features": features}


# ---------------------------------------------------------------------------
# Run + report
# ---------------------------------------------------------------------------

def run(today=None, dry_run=False, idle_days=IDLE_DAYS, base=None):
    today = today or datetime.date.today()
    base = base or BASE
    result = {"merged": [], "would_merge": [], "kept_worktrees": [],
              "condensed": [], "would_condense": [], "kept_features": [], "errors": []}

    for store, parent, label, reason in list(find_worktree_stores(base, today, idle_days)):
        if reason:
            result["kept_worktrees"].append((os.path.basename(store), reason))
        elif dry_run:
            result["would_merge"].append((os.path.basename(store), parent))
        else:
            try:
                result["merged"].append(merge_worktree_store(store, parent, label, base))
            except OSError as exc:
                result["errors"].append(f"{os.path.basename(store)}: merge failed ({exc})")

    for project_dir, fdir, reason in list(find_completed_features(base, today, idle_days)):
        rel = f"{os.path.basename(project_dir)}/{os.path.basename(fdir)}"
        if reason:
            result["kept_features"].append((rel, reason))
        elif dry_run:
            result["would_condense"].append(rel)
        else:
            try:
                result["condensed"].append(condense_feature(project_dir, fdir, today))
            except OSError as exc:
                result["errors"].append(f"{rel}: condense failed ({exc})")

    report = render_report(result, today, dry_run, base)
    report_dir = os.path.join(base, REPORT_DIR_NAME)
    os.makedirs(report_dir, exist_ok=True)
    path = os.path.join(report_dir, f"{today.isoformat()}.md")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(report)
    return path, result


def render_report(result, today, dry_run, base):
    lines = [f"# SDD Cleanup Report -- {today.isoformat()}", ""]
    if dry_run:
        lines += ["_Dry run -- nothing was condensed, merged, or removed._", ""]
    lines += [f"Memory root: `{base}`", ""]
    merged = result["would_merge"] if dry_run else [(m["store"], m["parent"]) for m in result["merged"]]
    lines.append(f"## Worktree stores {'to merge' if dry_run else 'merged'} ({len(merged)})")
    lines += [f"- `{s}` -> `{p}`" for s, p in merged] or ["- none"]
    lines += [f"- kept `{s}`: {r}" for s, r in result["kept_worktrees"]]
    lines.append("")
    lines.append(f"## Completed features {'to condense' if dry_run else 'condensed'}")
    if dry_run:
        lines += [f"- `{rel}`" for rel in result["would_condense"]] or ["- none"]
    else:
        lines += [f"- `{os.path.relpath(p, base)}`" for p in result["condensed"]] or ["- none"]
    lines += [f"- kept `{rel}`: {r}" for rel, r in result["kept_features"]]
    lines.append("")
    if not dry_run:
        lines.append("## New completed-feature summaries")
        lines += [f"- {p}" for p in result["condensed"]] or ["- none"]
        lines.append("")
    if result["errors"]:
        lines.append("## Errors")
        lines += [f"- {e}" for e in result["errors"]]
        lines.append("")
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--dry-run", action="store_true", help="Report only; change nothing.")
    parser.add_argument("--idle-days", type=int, default=IDLE_DAYS,
                        help=f"Days a folder must be unchanged before cleanup (default {IDLE_DAYS}).")
    args = parser.parse_args(argv)
    path, result = run(dry_run=args.dry_run, idle_days=args.idle_days)
    print(f"SDD cleanup: memory root {BASE}")
    if args.dry_run:
        print(f"Would merge {len(result['would_merge'])} worktree store(s); "
              f"would condense {len(result['would_condense'])} completed feature(s).")
    else:
        print(f"Merged {len(result['merged'])} worktree store(s); "
              f"condensed {len(result['condensed'])} completed feature(s).")
        for p in result["condensed"]:
            print(f"New summary: {p}")
    if result["errors"]:
        print(f"{len(result['errors'])} error(s) -- see report.")
    print(f"Report written to {path}")


if __name__ == "__main__":
    main()
