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
`nelly-orchestrator` applies via `/nelly-memory consolidate`, which this
script deliberately does not attempt to replicate.

Writes a human-readable report to
`~/.claude/agent-nelly-memory/consolidation-reports/YYYY-MM-DD.md` (this
plugin's actual memory root -- see hooks/nelly_memory.py's BASE) and, for
every project where it archived something, appends one `Action: archived`
block to that project's own CONSOLIDATION-LOG.md, matching the shape already
used by `nelly-orchestrator.md`'s "Supersession write-back" and "Discarding
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
import difflib
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "hooks"))
from nelly_memory import BASE, global_dir  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_index import iter_project_dirs, build_all  # noqa: E402

STALE_INFERRED_THRESHOLD_DAYS = 90
NEAR_DUPLICATE_RATIO = 0.72
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


def _similarity(a, b):
    return difflib.SequenceMatcher(None, a, b).ratio()


def _find_near_duplicate_pairs(entries):
    """Report-only heuristic: flag entry pairs whose slug or description text
    is highly similar. This never merges anything -- deciding whether two
    entries really describe the same fact is nelly-orchestrator's judgment
    call via `/nelly-memory consolidate`, not this script's.
    """
    pairs = []
    for i, a in enumerate(entries):
        for b in entries[i + 1:]:
            slug_ratio = _similarity(a["slug"], b["slug"])
            desc_ratio = (
                _similarity(a["description"].lower(), b["description"].lower())
                if a["description"] and b["description"]
                else 0.0
            )
            ratio = max(slug_ratio, desc_ratio)
            if ratio >= NEAR_DUPLICATE_RATIO:
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
    nelly-orchestrator.md's Promotion write-back.
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


def _render_report(date_str, threshold_days, project_results, global_dup_pairs, errors, dry_run):
    lines = [f"# Nelly Weekly Consolidation Report -- {date_str}", ""]
    if dry_run:
        lines.append("_Dry run -- no files were archived or modified._")
        lines.append("")
    lines.append(f"Stale-inferred threshold: {threshold_days} days.")
    lines.append(f"Near-duplicate similarity threshold: {NEAR_DUPLICATE_RATIO}.")
    lines.append("")

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
        lines.append("No project memory stores found under `~/.claude/agent-nelly-memory/`.")
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
                lines.append(f"- `{a['slug']}` <-> `{b['slug']}` (similarity {ratio:.2f})")

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
            lines.append(f"- `{a['slug']}` <-> `{b['slug']}` (similarity {ratio:.2f})")
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
        date_str, threshold_days, project_results, global_dup_pairs, errors, dry_run
    )
    with open(report_path, "w", encoding="utf-8") as fh:
        fh.write(report_text)

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
    _log(f"Archived {total_archived} stale inferred entr{'y' if total_archived == 1 else 'ies'}.")
    if errors:
        _log(f"{len(errors)} error(s) encountered -- see report for details.")
    _log(f"Report written to {report_path}")


if __name__ == "__main__":
    main()
