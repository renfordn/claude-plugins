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
    assert any("1 memory entries marked stale" in ln and "fact-a (src/a.py)" in ln for ln in lines)
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


def _meta_text(extra):
    return "---\nname: n\ndescription: d\nmetadata:\n" + extra + "---\n\nBody.\n"


def test_mark_text_replaces_block_stale_paths_with_blank_line_without_orphans():
    old = _meta_text("  type: project\n  stale: true\n  stale_since: 2026-01-01\n"
                     "  stale_paths:\n    - a\n\n    - b\n  basis: observed\n")
    new = nelly_freshness._mark_text(old, ["c"], "2026-05-05")
    assert new == _meta_text("  type: project\n  basis: observed\n  stale: true\n"
                             "  stale_since: 2026-05-05\n  stale_paths: [c]\n")


def test_mark_text_child_indent_skips_leading_comments_and_blanks():
    old = _meta_text("\n# comment\n      # deeper comment\n    type: project\n")
    new = nelly_freshness._mark_text(old, ["c"], "2026-05-05")
    assert new == _meta_text("\n# comment\n      # deeper comment\n    type: project\n"
                             "    stale: true\n    stale_since: 2026-05-05\n    stale_paths: [c]\n")


def test_session_line_command_is_absolute_env_prefixed_and_runs_without_plugin_env(repo, tmp_path):
    import shlex
    put_file(repo, "src/a.py", "old")
    make_entry(repo, "fact-a", {"src/a.py": "old"})
    put_file(repo, "src/a.py", "new")
    cmd = _commands(nelly_freshness.scan(str(repo)))[0]
    argv = shlex.split(cmd)
    assert argv[0].startswith("CLAUDE_PLUGIN_DATA=") and argv[1] == "python3"
    assert os.path.isabs(argv[2]) and os.path.isfile(argv[2]) and argv[2].endswith("nelly_evidence.py")
    env = {k: v for k, v in os.environ.items() if not k.startswith("CLAUDE_PLUGIN")}
    env.update(HOME=str(tmp_path / "home"), CLAUDE_CONFIG_DIR=str(tmp_path / "cfg"))
    proc = subprocess.run(cmd, shell=True, capture_output=True, text=True, env=env, cwd=str(tmp_path))
    assert proc.returncode == 0, proc.stderr
    text = open(nelly_memory.entry_path(str(repo), "fact-a")).read()
    assert "stale:" not in text and "stale_paths" not in text


def _commands(lines):
    """Every runnable command in the SessionStart lines (a line's text from CLAUDE_PLUGIN_DATA=)."""
    return [ln[ln.index("CLAUDE_PLUGIN_DATA="):].strip() for ln in lines if "CLAUDE_PLUGIN_DATA=" in ln]


def _clean_env(tmp_path):
    env = {k: v for k, v in os.environ.items() if not k.startswith("CLAUDE_PLUGIN")}
    env.update(HOME=str(tmp_path / "home"), CLAUDE_CONFIG_DIR=str(tmp_path / "cfg"))
    return env


def _g(repo, *args):
    subprocess.run(["git", "-c", "user.email=t@e.x", "-c", "user.name=t", "-C", str(repo), *args],
                   check=True, capture_output=True)


def test_command_drops_deleted_committed_source_and_runs_end_to_end(repo, tmp_path):
    put_file(repo, "src/a.py", "old")
    put_file(repo, "src/b.py", "old")
    _g(repo, "add", ".")
    _g(repo, "commit", "-qm", "init")
    path = make_entry(repo, "fact-a", {"src/a.py": "old", "src/b.py": "old"})
    _g(repo, "rm", "-q", "src/a.py")
    put_file(repo, "src/b.py", "new")
    _g(repo, "commit", "-qam", "change")
    cmds = _commands(nelly_freshness.scan(str(repo)))
    assert len(cmds) == 1
    assert "--drop-paths src/a.py" in cmds[0] and "--paths src/b.py" in cmds[0]
    proc = subprocess.run(cmds[0], shell=True, capture_output=True, text=True, env=_clean_env(tmp_path),
                          cwd=str(tmp_path))
    assert proc.returncode == 0, proc.stderr
    text = open(path).read()
    assert "src/a.py" not in text and "stale:" not in text


def test_deleted_but_uncommitted_source_stays_under_paths(repo):
    put_file(repo, "src/a.py", "old")
    _g(repo, "add", ".")
    _g(repo, "commit", "-qm", "init")
    make_entry(repo, "fact-a", {"src/a.py": "old"})
    os.remove(repo / "src" / "a.py")  # still in HEAD: dropping would be refused
    cmds = _commands(nelly_freshness.scan(str(repo)))
    assert "--drop-paths" not in cmds[0] and "--paths src/a.py" in cmds[0]


def test_one_runnable_command_per_named_entry_up_to_cap(repo):
    for i in range(nelly_freshness.NAMED_CAP + 2):
        put_file(repo, f"src/f{i}.py", "new")
        make_entry(repo, f"fact-{i}", {f"src/f{i}.py": "old"})
    cmds = _commands(nelly_freshness.scan(str(repo)))
    assert len(cmds) == len(set(cmds)) == nelly_freshness.NAMED_CAP
