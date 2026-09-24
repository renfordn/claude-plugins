#!/usr/bin/env python3
"""Unattended weekly consolidation scan across every Agent Nelly memory store.

Runs with no LLM calls and no interactive prompts -- meant for a scheduled
task, not a human at a terminal. It only ever takes one auto-mutating action
-- archiving (never deleting) `error-prevention` entries that are
`confidence: inferred`, never confirmed, and at least
STALE_INFERRED_THRESHOLD_DAYS old -- because that judgment ("has this sat
unconfirmed past a fixed threshold") is deterministic. Everything else this
script notices (near-duplicate slugs/descriptions, an active entry that some
other entry's `metadata.supersedes` names) is reported only: deciding whether
two entries really describe the same fact needs the LLM judgment
`agent-nelly` applies via `/nelly-memory consolidate`, which this
script deliberately does not attempt to replicate.

Before scanning, runs scripts/nelly_cleanup.py's bloat cleanup (stale clean-and-pushed git
worktrees removed, orphaned worktree stores merged into their parent repo's store, old
session-handoff entries rolled up into SESSION-HISTORY.md).

Writes a human-readable report to
`<memory root>/agent-nelly-memory/consolidation-reports/YYYY-MM-DD.md` (the shared_memory_root
option when set, else ${CLAUDE_PLUGIN_DATA}; this
plugin's actual memory root -- see hooks/nelly_memory.py's BASE) and, for
every project where it archived something, appends one `Action: archived`
block to that project's own CONSOLIDATION-LOG.md, matching the shape already
used by `agent-nelly.md`'s "Supersession write-back" and "Discarding
an inferred error lesson" sections. After any archiving it rebuilds
nelly-index.json via build_index.build_all() so the index never drifts from
entries/ (see build_index.py's own docstring on why entries/ is the source
of truth after an archive-move).

Usage:
    python3 nelly_weekly_consolidate.py [--dry-run] [--stale-days N]

--dry-run reports every candidate exactly as a real run would, but never
archives anything, never touches CONSOLIDATION-LOG.md, and never rebuilds
the index -- useful for eyeballing what a real run would do first.
"""
import argparse
import datetime
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "hooks"))
from nelly_memory import BASE, global_dir  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_index import iter_project_dirs, build_all  # noqa: E402
import nelly_cleanup  # noqa: E402

STALE_INFERRED_THRESHOLD_DAYS = 90
# Near-duplicate heuristic (report only): word-set overlap on slug + description, not character
# similarity -- auto-extracted entries share long slug prefixes (`auto-tests-test-mongo-...`), which
# made SequenceMatcher flag ~1000 unrelated pairs per run.
NEAR_DUPLICATE_RATIO = 0.6       # Jaccard overlap of distinctive words
NEAR_DUPLICATE_MIN_SHARED = 3    # ...and at least this many distinctive words in common
COMMON_WORD_SHARE = 0.2          # words in more than this share of a store's entries aren't distinctive
COMMON_WORD_MIN_ENTRIES = 5      # (only applied once a store has this many entries)
_STOPWORDS = frozenset(
    "a an the and or of to in on for with is are be by as at it this that from when not no "
    "use uses using via".split()
)
REPORT_DIR = os.path.join(BASE, "consolidation-reports")

CONSOLIDATION_LOG_HEADER = (
    "# Consolidation Log\n\n"
    "Append-only history of consolidation-related actions taken against this "
    "project's memory store, including archives performed by the scheduled "
    "weekly consolidation script (scripts/nelly_weekly_consolidate.py). Never "
    "edit or remove a prior entry -- archived files remain fully readable "
    "under archive/, not deleted.\n\n"
    "## Log\n"
)

_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---", re.S)
_NAME_RE = re.compile(r"^name:\s*(.+)$", re.M)
_DESCRIPTION_RE = re.compile(r"^description:\s*(.+)$", re.M)
_TYPE_RE = re.compile(r"^\s*type:\s*(\S+)", re.M)
_CONFIDENCE_RE = re.compile(r"^\s*confidence:\s*(\S+)", re.M)
_LAST_REFERENCED_RE = re.compile(r"^\s*last_referenced:\s*(\S+)", re.M)
_SUPERSEDES_RE = re.compile(r"^\s*supersedes:\s*(\S+)", re.M)


def _log(msg):
    print(msg, flush=True)


def _parse_entry(path):
    """Parse one entries/<name>.md file's frontmatter. Returns None on any
    read/parse failure -- a malformed entry is reported as a skip, never a
    crash for the whole run.
    """
    try:
        with open(path, "r", encoding="utf-8") as fh:
            text = fh.read()
    except OSError as exc:
        return None, str(exc)
    m = _FRONTMATTER_RE.search(text)
    if not m:
        return None, "no frontmatter block found"
    block = m.group(1)
    name_m = _NAME_RE.search(block)
    if not name_m:
        return None, "no name field in frontmatter"
    desc_m = _DESCRIPTION_RE.search(block)
    type_m = _TYPE_RE.search(block)
    confidence_m = _CONFIDENCE_RE.search(block)
    last_ref_m = _LAST_REFERENCED_RE.search(block)
    supersedes_m = _SUPERSEDES_RE.search(block)
    record = {
        "slug": name_m.group(1).strip(),
        "description": desc_m.group(1).strip() if desc_m else "",
        "type": type_m.group(1).strip() if type_m else None,
        "confidence": confidence_m.group(1).strip() if confidence_m else None,
        "last_referenced": last_ref_m.group(1).strip() if last_ref_m else None,
        "supersedes": supersedes_m.group(1).strip() if supersedes_m else None,
        "path": path,
    }
    return record, None


def _entries_in(project_dir, errors):
    entries_dir = os.path.join(project_dir, "entries")
    if not os.path.isdir(entries_dir):
        return []
    out = []
    for name in sorted(os.listdir(entries_dir)):
        if not name.endswith(".md"):
            continue
        record, err = _parse_entry(os.path.join(entries_dir, name))
        if record:
            out.append(record)
        else:
            errors.append(f"{os.path.join('entries', name)}: {err}")
    return out


def _days_old(date_str, today):
    try:
        d = datetime.date.fromisoformat(date_str)
    except (TypeError, ValueError):
        return None
    return (today - d).days


def _words(entry):
    text = f"{entry['slug']} {entry.get('description') or ''}".lower()
    return {w for w in re.findall(r"[a-z0-9]+", text) if len(w) > 2 and w not in _STOPWORDS}


def _find_near_duplicate_pairs(entries):
    """Report-only heuristic: flag entry pairs that likely describe the same fact.

    Two entries are candidates when they have the same `type` and their distinctive words
    (slug + description, minus stopwords and minus words common across this store) overlap by
    at least NEAR_DUPLICATE_RATIO (Jaccard) with NEAR_DUPLICATE_MIN_SHARED words in common.
    Session-handoff entries are skipped -- nelly_cleanup.py rolls those up instead. This never
    merges anything: deciding whether two entries really describe the same fact is
    agent-nelly's judgment call via `/nelly-memory consolidate`, not this script's.
    """
    candidates = [e for e in entries if not e["slug"].startswith("session-handoff-")]
    words = [_words(e) for e in candidates]
    common = set()
    if len(candidates) >= COMMON_WORD_MIN_ENTRIES:
        counts = {}
        for ws in words:
            for w in ws:
                counts[w] = counts.get(w, 0) + 1
        common = {w for w, n in counts.items() if n / len(candidates) > COMMON_WORD_SHARE}
    distinctive = [ws - common for ws in words]

    pairs = []
    for i, a in enumerate(candidates):
        for j in range(i + 1, len(candidates)):
            b = candidates[j]
            if a.get("type") != b.get("type"):
                continue
            wa, wb = distinctive[i], distinctive[j]
            if not wa or not wb:
                continue
            shared = len(wa & wb)
            ratio = shared / len(wa | wb)
            if ratio >= NEAR_DUPLICATE_RATIO and shared >= NEAR_DUPLICATE_MIN_SHARED:
                pairs.append((a, b, ratio))
    return pairs


def _find_stale_inferred(entries, today, threshold_days):
    stale = []
    for e in entries:
        if e["type"] != "error-prevention" or e["confidence"] != "inferred":
            continue
        age = _days_old(e["last_referenced"], today)
        if age is not None and age >= threshold_days:
            stale.append((e, age))
    return stale


def _find_superseded_not_archived(entries):
    """An entry still in entries/ that some OTHER active entry's
    `metadata.supersedes` names. The normal write path (Supersession
    write-back) always archives the old entry in the same call it writes the
    new one, so this should never happen -- flagged defensively rather than
    assumed impossible.
    """
    slugs = {e["slug"] for e in entries}
    flagged = []
    for e in entries:
        if e["supersedes"] and e["supersedes"] in slugs:
            flagged.append((e, e["supersedes"]))
    return flagged


def _archive_entry(project_dir, record):
    archive_dir = os.path.join(project_dir, "archive")
    os.makedirs(archive_dir, exist_ok=True)
    dest = os.path.join(archive_dir, os.path.basename(record["path"]))
    os.rename(record["path"], dest)
    return dest


def _remove_index_line(project_dir, slug):
    memory_md = os.path.join(project_dir, "MEMORY.md")
    try:
        with open(memory_md, "r", encoding="utf-8") as fh:
            lines = fh.readlines()
    except OSError:
        return
    pattern = re.compile(r"\]\(entries/" + re.escape(slug) + r"\.md\)")
    new_lines = [ln for ln in lines if not pattern.search(ln)]
    if new_lines != lines:
        with open(memory_md, "w", encoding="utf-8") as fh:
            fh.writelines(new_lines)


def _append_consolidation_log(project_dir, archived):
    if not archived:
        return
    log_path = os.path.join(project_dir, "CONSOLIDATION-LOG.md")
    if not os.path.exists(log_path):
        with open(log_path, "w", encoding="utf-8") as fh:
            fh.write(CONSOLIDATION_LOG_HEADER)
    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    blocks = []
    for record, age in archived:
        blocks.append(
            f"\n### {timestamp}\n"
            f"- Action: archived\n"
            f"- Entry: {record['slug']}\n"
            f"- Reason: inferred error-prevention lesson stale ({age} days, "
            f"never confirmed) -- auto-archived by weekly consolidation script\n"
            f"- Trigger: scheduled weekly consolidation "
            f"(scripts/nelly_weekly_consolidate.py)\n"
        )
    with open(log_path, "a", encoding="utf-8") as fh:
        fh.write("".join(blocks))


def _scan_project(project_dir, today, threshold_days, dry_run, errors):
    slug = os.path.basename(project_dir)
    entries = _entries_in(project_dir, errors)
    if not entries:
        return None

    dup_pairs = _find_near_duplicate_pairs(entries)
    stale_inferred = _find_stale_inferred(entries, today, threshold_days)
    superseded_anomalies = _find_superseded_not_archived(entries)

    archived = []
    if not dry_run:
        for record, age in stale_inferred:
            try:
                _archive_entry(project_dir, record)
                _remove_index_line(project_dir, record["slug"])
                archived.append((record, age))
            except OSError as exc:
                errors.append(f"{slug}/{record['slug']}: failed to archive ({exc})")
        _append_consolidation_log(project_dir, archived)

    return {
        "slug": slug,
        "entry_count": len(entries),
        "dup_pairs": dup_pairs,
        "stale_inferred": stale_inferred,
        "superseded_anomalies": superseded_anomalies,
        "archived": archived,
    }


def _scan_global(errors):
    """Global tier has no per-entry files -- just report near-duplicate
    frontmatter blocks inside GLOBAL-MEMORY.md. Never archives anything here;
    "Consolidating global-tier duplicates is out of scope" per
    agent-nelly.md's Promotion write-back.
    """
    g = global_dir()
    source = os.path.join(g, "GLOBAL-MEMORY.md")
    try:
        with open(source, "r", encoding="utf-8") as fh:
            text = fh.read()
    except OSError as exc:
        errors.append(f"global/GLOBAL-MEMORY.md: {exc}")
        return []
    entries = []
    for block in re.findall(r"^---\n(.*?)\n---", text, re.M | re.S):
        name_m = _NAME_RE.search(block)
        if not name_m:
            continue
        desc_m = _DESCRIPTION_RE.search(block)
        entries.append({
            "slug": name_m.group(1).strip(),
            "description": desc_m.group(1).strip() if desc_m else "",
        })
    return _find_near_duplicate_pairs(entries)


def _render_report(date_str, threshold_days, project_results, global_dup_pairs, errors, dry_run,
                   cleanup=None):
    lines = [f"# Nelly Weekly Consolidation Report -- {date_str}", ""]
    if dry_run:
        lines.append("_Dry run -- no files were archived or modified._")
        lines.append("")
    lines.append(f"Memory root: `{BASE}`")
    lines.append(f"Stale-inferred threshold: {threshold_days} days.")
    lines.append(f"Near-duplicate threshold: {NEAR_DUPLICATE_RATIO} word overlap, "
                 f"{NEAR_DUPLICATE_MIN_SHARED}+ shared distinctive words, same type.")
    lines.append("")
    if cleanup is not None:
        lines.extend(nelly_cleanup.render_cleanup_section(cleanup, dry_run))

    total_archived = sum(len(r["archived"]) for r in project_results)
    total_dup_pairs = sum(len(r["dup_pairs"]) for r in project_results) + len(global_dup_pairs)
    total_anomalies = sum(len(r["superseded_anomalies"]) for r in project_results)

    lines.append("## Summary")
    lines.append(f"- Projects scanned: {len(project_results)}")
    lines.append(f"- Entries archived (stale inferred error-prevention): {total_archived}")
    lines.append(f"- Near-duplicate candidate pairs found: {total_dup_pairs}")
    lines.append(f"- Superseded-but-not-archived anomalies found: {total_anomalies}")
    lines.append(f"- Errors encountered: {len(errors)}")
    lines.append("")

    if not project_results:
        lines.append("No project memory stores found under Agent Nelly's memory root "
                     "(see hooks/nelly_memory.py's BASE).")
        lines.append("")

    for r in project_results:
        if not (r["dup_pairs"] or r["stale_inferred"] or r["superseded_anomalies"]):
            continue
        lines.append(f"## Project: `{r['slug']}` ({r['entry_count']} entries)")

        if r["archived"]:
            lines.append("")
            lines.append("### Archived this run")
            for record, age in r["archived"]:
                lines.append(
                    f"- `{record['slug']}` -- inferred error-prevention, "
                    f"{age} days since last_referenced, never confirmed. "
                    f"Moved to `archive/`, logged in `CONSOLIDATION-LOG.md`."
                )
        elif r["stale_inferred"]:
            lines.append("")
            lines.append("### Stale inferred entries (would be archived on a non-dry-run pass)")
            for record, age in r["stale_inferred"]:
                lines.append(
                    f"- `{record['slug']}` -- {age} days since last_referenced, "
                    f"never confirmed."
                )

        if r["dup_pairs"]:
            lines.append("")
            lines.append("### Near-duplicate candidates (report only -- needs "
                          "`/nelly-memory consolidate` to merge)")
            for a, b, ratio in r["dup_pairs"]:
                lines.append(f"- `{a['slug']}` <-> `{b['slug']}` (overlap {ratio:.2f})")

        if r["superseded_anomalies"]:
            lines.append("")
            lines.append("### Superseded-but-not-archived anomalies (needs manual review)")
            for record, old_slug in r["superseded_anomalies"]:
                lines.append(
                    f"- `{record['slug']}` names `{old_slug}` as superseded via "
                    f"`metadata.supersedes`, but `{old_slug}` is still in `entries/` "
                    f"(should have been archived when `{record['slug']}` was written)."
                )
        lines.append("")

    if global_dup_pairs:
        lines.append("## Global tier: near-duplicate candidates (report only)")
        for a, b, ratio in global_dup_pairs:
            lines.append(f"- `{a['slug']}` <-> `{b['slug']}` (overlap {ratio:.2f})")
        lines.append("")

    if errors:
        lines.append("## Errors")
        for err in errors:
            lines.append(f"- {err}")
        lines.append("")

    return "\n".join(lines) + "\n"


def run(threshold_days=STALE_INFERRED_THRESHOLD_DAYS, dry_run=False, today=None):
    today = today or datetime.date.today()
    errors = []

    # Bloat cleanup first, so merged worktree entries are scanned with their new parent.
    try:
        cleanup = nelly_cleanup.run_cleanup(today, dry_run=dry_run)
    except OSError as exc:
        cleanup = None
        errors.append(f"cleanup: {exc}")

    project_results = []
    for project_dir in iter_project_dirs():
        result = _scan_project(project_dir, today, threshold_days, dry_run, errors)
        if result is not None:
            project_results.append(result)

    global_dup_pairs = _scan_global(errors)

    if not dry_run:
        build_all()

    os.makedirs(REPORT_DIR, exist_ok=True)
    date_str = today.isoformat()
    report_path = os.path.join(REPORT_DIR, f"{date_str}.md")
    report_text = _render_report(
        date_str, threshold_days, project_results, global_dup_pairs, errors, dry_run, cleanup
    )
    with open(report_path, "w", encoding="utf-8") as fh:
        fh.write(report_text)

    run.last_cleanup = cleanup
    return report_path, project_results, global_dup_pairs, errors


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                         help="Report candidates without archiving or rebuilding the index.")
    parser.add_argument("--stale-days", type=int, default=STALE_INFERRED_THRESHOLD_DAYS,
                         help=f"Age threshold in days for stale inferred entries "
                              f"(default {STALE_INFERRED_THRESHOLD_DAYS}).")
    args = parser.parse_args(argv)

    report_path, project_results, global_dup_pairs, errors = run(
        threshold_days=args.stale_days, dry_run=args.dry_run
    )

    total_archived = sum(len(r["archived"]) for r in project_results)
    _log(f"Nelly weekly consolidation: scanned {len(project_results)} project(s).")
    _log(f"Memory root: {BASE}")
    _log(f"Archived {total_archived} stale inferred entr{'y' if total_archived == 1 else 'ies'}.")
    cleanup = getattr(run, "last_cleanup", None)
    if cleanup is not None:
        merged = cleanup["would_merge"] if args.dry_run else cleanup["merged"]
        rolled = sum(len(v) for v in cleanup["rolled_up"].values())
        verb = "Would merge" if args.dry_run else "Merged"
        _log(f"{verb} {len(merged)} orphaned worktree store(s); "
             f"{'would roll' if args.dry_run else 'rolled'} up {rolled} old session handoff(s).")
    if errors:
        _log(f"{len(errors)} error(s) encountered -- see report for details.")
    _log(f"Report written to {report_path}")


if __name__ == "__main__":
    main()
