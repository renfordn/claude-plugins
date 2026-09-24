"""Tests for scripts/nelly_cleanup.py: worktree-store merges and session-handoff rollups."""
import datetime
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nelly_cleanup  # noqa: E402

TODAY = datetime.date(2026, 10, 30)
OLD = time.mktime(datetime.date(2026, 9, 1).timetuple())


def _write(path, text, mtime=OLD):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    os.utime(path, (mtime, mtime))


def _entry(name, desc="a fact"):
    return f"---\nname: {name}\ndescription: {desc}\nmetadata:\n  type: project\n---\nbody\n"


def _handoff(store, stamp, desc="active files: a.py", commit=None):
    name = f"session-handoff-{stamp}"
    body = _entry(name, f"Session ended -- {desc}") + (f"Last commit: {commit}\n" if commit else "")
    _write(os.path.join(store, "entries", name + ".md"), body)
    with open(os.path.join(store, "MEMORY.md"), "a") as fh:
        fh.write(f"- [H](entries/{name}.md) — handoff `[type:technique]`\n")
    return name


def _store(base, slug, project_path):
    d = os.path.join(base, slug)
    _write(os.path.join(d, "MEMORY.md"), f"# Agent Nelly Memory Index\n\nProject: {project_path}\n\n")
    return d


# --- session-handoff rollup ------------------------------------------------

def test_rollup_keeps_newest_and_rolls_old_ones(tmp_path):
    store = _store(str(tmp_path), "proj", "/p")
    names = [_handoff(store, f"2026-09-{d:02d}-1000", desc=f"day {d}", commit="fix x" if d == 1 else None)
             for d in range(1, 9)]  # 8 handoffs, all > 14 days old
    rolled = nelly_cleanup.roll_up_session_handoffs(store, TODAY)
    assert sorted(rolled) == sorted(n + ".md" for n in names[:3])  # newest 5 kept
    remaining = os.listdir(os.path.join(store, "entries"))
    assert sorted(remaining) == sorted(n + ".md" for n in names[3:])
    history = open(os.path.join(store, "SESSION-HISTORY.md")).read()
    assert "- 2026-09-01 10:00 — day 1 Last commit: fix x." in history
    assert "day 4" not in history
    index = open(os.path.join(store, "MEMORY.md")).read()
    assert names[0] not in index and names[7] in index
    assert "rolled-up-session-handoffs" in open(os.path.join(store, "CONSOLIDATION-LOG.md")).read()


def test_rollup_leaves_recent_handoffs_even_beyond_keep(tmp_path):
    store = _store(str(tmp_path), "proj", "/p")
    for d in range(20, 28):  # 8 handoffs, all under 14 days old
        _handoff(store, f"2026-10-{d:02d}-0900")
    assert nelly_cleanup.roll_up_session_handoffs(store, TODAY) == []


def test_rollup_dry_run_changes_nothing(tmp_path):
    store = _store(str(tmp_path), "proj", "/p")
    for d in range(1, 9):
        _handoff(store, f"2026-09-{d:02d}-1000")
    rolled = nelly_cleanup.roll_up_session_handoffs(store, TODAY, dry_run=True)
    assert len(rolled) == 3
    assert len(os.listdir(os.path.join(store, "entries"))) == 8
    assert not os.path.exists(os.path.join(store, "SESSION-HISTORY.md"))


# --- orphaned worktree stores ----------------------------------------------

def test_worktree_store_merged_into_parent(tmp_path):
    base = str(tmp_path / "mem")
    repo = str(tmp_path / "repo")
    parent_slug = nelly_cleanup.get_project_slug(repo)
    parent = _store(base, parent_slug, repo)
    _write(os.path.join(parent, "entries", "shared.md"), _entry("shared", "parent version"))
    _write(os.path.join(parent, "entries", "same.md"), _entry("same"))
    with open(os.path.join(parent, "MEMORY.md"), "a") as fh:
        fh.write("- [Shared](entries/shared.md) — parent\n")

    wt_path = f"{repo}/.claude/worktrees/wt1"  # never created -> worktree is gone
    wt = _store(base, nelly_cleanup.get_project_slug(wt_path), wt_path)
    _write(os.path.join(wt, "entries", "only-wt.md"), _entry("only-wt"))
    _write(os.path.join(wt, "entries", "shared.md"), _entry("shared", "worktree version"))
    _write(os.path.join(wt, "entries", "same.md"), _entry("same"))
    with open(os.path.join(wt, "MEMORY.md"), "a") as fh:
        fh.write("- [Only](entries/only-wt.md) — wt\n- [Shared](entries/shared.md) — wt\n")
    _handoff(wt, "2026-09-02-0800", desc="worked in wt")
    _write(os.path.join(wt, "hotspots.json"), "{}")
    for root, _, files in os.walk(wt):
        for f in files:
            os.utime(os.path.join(root, f), (OLD, OLD))

    result = nelly_cleanup.run_cleanup(TODAY, base=base)

    assert not os.path.exists(wt)
    assert [m["parent"] for m in result["merged"]] == [parent_slug]
    entries = sorted(os.listdir(os.path.join(parent, "entries")))
    assert entries == ["only-wt.md", "same.md", "shared--wt1.md", "shared.md"]
    index = open(os.path.join(parent, "MEMORY.md")).read()
    assert "](entries/only-wt.md)" in index and "](entries/shared--wt1.md)" in index
    assert "session-handoff" not in index
    assert "(worktree wt1) — worked in wt" in open(os.path.join(parent, "SESSION-HISTORY.md")).read()
    assert not os.path.exists(os.path.join(parent, "hotspots.json"))
    assert "merged-worktree-store" in open(os.path.join(parent, "CONSOLIDATION-LOG.md")).read()


def test_nested_worktree_maps_to_matching_repo_subdir(tmp_path):
    base = str(tmp_path / "mem")
    repo = str(tmp_path / "repo")
    wt_path = f"{repo}/.claude/worktrees/wt2/agent-isdd"
    wt = _store(base, nelly_cleanup.get_project_slug(wt_path), wt_path)
    os.utime(os.path.join(wt, "MEMORY.md"), (OLD, OLD))
    [(store, parent, label, reason)] = nelly_cleanup.find_orphaned_worktree_stores(base, TODAY)
    assert parent == nelly_cleanup.get_project_slug(f"{repo}/agent-isdd")
    assert label == "wt2" and reason is None


def test_existing_or_recent_worktree_is_kept(tmp_path):
    base = str(tmp_path / "mem")
    live = tmp_path / "repo" / ".claude" / "worktrees" / "live"
    live.mkdir(parents=True)
    _store(base, nelly_cleanup.get_project_slug(str(live)), str(live))
    recent_path = str(tmp_path / "repo" / ".claude" / "worktrees" / "recent")
    recent = _store(base, nelly_cleanup.get_project_slug(recent_path), recent_path)
    now = time.time()
    os.utime(os.path.join(recent, "MEMORY.md"), (now, now))

    result = nelly_cleanup.run_cleanup(datetime.date.today(), base=base)
    reasons = dict(result["skipped_worktrees"])
    assert result["merged"] == []
    assert any("still exists" in r for r in reasons.values())
    assert any("changed 0 day(s) ago" in r for r in reasons.values())


def test_cleanup_section_renders(tmp_path):
    result = {"merged": [], "would_merge": [("wt", "repo")], "skipped_worktrees": [],
              "rolled_up": {"repo": ["a", "b"]}}
    text = "\n".join(nelly_cleanup.render_cleanup_section(result, dry_run=True))
    assert "Would merge 1 orphaned worktree store(s)" in text
    assert "Would roll up 2 old session-handoff entries" in text
