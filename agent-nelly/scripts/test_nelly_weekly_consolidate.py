"""Tests for scripts/nelly_weekly_consolidate.py -- the unattended weekly
consolidation scan (no LLM calls, no interactive prompts).
"""
import datetime
import os

import pytest

import nelly_weekly_consolidate as consolidate
import nelly_memory


@pytest.fixture(autouse=True)
def isolated_base(tmp_path, monkeypatch):
    base = str(tmp_path / "agent-nelly-memory")
    monkeypatch.setattr(nelly_memory, "BASE", base)
    monkeypatch.setattr(consolidate, "BASE", base)
    monkeypatch.setattr(consolidate, "REPORT_DIR", os.path.join(base, "consolidation-reports"))
    import build_index
    monkeypatch.setattr(build_index, "BASE", base)
    return tmp_path


def _write_entry(cwd, name, type_="project", description="A test fact.",
                  confidence=None, last_referenced="2026-08-16", supersedes=None):
    entries_dir = nelly_memory.ensure_entries_dir(cwd)
    lines = ["---", f"name: {name}", f"description: {description}",
             "metadata:", f"  type: {type_}", f"  last_referenced: {last_referenced}"]
    if confidence is not None:
        lines.append(f"  confidence: {confidence}")
    if supersedes is not None:
        lines.append(f"  supersedes: {supersedes}")
    lines += ["---", "", "Body text."]
    path = os.path.join(entries_dir, f"{name}.md")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    return path


TODAY = datetime.date(2026, 8, 16)


# ---------------------------------------------------------------------------
# _find_near_duplicate_pairs
# ---------------------------------------------------------------------------

def test_near_duplicate_pairs_flags_similar_descriptions():
    entries = [
        {"slug": "retry-http-timeouts", "description": "Retry on flaky HTTP timeouts with backoff."},
        {"slug": "backoff-for-http-timeouts", "description": "Retry on flaky HTTP timeouts with a backoff strategy."},
        {"slug": "unrelated-fact", "description": "Docker compose local dev setup."},
    ]
    pairs = consolidate._find_near_duplicate_pairs(entries)
    slugs = {(a["slug"], b["slug"]) for a, b, _ in pairs}
    assert ("retry-http-timeouts", "backoff-for-http-timeouts") in slugs
    assert not any("unrelated-fact" in pair for pair in slugs)


def test_near_duplicate_pairs_empty_for_distinct_entries():
    entries = [
        {"slug": "docker-compose-setup", "description": "Completely different subject one."},
        {"slug": "monzo-api-quirks", "description": "Totally unrelated topic two here."},
    ]
    assert consolidate._find_near_duplicate_pairs(entries) == []


# ---------------------------------------------------------------------------
# _find_stale_inferred
# ---------------------------------------------------------------------------

def test_stale_inferred_flags_old_unconfirmed_entries():
    entries = [
        {"slug": "old-inferred", "type": "error-prevention", "confidence": "inferred",
         "last_referenced": "2026-01-01"},
        {"slug": "fresh-inferred", "type": "error-prevention", "confidence": "inferred",
         "last_referenced": "2026-08-10"},
        {"slug": "old-explicit", "type": "error-prevention", "confidence": "explicit",
         "last_referenced": "2026-01-01"},
        {"slug": "old-project-fact", "type": "project", "confidence": None,
         "last_referenced": "2026-01-01"},
    ]
    stale = consolidate._find_stale_inferred(entries, TODAY, 90)
    slugs = {e["slug"] for e, _age in stale}
    assert slugs == {"old-inferred"}


# ---------------------------------------------------------------------------
# _find_superseded_not_archived
# ---------------------------------------------------------------------------

def test_superseded_not_archived_flags_dangling_reference():
    entries = [
        {"slug": "new-lesson", "supersedes": "old-lesson"},
        {"slug": "old-lesson", "supersedes": None},
    ]
    flagged = consolidate._find_superseded_not_archived(entries)
    assert len(flagged) == 1
    assert flagged[0][0]["slug"] == "new-lesson"
    assert flagged[0][1] == "old-lesson"


def test_superseded_not_flagged_when_old_entry_already_archived():
    entries = [{"slug": "new-lesson", "supersedes": "old-lesson"}]
    assert consolidate._find_superseded_not_archived(entries) == []


# ---------------------------------------------------------------------------
# run() -- end-to-end against a fake memory store
# ---------------------------------------------------------------------------

def test_run_archives_stale_inferred_and_writes_report(tmp_path):
    cwd = str(tmp_path / "some-project")
    os.makedirs(cwd, exist_ok=True)
    _write_entry(cwd, "old-inferred-lesson", type_="error-prevention",
                 confidence="inferred", last_referenced="2026-01-01")
    _write_entry(cwd, "fresh-inferred-lesson", type_="error-prevention",
                 confidence="inferred", last_referenced="2026-08-10")
    _write_entry(cwd, "normal-fact", type_="project", last_referenced="2026-08-01")

    project_dir = nelly_memory.memory_dir(cwd)
    nelly_memory.write_index_line(cwd, "old-inferred-lesson", "hook", "error-prevention",
                                   confidence="inferred")
    nelly_memory.write_index_line(cwd, "fresh-inferred-lesson", "hook", "error-prevention",
                                   confidence="inferred")

    report_path, project_results, _global_pairs, errors = consolidate.run(
        threshold_days=90, dry_run=False, today=TODAY
    )

    assert errors == []
    assert os.path.exists(report_path)
    assert not os.path.exists(os.path.join(project_dir, "entries", "old-inferred-lesson.md"))
    assert os.path.exists(os.path.join(project_dir, "archive", "old-inferred-lesson.md"))
    assert os.path.exists(os.path.join(project_dir, "entries", "fresh-inferred-lesson.md"))

    memory_md = open(os.path.join(project_dir, "MEMORY.md"), encoding="utf-8").read()
    assert "old-inferred-lesson" not in memory_md
    assert "fresh-inferred-lesson" in memory_md

    log_path = os.path.join(project_dir, "CONSOLIDATION-LOG.md")
    assert os.path.exists(log_path)
    log_text = open(log_path, encoding="utf-8").read()
    assert "Action: archived" in log_text
    assert "old-inferred-lesson" in log_text

    index_path = os.path.join(project_dir, "nelly-index.json")
    assert os.path.exists(index_path)

    result = project_results[0]
    assert len(result["archived"]) == 1
    assert result["archived"][0][0]["slug"] == "old-inferred-lesson"


def test_run_dry_run_archives_nothing(tmp_path):
    cwd = str(tmp_path / "dry-project")
    os.makedirs(cwd, exist_ok=True)
    _write_entry(cwd, "old-inferred-lesson", type_="error-prevention",
                 confidence="inferred", last_referenced="2026-01-01")

    project_dir = nelly_memory.memory_dir(cwd)
    report_path, project_results, _global_pairs, errors = consolidate.run(
        threshold_days=90, dry_run=True, today=TODAY
    )

    assert errors == []
    assert os.path.exists(os.path.join(project_dir, "entries", "old-inferred-lesson.md"))
    assert not os.path.exists(os.path.join(project_dir, "archive"))
    assert not os.path.exists(os.path.join(project_dir, "CONSOLIDATION-LOG.md"))

    result = project_results[0]
    assert result["archived"] == []
    assert len(result["stale_inferred"]) == 1
    report_text = open(report_path, encoding="utf-8").read()
    assert "Dry run" in report_text
    assert "old-inferred-lesson" in report_text


def test_run_graceful_on_missing_base_dir(tmp_path):
    """BASE itself doesn't exist yet (no project has ever written memory) --
    run() must not crash, just report zero projects scanned.
    """
    report_path, project_results, global_pairs, errors = consolidate.run(
        threshold_days=90, dry_run=False, today=TODAY
    )
    assert project_results == []
    assert global_pairs == []
    assert errors == []
    assert os.path.exists(report_path)


def test_run_skips_malformed_entry_without_crashing(tmp_path):
    cwd = str(tmp_path / "broken-project")
    entries_dir = nelly_memory.ensure_entries_dir(cwd)
    with open(os.path.join(entries_dir, "broken.md"), "w", encoding="utf-8") as fh:
        fh.write("not valid frontmatter at all")
    _write_entry(cwd, "good-entry", last_referenced="2026-08-01")

    report_path, project_results, _global_pairs, errors = consolidate.run(
        threshold_days=90, dry_run=False, today=TODAY
    )
    assert any("broken.md" in e for e in errors)
    assert os.path.exists(report_path)
    assert len(project_results) == 1
    assert project_results[0]["entry_count"] == 1
