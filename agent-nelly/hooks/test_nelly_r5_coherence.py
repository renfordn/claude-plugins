"""Slice 2E (R5 coherence): SessionStart stale commands, lexical roots, batching, pending location,
stop-capture refresh prompt. Runs against the conftest-provided temp CLAUDE_PLUGIN_DATA (never a real root)."""
import io
import json
import os
import shlex
import subprocess
import sys
import time

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))

import build_index  # noqa: E402
import nelly_freshness  # noqa: E402
import nelly_memory  # noqa: E402
import nelly_pending  # noqa: E402
import nelly_stop_capture  # noqa: E402
import nelly_store  # noqa: E402
from research_digest import blob_hash  # noqa: E402

EVIDENCE = os.path.join(HERE, "..", "scripts", "nelly_evidence.py")


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True,
                          text=True).stdout.strip()


@pytest.fixture
def repo(tmp_path):
    r = (tmp_path / "repo").resolve()
    (r / "src").mkdir(parents=True)
    (r / "src" / "a.py").write_text("old\n")
    git(r, "init", "-q", "-b", "main")
    git(r, "config", "user.email", "t@example.com")
    git(r, "config", "user.name", "t")
    git(r, "add", "-A")
    git(r, "commit", "-q", "-m", "init")
    return r


def make_entry(repo, name, sources, verified="2026-01-01", stale_since=None):
    cwd = str(repo)
    nelly_memory.ensure_entries_dir(cwd)
    path = nelly_memory.entry_path(cwd, name)
    src = ", ".join("{path: %s, hash: %s}" % (p, blob_hash(t.encode())) for p, t in sources.items())
    lines = ["---", f"name: {name}", "description: d", "metadata:", "  type: project",
             f"  sources: [{src}]", "  revision: abc", f"  verified: {verified}", "  basis: observed"]
    if stale_since:
        lines += ["  stale: true", f"  stale_since: {stale_since}", "  stale_paths: [src/a.py]"]
    lines += ["---", "", "Body."]
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    build_index.upsert_project_entry(cwd, path)
    return path


def commands(lines):
    """The runnable command on each line that carries one (the env prefix starts it)."""
    return [ln[ln.index("CLAUDE_PLUGIN_DATA="):] for ln in lines
            if "nelly_evidence.py" in ln and "CLAUDE_PLUGIN_DATA=" in ln]


# --- F2: already-stale entries get runnable commands (oldest stale_since first, capped) ---

def test_second_scan_prints_command_for_already_stale_entry(repo):
    make_entry(repo, "fact-a", {"src/a.py": "old\n"})
    (repo / "src" / "a.py").write_text("new\n")
    first = nelly_freshness.scan(str(repo))
    assert any("refresh" in c and "fact-a" in c for c in commands(first))
    second = nelly_freshness.scan(str(repo))
    cmds = commands(second)
    assert len(cmds) == 1
    assert "fact-a" in cmds[0] and "refresh" in cmds[0]
    assert f"--cwd {shlex.quote(str(repo))}" in cmds[0] and "--slug fact-a" in cmds[0]
    assert "CLAUDE_PLUGIN_DATA=" in cmds[0]


def test_already_stale_oldest_first_capped_with_more_and_list_command(repo):
    for i in range(7):
        make_entry(repo, f"fact-{i}", {"src/a.py": "old\n"}, stale_since=f"2026-02-0{i + 1}")
    lines = nelly_freshness.scan(str(repo))
    cmds = commands(lines)
    named = [c for c in cmds if "refresh" in c]
    assert len(named) == nelly_freshness.NAMED_CAP == 5
    assert [("--slug fact-%d" % i) in named[i] for i in range(5)] == [True] * 5  # oldest first
    more = [ln for ln in lines if "+2 more" in ln]
    assert more and " stale --cwd " in more[0] and "nelly_evidence.py" in more[0]


def test_stale_line_says_recheck_rewrite_then_refresh_and_confirm(repo):
    make_entry(repo, "fact-a", {"src/a.py": "old\n"})
    (repo / "src" / "a.py").write_text("new\n")
    text = "\n".join(nelly_freshness.scan(str(repo)))
    assert "rewrite" in text and "archive" in text and "--confirm-unchanged" in text


# --- F3: lexical repo root for printed --cwd and slug derivation ---

def test_symlinked_repo_printed_command_succeeds(tmp_path, repo):
    link = tmp_path / "link"
    os.symlink(str(repo), str(link))
    rec = subprocess.run([sys.executable, EVIDENCE, "record", "--cwd", str(link), "--slug", "fact-a",
                          "--type", "project", "--description", "d", "--body", "b", "--paths", "src/a.py",
                          "--basis", "observed"], capture_output=True, text=True)
    assert rec.returncode == 0, rec.stderr
    (repo / "src" / "a.py").write_text("new\n")
    git(repo, "commit", "-qam", "change")
    cmds = commands(nelly_freshness.scan(str(link)))
    assert cmds and f"--cwd {shlex.quote(str(link))}" in cmds[0]
    out = subprocess.run(cmds[0] + " --confirm-unchanged", shell=True, capture_output=True, text=True)
    assert out.returncode == 0, out.stderr


# --- cleanup: one index write per scan ---

def test_scan_batches_index_updates(repo, monkeypatch):
    for i in range(3):
        make_entry(repo, f"fact-{i}", {"src/a.py": "old\n"})
    (repo / "src" / "a.py").write_text("new\n")
    calls = []
    real = nelly_store.upsert_index
    monkeypatch.setattr(nelly_store, "upsert_index", lambda *a, **k: calls.append(a) or real(*a, **k))
    nelly_freshness.scan(str(repo))
    assert len(calls) == 1
    with open(os.path.join(nelly_memory.memory_dir(str(repo)), "nelly-index.json")) as fh:
        recs = {r["slug"]: r for r in json.load(fh)}
    assert all(recs[f"fact-{i}"]["stale"] is True for i in range(3))


# --- F8: stop capture prompts refresh when a stale record already covers the paths ---

def _stop_out(monkeypatch, capsys, repo, tmp_path, records):
    d = nelly_memory.memory_dir(str(repo))
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "nelly-index.json"), "w") as fh:
        json.dump(records, fh)
    answer = "`save()` in src/store.py writes the cache to disk."
    (repo / "src" / "store.py").write_text("def save(c):\n    pass\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "store")
    t = tmp_path / "t.jsonl"
    ev = [{"type": "user", "message": {"role": "user", "content": "How is the cache saved?"}},
          {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": answer}]}}]
    t.write_text("\n".join(json.dumps(e) for e in ev) + "\n")
    payload = {"hook_event_name": "Stop", "session_id": "s", "transcript_path": str(t), "cwd": str(repo),
               "permission_mode": "default", "stop_hook_active": False}
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
    nelly_stop_capture.main()
    return capsys.readouterr().out


def test_stop_capture_prompts_refresh_for_stale_covering_record(tmp_path, repo, monkeypatch, capsys):
    rec = {"slug": "cache-save", "file_path": "entries/cache-save.md", "type": "project", "stale": True,
           "stale_paths": ["src/store.py"], "sources": [{"path": "src/store.py", "hash": "x"}]}
    out = _stop_out(monkeypatch, capsys, repo, tmp_path, [rec])
    reason = json.loads(out)["reason"]
    assert " refresh " in reason and "--slug cache-save" in reason and "--paths src/store.py" in reason
    assert " record " not in reason
    assert "stale" in reason.splitlines()[0] and "not recorded in memory" not in reason
    assert "CLAUDE_PLUGIN_DATA=" in reason


def test_stop_capture_still_records_when_no_stale_record_covers(tmp_path, repo, monkeypatch, capsys):
    out = _stop_out(monkeypatch, capsys, repo, tmp_path, [])
    assert " record " in json.loads(out)["reason"]


# --- F5: pending/resolved findings are machine-local ---

@pytest.fixture
def split_roots(tmp_path, monkeypatch):
    monkeypatch.setattr(nelly_memory, "BASE", str(tmp_path / "shared" / "mem"))
    monkeypatch.setattr(nelly_memory, "LOCAL_BASE", str(tmp_path / "data" / "local"))


def test_pending_and_resolved_live_under_local_state_dir(repo, split_roots):
    (repo / "src" / "n.py").write_text("x = 1\n")
    pid = nelly_pending.add(str(repo), "s", ["src/n.py"], [], "uncommitted")
    local = nelly_memory.local_state_dir(str(repo))
    shared = nelly_memory.memory_dir(str(repo))
    assert os.path.isfile(os.path.join(local, "pending-findings", pid + ".json"))
    assert not os.path.exists(os.path.join(shared, "pending-findings"))
    assert nelly_pending._resolve(str(repo), pid, "dismissed", "checked") == 0
    assert os.path.isfile(os.path.join(local, "resolved-findings", pid + ".json"))
    assert not os.path.exists(os.path.join(shared, "resolved-findings"))


def test_existing_shared_records_migrate_on_first_access(repo, split_roots):
    shared = nelly_memory.memory_dir(str(repo))
    for sub in ("pending-findings", "resolved-findings"):
        os.makedirs(os.path.join(shared, sub))
    rec = {"id": "abc123", "summary": "s", "paths": ["src/a.py"], "symbols": [], "reason": "uncommitted",
           "branch": "main", "head": "h", "hashes": {}, "captured": "2026-01-01"}
    for sub in ("pending-findings", "resolved-findings"):
        with open(os.path.join(shared, sub, "abc123.json"), "w") as fh:
            json.dump(rec, fh)
    assert [r["id"] for r in nelly_pending.list_pending(str(repo))] == ["abc123"]
    local = nelly_memory.local_state_dir(str(repo))
    assert os.path.isfile(os.path.join(local, "pending-findings", "abc123.json"))
    assert os.path.isfile(os.path.join(local, "resolved-findings", "abc123.json"))
    assert not os.path.exists(os.path.join(shared, "pending-findings", "abc123.json"))
    assert not os.path.exists(os.path.join(shared, "resolved-findings", "abc123.json"))


def test_second_sessionstart_prints_command_for_already_stale_entry(repo):
    import nelly_session_start
    make_entry(repo, "fact-a", {"src/a.py": "old\n"})
    (repo / "src" / "a.py").write_text("new\n")
    first = nelly_session_start._release5_lines(str(repo))
    assert any("marked stale" in ln for ln in first)
    second = nelly_session_start._release5_lines(str(repo))
    assert not any("marked stale" in ln for ln in second)
    assert any("fact-a" in c and " refresh " in c for c in commands(second))


# --- F13: one placeholder guard for pending and evidence ---

@pytest.mark.parametrize("argv", [["--summary", "<one-line finding>", "--paths", "src/a.py"],
                                  ["--summary", "real", "--paths", "<paths>"]])
def test_pending_add_rejects_placeholders(repo, argv):
    assert nelly_pending.main(["add", "--cwd", str(repo), *argv]) == 3
    assert nelly_pending.list_pending(str(repo)) == []


def test_reject_placeholder_helper_is_shared():
    import nelly_frontmatter
    with pytest.raises(ValueError, match="placeholder"):
        nelly_frontmatter.reject_placeholder("--x", " <val> ")
    nelly_frontmatter.reject_placeholder("--x", "real <b> text")
    nelly_frontmatter.reject_placeholder("--x", None)


# --- F11/F14: one scalar reader that unquotes ---

def test_read_scalar_unquotes_and_proactive_description_uses_it():
    import nelly_frontmatter
    import nelly_proactive_surface
    block = 'name: "yes"\ndescription: "save_user: writes to db"\n'
    assert nelly_frontmatter.read_scalar(block, "description") == "save_user: writes to db"
    assert nelly_frontmatter.read_scalar(block, "name") == "yes"
    assert nelly_frontmatter.read_scalar(block, "missing") is None
    assert nelly_proactive_surface._description("---\n" + block + "---\nB") == "save_user: writes to db"
    assert build_index._parse_frontmatter_block(block)["slug"] == "yes"
