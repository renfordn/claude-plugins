"""Tests for nelly_freshness.scan: mark entries stale when their recorded sources changed (R17)."""
import json
import os
import subprocess
import sys
import time

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))

import build_index  # noqa: E402
import nelly_freshness  # noqa: E402
import nelly_memory  # noqa: E402
import nelly_store  # noqa: E402
from research_digest import blob_hash  # noqa: E402


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    data = str(tmp_path / "plugin-data")
    monkeypatch.setenv("CLAUDE_PLUGIN_DATA", data)
    monkeypatch.setattr(nelly_memory, "BASE", os.path.join(data, "agent-nelly-memory"))
    monkeypatch.setattr(nelly_memory, "LOCAL_BASE", os.path.join(data, "agent-nelly-local"))


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "repo"
    (r / "src").mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(r)], check=True)
    return r


def put_file(repo, rel, text):
    p = repo / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)


def make_entry(repo, name, sources, verified="2026-01-01", stale=False):
    """sources: {rel: recorded_text}; the recorded hash is of that text."""
    cwd = str(repo)
    nelly_memory.ensure_entries_dir(cwd)
    path = nelly_memory.entry_path(cwd, name)
    src = ", ".join("{path: %s, hash: %s}" % (p, blob_hash(t.encode())) for p, t in sources.items())
    lines = ["---", f"name: {name}", "description: d", "metadata:", "  type: project",
             f"  sources: [{src}]", "  revision: abc", f"  verified: {verified}", "  basis: observed"]
    if stale:
        lines += ["  stale: true", "  stale_since: 2026-02-02", "  stale_paths: [x]"]
    lines += ["---", "", "Body."]
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    build_index.upsert_project_entry(cwd, path)
    return path


def records(repo):
    with open(os.path.join(nelly_memory.memory_dir(str(repo)), "nelly-index.json")) as fh:
        return {r["slug"]: r for r in json.load(fh)}


def cursor_path(repo):
    return os.path.join(nelly_memory.local_state_dir(str(repo)), "freshness-cursor.json")


def test_changed_file_marked_stale_exact_frontmatter_and_index(repo):
    put_file(repo, "src/a.py", "old")
    path = make_entry(repo, "fact-a", {"src/a.py": "old"})
    before = open(path).read()
    put_file(repo, "src/a.py", "new")

    lines = nelly_freshness.scan(str(repo))

    expected = before.replace(
        "  basis: observed\n",
        "  basis: observed\n  stale: true\n  stale_since: %s\n  stale_paths: [src/a.py]\n"
        % time.strftime("%Y-%m-%d"))
    assert open(path).read() == expected
    rec = records(repo)["fact-a"]
    assert rec["stale"] is True and rec["stale_paths"] == ["src/a.py"]
    assert any("1 memory entries marked stale" in ln and "fact-a (src/a.py)" in ln
               and "nelly_evidence.py refresh <slug> --paths" in ln for ln in lines)
    assert "1 memory entries are stale in total." in lines


def test_unchanged_stays_fresh_and_no_lines(repo):
    put_file(repo, "src/a.py", "same")
    path = make_entry(repo, "fact-a", {"src/a.py": "same"})
    before = open(path).read()
    assert nelly_freshness.scan(str(repo)) == []
    assert open(path).read() == before
    assert not records(repo)["fact-a"].get("stale")


def test_missing_file_is_stale_and_nothing_deleted(repo):
    put_file(repo, "src/a.py", "x")
    path = make_entry(repo, "fact-a", {"src/a.py": "x", "src/gone.py": "y"})
    nelly_freshness.scan(str(repo))
    assert records(repo)["fact-a"]["stale_paths"] == ["src/gone.py"]
    assert os.path.isfile(path)
    assert (repo / "src/a.py").read_text() == "x"


def test_already_stale_skipped_but_counted_in_total(repo):
    put_file(repo, "src/a.py", "new")
    path = make_entry(repo, "fact-a", {"src/a.py": "old"}, stale=True)
    before = open(path).read()
    lines = nelly_freshness.scan(str(repo))
    assert open(path).read() == before
    assert lines == ["1 memory entries are stale in total."]


def test_non_git_cwd_returns_empty(tmp_path):
    d = tmp_path / "plain"
    d.mkdir()
    assert nelly_freshness.scan(str(d)) == []


def test_store_locked_entry_skipped(repo, monkeypatch):
    put_file(repo, "src/a.py", "new")
    path = make_entry(repo, "fact-a", {"src/a.py": "old"})
    before = open(path).read()

    def locked(*a, **k):
        raise nelly_store.StoreLocked("busy")
    monkeypatch.setattr(nelly_store, "update_entry", locked)
    assert nelly_freshness.scan(str(repo)) == []
    assert open(path).read() == before


def test_cursor_rotation_with_tiny_budget(repo, monkeypatch):
    for i in range(3):
        put_file(repo, f"src/f{i}.py", "new")
        make_entry(repo, f"fact-{i}", {f"src/f{i}.py": "old"}, verified=f"2026-01-0{i + 1}")
    # Fake clock: each monotonic() call advances 0.5s, budget 1.0s -> a scan handles only a
    # prefix of the entries, so the cursor must carry the rest to later scans.
    ticks = iter(range(0, 10000))
    monkeypatch.setattr(nelly_freshness.time, "monotonic", lambda: next(ticks) * 0.5)
    counts = []
    for _ in range(4):
        nelly_freshness.scan(str(repo), budget=1.0)
        counts.append(sum(1 for r in records(repo).values() if r.get("stale")))
    assert counts[0] < 3
    assert counts == sorted(counts)
    assert counts[-1] == 3
    assert os.path.isfile(cursor_path(repo))


def test_many_entries_respects_budget(repo):
    put_file(repo, "src/a.py", "same")
    for i in range(200):
        make_entry(repo, f"fact-{i}", {"src/a.py": "same"})
    start = time.monotonic()
    nelly_freshness.scan(str(repo), budget=0.25)
    assert time.monotonic() - start <= 0.25 + 0.2
    assert os.path.isfile(cursor_path(repo))  # saved whether the pass finished or ran out of budget


def _fm(text):
    import yaml
    return yaml.safe_load(text.split("---\n")[1])


def test_research_digest_with_changed_source_never_reported(repo):
    put_file(repo, "src/a.py", "new")
    cwd = str(repo)
    nelly_memory.ensure_entries_dir(cwd)
    path = nelly_memory.entry_path(cwd, "dig")
    with open(path, "w") as fh:
        fh.write("---\nname: dig\ndescription: d\ntype: research-digest\ntopic: t\n"
                 "sources: [{path: src/a.py, hash: %s}]\n---\n\nBody.\n" % blob_hash(b"old"))
    build_index.upsert_project_entry(cwd, path)
    before = open(path).read()
    assert nelly_freshness.scan(cwd) == []
    assert nelly_freshness.scan(cwd) == []
    assert open(path).read() == before


def test_entry_without_metadata_not_reported(repo):
    put_file(repo, "src/a.py", "new")
    cwd = str(repo)
    nelly_memory.ensure_entries_dir(cwd)
    path = nelly_memory.entry_path(cwd, "nometa")
    with open(path, "w") as fh:
        fh.write("---\nname: nometa\ndescription: d\ntype: project\n"
                 "sources: [{path: src/a.py, hash: %s}]\n---\n\nBody.\n" % blob_hash(b"old"))
    build_index.upsert_project_entry(cwd, path)
    assert nelly_freshness.scan(cwd) == []


def test_metadata_with_trailing_comment_is_marked(repo):
    put_file(repo, "src/a.py", "new")
    path = make_entry(repo, "fact-a", {"src/a.py": "old"})
    text = open(path).read().replace("metadata:\n", "metadata:  # evidence\n")
    with open(path, "w") as fh:
        fh.write(text)
    # index keeps the record made before the comment was added; the marking edits the file
    lines = nelly_freshness.scan(str(repo))
    assert "  stale: true\n" in open(path).read()
    assert any("fact-a" in ln for ln in lines)


def test_stale_paths_quoted_and_roundtrip():
    text = "---\nname: a\nmetadata:\n  type: project\n---\nB\n"
    out = nelly_freshness._mark_text(text, ["src/a,b.py", "c#d"], "2026-01-01")
    rec = build_index._parse_frontmatter_block(out.split("---\n")[1])
    assert rec["stale_paths"] == ["src/a,b.py", "c#d"]
    assert '"src/a,b.py"' in out and '"c#d"' in out
    assert "stale_paths: [src/a.py]" in nelly_freshness._mark_text(text, ["src/a.py"], "d")


def test_mark_text_replaces_old_block_stale_keys_valid_yaml():
    text = ("---\nname: a\nmetadata:\n  type: project\n  stale: false\n  stale_paths:\n    - old\n"
            "  verified: 2026-01-01\n---\nB\n")
    out = nelly_freshness._mark_text(text, ["src/a.py"], "2026-02-02")
    assert out.count("stale:") == 1 and out.count("stale_paths") == 1 and "- old" not in out
    meta = _fm(out)["metadata"]
    assert meta["stale"] is True and meta["stale_paths"] == ["src/a.py"] and meta["verified"]


def test_mark_text_flow_stale_inserted_after_last_key():
    text = ("---\nname: a\nmetadata:\n  type: project\n  stale: false\n  stale_paths: [x]\n"
            "  basis: observed\n---\nB\n")
    out = nelly_freshness._mark_text(text, ["p"], "2026-02-02")
    assert out == ("---\nname: a\nmetadata:\n  type: project\n  basis: observed\n"
                   "  stale: true\n  stale_since: 2026-02-02\n  stale_paths: [p]\n---\nB\n")


def test_mark_text_block_sources_inserted_after_last_nested_item():
    text = ("---\nname: a\nmetadata:\n  type: project\n  sources:\n    - path: x\n      hash: h\n---\nB\n")
    out = nelly_freshness._mark_text(text, ["x"], "2026-02-02")
    assert out == text.replace("      hash: h\n", "      hash: h\n  stale: true\n  stale_since: 2026-02-02\n  stale_paths: [x]\n")


def test_held_lock_scan_returns_within_budget(repo):
    import multiprocessing
    put_file(repo, "src/a.py", "new")
    for i in range(3):
        make_entry(repo, f"fact-{i}", {"src/a.py": "old"})
    mem = nelly_memory.memory_dir(str(repo))
    ready, release = multiprocessing.Event(), multiprocessing.Event()
    proc = multiprocessing.Process(target=_hold_lock, args=(mem, ready, release))
    proc.start()
    try:
        assert ready.wait(5)
        start = time.monotonic()
        lines = nelly_freshness.scan(str(repo), budget=0.3)
        assert time.monotonic() - start <= 0.3 + 0.3
        assert not any("marked stale" in ln for ln in lines)
    finally:
        release.set()
        proc.join(5)


def _hold_lock(mem, ready, release):
    with nelly_store.lock(mem):
        ready.set()
        release.wait(10)
