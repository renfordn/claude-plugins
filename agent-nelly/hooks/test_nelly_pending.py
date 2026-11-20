"""Tests for hooks/nelly_pending.py -- the pending-findings queue (R18, slice 1C).

In-process calls use a monkeypatched nelly_memory.BASE; CLI calls run the script as a
subprocess with CLAUDE_PLUGIN_DATA pointing at the same tmp dir, so both resolve the same
<memory_dir>. Repos are real temp git repos.
"""
import hashlib
import json
import os
import subprocess
import sys

import pytest

import shlex

import nelly_memory
import nelly_pending

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import nelly_evidence  # noqa: E402

HOOK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nelly_pending.py")
V1 = "def save():\n    return 1\n"
V2 = "def save():\n    return 2\n"


@pytest.fixture(autouse=True)
def isolated_base(tmp_path, monkeypatch):
    data = str(tmp_path / "data")
    base = os.path.join(data, "agent-nelly-memory")
    monkeypatch.setattr(nelly_memory, "BASE", base)
    monkeypatch.setattr(nelly_memory, "LOCAL_BASE", base)
    return data


def _git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], check=True,
                          capture_output=True, text=True).stdout.strip()


@pytest.fixture
def repo(tmp_path):
    r = (tmp_path / "repo").resolve()
    (r / "src").mkdir(parents=True)
    (r / "src" / "base.py").write_text("x = 1\n")
    _git(r, "init", "-q", "-b", "main")
    _git(r, "config", "user.email", "t@example.com")
    _git(r, "config", "user.name", "t")
    _git(r, "add", "-A")
    _git(r, "commit", "-q", "-m", "init")
    return r


def _commit(repo, rel, content):
    (repo / rel).write_text(content)
    _git(repo, "add", rel)
    _git(repo, "commit", "-q", "-m", f"commit {rel}")


def _pdir(repo, sub="pending-findings"):
    return os.path.join(nelly_memory.memory_dir(str(repo)), sub)


def _cli(isolated_base, *args):
    env = dict(os.environ, CLAUDE_PLUGIN_DATA=isolated_base)
    env.pop("CLAUDE_PLUGIN_OPTION_SHARED_MEMORY_ROOT", None)
    return subprocess.run([sys.executable, HOOK, *args], capture_output=True, text=True, env=env,
                          stdin=subprocess.DEVNULL, timeout=30)


def _add_dirty(repo, rel="src/store.py", content=V1, summary="save() in src/store.py writes the cache."):
    (repo / rel).write_text(content)
    return nelly_pending.add(str(repo), summary, [rel], ["save"], "uncommitted")


# 9: add / list_pending --------------------------------------------------------------------

def test_add_writes_record_and_lists_it(repo):
    pid = _add_dirty(repo)
    path = os.path.join(_pdir(repo), pid + ".json")
    assert os.path.isfile(path)
    with open(path) as fh:
        rec = json.load(fh)
    assert rec["id"] == pid
    assert rec["paths"] == ["src/store.py"]
    assert rec["symbols"] == ["save"]
    assert rec["reason"] == "uncommitted"
    assert rec["hashes"] == {"src/store.py": hashlib.sha256(V1.encode()).hexdigest()}
    assert rec["head"] == _git(repo, "rev-parse", "HEAD")
    assert rec["branch"] == "main"
    body = {k: v for k, v in rec.items() if k not in ("id", "captured")}
    assert pid == hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
    listed = nelly_pending.list_pending(str(repo))
    assert [r["id"] for r in listed] == [pid]


@pytest.mark.parametrize("paths,symbols,reason", [
    ([], [], "uncommitted"),
    ([f"src/f{i}.py" for i in range(13)], [], "uncommitted"),
    (["src/store.py"], [f"sym{i}" for i in range(21)], "uncommitted"),
    (["src/store.py"], [], "because"),
])
def test_add_rejects_limits_and_reason(repo, paths, symbols, reason):
    (repo / "src" / "store.py").write_text(V1)
    for p in paths:
        (repo / p).write_text("y = 1\n")
    with pytest.raises(ValueError):
        nelly_pending.add(str(repo), "summary", paths, symbols, reason)
    assert nelly_pending.list_pending(str(repo)) == []


@pytest.mark.parametrize("reason", ["uncommitted", "unverified", "conflict", "unavailable"])
def test_add_accepts_each_reason(repo, reason):
    (repo / "src" / "store.py").write_text(V1)
    pid = nelly_pending.add(str(repo), "summary", ["src/store.py"], [], reason)
    assert os.path.isfile(os.path.join(_pdir(repo), pid + ".json"))


def test_duplicate_add_collapses(repo):
    a = _add_dirty(repo)
    b = _add_dirty(repo)
    assert a == b
    assert os.listdir(_pdir(repo)) == [a + ".json"]


def test_different_content_is_a_distinct_candidate(repo):
    a = _add_dirty(repo, content=V1)
    b = _add_dirty(repo, content=V2)
    assert a != b
    assert sorted(os.listdir(_pdir(repo))) == sorted([a + ".json", b + ".json"])


# 10: readiness ----------------------------------------------------------------------------

def test_only_exact_committed_content_is_ready(repo):
    pid = _add_dirty(repo, content=V1)
    rec = nelly_pending.list_pending(str(repo))[0]
    assert rec["id"] == pid
    assert nelly_pending.readiness(str(repo), rec) == "pending"

    _commit(repo, "src/store.py", V1)
    assert nelly_pending.readiness(str(repo), rec) == "ready"


def test_committed_different_content_is_changed(repo):
    _add_dirty(repo, content=V1)
    rec = nelly_pending.list_pending(str(repo))[0]
    _commit(repo, "src/store.py", V2)
    assert nelly_pending.readiness(str(repo), rec) == "changed"


# 11: session_hint -------------------------------------------------------------------------

def test_session_hint_empty_queue(repo):
    assert nelly_pending.session_hint(str(repo)) == []


def test_session_hint_caps_two_ready_two_changed(repo):
    summaries = {}
    for i in range(3):
        rel = f"src/ready{i}.py"
        content = f"r = {i}\n"
        (repo / rel).write_text(content)
        nelly_pending.add(str(repo), f"READY-{i} finding", [rel], [], "uncommitted")
        _commit(repo, rel, content)
    for i in range(3):
        rel = f"src/changed{i}.py"
        (repo / rel).write_text(f"c = {i}\n")
        nelly_pending.add(str(repo), f"CHANGED-{i} finding", [rel], [], "uncommitted")
        _commit(repo, rel, f"c = {i + 100}\n")
    (repo / "src" / "wip.py").write_text("w = 1\n")
    nelly_pending.add(str(repo), "PENDING-0 finding", ["src/wip.py"], [], "uncommitted")

    lines = nelly_pending.session_hint(str(repo))
    assert isinstance(lines, list) and all(isinstance(l, str) for l in lines)
    text = "\n".join(lines)
    assert sum(f"READY-{i}" in text for i in range(3)) == 2
    assert sum(f"CHANGED-{i}" in text for i in range(3)) == 2
    assert "PENDING-0" not in text


# 12: CLI list / resolve -------------------------------------------------------------------

def test_cli_list_reports_readiness(repo, isolated_base):
    pid = _add_dirty(repo)
    r = _cli(isolated_base, "list", "--cwd", str(repo))
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    assert isinstance(data, list) and len(data) == 1
    assert data[0]["id"] == pid and data[0]["readiness"] == "pending"


def test_verified_resolution_requires_committed_sources(repo, isolated_base):
    pid = _add_dirty(repo)
    r = _cli(isolated_base, "resolve", pid, "verified", "--evidence", "read the code", "--cwd", str(repo))
    assert r.returncode == 3, (r.stdout, r.stderr)
    assert os.path.isfile(os.path.join(_pdir(repo), pid + ".json"))
    assert not os.path.exists(os.path.join(_pdir(repo, "resolved-findings"), pid + ".json"))

    _commit(repo, "src/store.py", V1)
    r = _cli(isolated_base, "resolve", pid, "verified", "--evidence", "read the code", "--cwd", str(repo))
    assert r.returncode == 0, (r.stdout, r.stderr)
    assert "nelly_evidence.py record" in r.stdout
    assert not os.path.exists(os.path.join(_pdir(repo), pid + ".json"))
    with open(os.path.join(_pdir(repo, "resolved-findings"), pid + ".json")) as fh:
        res = json.load(fh)
    assert res["id"] == pid
    assert res["outcome"] == "verified"
    assert res["evidence"] == "read the code"
    assert len(res["resolved"]) == 10 and res["resolved"][4] == "-"
    assert nelly_pending.list_pending(str(repo)) == []


def test_dismissed_needs_only_evidence(repo, isolated_base):
    pid = _add_dirty(repo)
    r = _cli(isolated_base, "resolve", pid, "dismissed", "--cwd", str(repo))
    assert r.returncode == 3
    assert os.path.isfile(os.path.join(_pdir(repo), pid + ".json"))

    r = _cli(isolated_base, "resolve", pid, "dismissed", "--evidence", "wrong file", "--cwd", str(repo))
    assert r.returncode == 0, (r.stdout, r.stderr)
    assert not os.path.exists(os.path.join(_pdir(repo), pid + ".json"))
    with open(os.path.join(_pdir(repo, "resolved-findings"), pid + ".json")) as fh:
        res = json.load(fh)
    assert res["outcome"] == "dismissed" and res["evidence"] == "wrong file"


def test_resolve_unknown_id_exits_4(repo, isolated_base):
    r = _cli(isolated_base, "resolve", "0" * 64, "dismissed", "--evidence", "x", "--cwd", str(repo))
    assert r.returncode == 4


# decisions 2 and 3 --------------------------------------------------------------------------

def test_add_truncates_long_summary_without_error(repo):
    (repo / "src" / "store.py").write_text(V1)
    pid = nelly_pending.add(str(repo), "s" * 600, ["src/store.py"], [], "uncommitted")
    rec = nelly_pending.list_pending(str(repo))[0]
    assert rec["id"] == pid and rec["summary"] == "s" * 500


def test_head_match_but_worktree_edited_again_is_not_ready(repo):
    _add_dirty(repo, content=V1)
    rec = nelly_pending.list_pending(str(repo))[0]
    _commit(repo, "src/store.py", V1)
    (repo / "src" / "store.py").write_text(V1 + "# more\n")
    assert nelly_pending.readiness(str(repo), rec) == "changed"


# F1: printed commands are runnable without CLAUDE_PLUGIN_ROOT / CLAUDE_PLUGIN_DATA ----------------

def test_cmd_helper_output_runs_with_plugin_env_unset(repo, isolated_base, tmp_path):
    pid = _add_dirty(repo)
    cmd = nelly_pending._cmd("hooks/nelly_pending.py", "list", "--cwd", str(repo))
    assert "CLAUDE_PLUGIN_ROOT" not in cmd and cmd.startswith("CLAUDE_PLUGIN_DATA=")
    env = {k: v for k, v in os.environ.items()
           if k not in ("CLAUDE_PLUGIN_DATA", "CLAUDE_PLUGIN_ROOT", "CLAUDE_PLUGIN_OPTION_SHARED_MEMORY_ROOT")}
    env["CLAUDE_CONFIG_DIR"] = str(tmp_path / "cfg")
    r = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True, env=env, timeout=30)
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout)[0]["id"] == pid


def test_cmd_helper_quotes_arguments(repo):
    import shlex
    cmd = nelly_pending._cmd("scripts/x.py", "--description", "a b; rm -rf /", "--paths", "it's.py")
    toks = shlex.split(cmd)
    assert toks[-4:] == ["--description", "a b; rm -rf /", "--paths", "it's.py"]
    assert os.path.isabs(toks[-5]) and toks[-5].endswith("scripts/x.py")


def test_cmd_helper_carries_shared_root_when_set(monkeypatch):
    monkeypatch.setattr(nelly_memory, "SHARED_ROOT", "/some/shared root")
    cmd = nelly_pending._cmd("scripts/x.py")
    assert "CLAUDE_PLUGIN_OPTION_SHARED_MEMORY_ROOT='/some/shared root'" in cmd


def test_resolve_output_command_is_absolute_and_project_typed(repo, isolated_base):
    pid = _add_dirty(repo)
    _commit(repo, "src/store.py", V1)
    r = _cli(isolated_base, "resolve", pid, "verified", "--evidence", "read it", "--cwd", str(repo))
    assert r.returncode == 0, r.stderr
    assert "CLAUDE_PLUGIN_ROOT" not in r.stdout
    assert "--type project" in r.stdout and "CLAUDE_PLUGIN_DATA=" in r.stdout


# F4: paths resolve from the repo toplevel, not cwd -------------------------------------------

def test_readiness_and_resolve_work_from_a_subdirectory(repo, isolated_base):
    pid = _add_dirty(repo)
    rec = nelly_pending.list_pending(str(repo))[0]
    sub = str(repo / "src")
    assert nelly_pending.readiness(sub, rec) == "pending"
    _commit(repo, "src/store.py", V1)
    assert nelly_pending.readiness(sub, rec) == "ready"
    r = _cli(isolated_base, "resolve", pid, "verified", "--evidence", "ok", "--cwd", sub)
    assert r.returncode == 0, (r.stdout, r.stderr)


# F7: queue cap, vanished paths, hint time budget -----------------------------------------------

def _archived(repo):
    d = _pdir(repo, "resolved-findings")
    return [json.load(open(os.path.join(d, n))) for n in sorted(os.listdir(d))] if os.path.isdir(d) else []


def test_queue_is_capped_at_50_and_oldest_expire(repo):
    for i in range(52):
        (repo / "src" / f"f{i}.py").write_text(f"v = {i}\n")
        nelly_pending.add(str(repo), f"finding {i}", [f"src/f{i}.py"], [], "uncommitted")
    assert len(nelly_pending.list_pending(str(repo))) == 50
    gone = _archived(repo)
    assert len(gone) == 2 and all(r["outcome"] == "expired" for r in gone)


def test_records_with_vanished_paths_are_expired(repo):
    (repo / "src" / "old.py").write_text("o = 1\n")
    nelly_pending.add(str(repo), "old finding", ["src/old.py"], [], "uncommitted")
    (repo / "src" / "old.py").unlink()
    (repo / "src" / "new.py").write_text("n = 1\n")
    nelly_pending.add(str(repo), "new finding", ["src/new.py"], [], "uncommitted")
    assert [r["summary"] for r in nelly_pending.list_pending(str(repo))] == ["new finding"]
    assert [r["outcome"] for r in _archived(repo)] == ["expired"]


def test_session_hint_stops_after_half_a_second(repo, monkeypatch):
    for i in range(5):
        (repo / "src" / f"g{i}.py").write_text(f"v = {i}\n")
        nelly_pending.add(str(repo), f"finding {i}", [f"src/g{i}.py"], [], "uncommitted")
    clock = {"t": 0.0}

    def fake_monotonic():
        clock["t"] += 0.3
        return clock["t"]

    calls = []
    monkeypatch.setattr(nelly_pending.time, "monotonic", fake_monotonic)
    monkeypatch.setattr(nelly_pending, "readiness", lambda cwd, rec: calls.append(rec["id"]) or "ready")
    nelly_pending.session_hint(str(repo))
    assert len(calls) <= 2


# F10: exit codes --------------------------------------------------------------------------------

def test_missing_data_dir_is_a_clean_exit_5(repo, tmp_path):
    env = {k: v for k, v in os.environ.items()
           if k not in ("CLAUDE_PLUGIN_DATA", "CLAUDE_PLUGIN_OPTION_SHARED_MEMORY_ROOT")}
    env["CLAUDE_CONFIG_DIR"] = str(tmp_path / "cfg")
    r = subprocess.run([sys.executable, HOOK, "list", "--cwd", str(repo)], capture_output=True, text=True,
                       env=env, stdin=subprocess.DEVNULL, timeout=30)
    assert r.returncode == 5
    assert "Traceback" not in r.stderr and "CLAUDE_PLUGIN_DATA" in r.stderr


def test_usage_error_exits_2(repo, isolated_base):
    assert _cli(isolated_base, "resolve").returncode == 2


# round 2: F18 record_cmd, F1 hint command, F19 add CLI, F20 symlinked cwd ---------------------

def _argv_after_script(cmd, script_name):
    toks = shlex.split(cmd)
    i = next(n for n, t in enumerate(toks) if t.endswith(script_name))
    return toks[i + 1:]


def test_record_cmd_parses_with_nelly_evidence_parser(repo):
    cmd = nelly_pending.record_cmd(str(repo), ["src/a.py", "src/b.py"], "it's a desc; x", "body text\nline2",
                                   symbols=["save", "load"])
    args = nelly_evidence._parser().parse_args(_argv_after_script(cmd, "nelly_evidence.py"))
    assert args.cmd == "record" and args.cwd == str(repo)
    assert args.paths == ["src/a.py", "src/b.py"] and args.symbols == ["save", "load"]
    assert args.body == "body text\nline2" and args.description == "it's a desc; x"
    assert args.type == "project" and args.basis == "observed" and args.slug


def test_record_cmd_placeholder_slug_default(repo):
    cmd = nelly_pending.record_cmd(str(repo), ["src/a.py"], "d", "<one-paragraph finding>")
    args = nelly_evidence._parser().parse_args(_argv_after_script(cmd, "nelly_evidence.py"))
    assert args.slug == "<kebab-slug>" and args.body == "<one-paragraph finding>"


def test_resolve_verified_command_runs_end_to_end(repo, isolated_base, tmp_path):
    pid = _add_dirty(repo)
    _commit(repo, "src/store.py", V1)
    r = _cli(isolated_base, "resolve", pid, "verified", "--evidence", "read it", "--cwd", str(repo))
    assert r.returncode == 0, r.stderr
    cmd = r.stdout.split("Record it with: ", 1)[1].strip()
    env = {k: v for k, v in os.environ.items()
           if k not in ("CLAUDE_PLUGIN_DATA", "CLAUDE_PLUGIN_ROOT", "CLAUDE_PLUGIN_OPTION_SHARED_MEMORY_ROOT")}
    env["CLAUDE_CONFIG_DIR"] = str(tmp_path / "cfg")
    out = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True, env=env, timeout=60)
    assert out.returncode == 0, (out.stdout, out.stderr)
    written = json.loads(out.stdout)
    assert os.path.isfile(written["path"])


def test_session_hint_commands_are_runnable_shape(repo):
    (repo / "src" / "r.py").write_text("r = 1\n")
    nelly_pending.add(str(repo), "READY finding", ["src/r.py"], [], "uncommitted")
    _commit(repo, "src/r.py", "r = 1\n")
    (repo / "src" / "c.py").write_text("c = 1\n")
    nelly_pending.add(str(repo), "CHANGED finding", ["src/c.py"], [], "uncommitted")
    _commit(repo, "src/c.py", "c = 2\n")
    text = "\n".join(nelly_pending.session_hint(str(repo)))
    script = os.path.join(nelly_pending.PLUGIN_ROOT, "hooks", "nelly_pending.py")
    assert text.count(script) == 2 and "CLAUDE_PLUGIN_DATA=" in text
    assert "verified" in text and "dismissed" in text


def test_cli_add_queues_and_prints_id(repo, isolated_base):
    (repo / "src" / "store.py").write_text(V1)
    r = _cli(isolated_base, "add", "--cwd", str(repo), "--summary", "save() writes the cache",
             "--paths", "src/store.py", "--symbols", "save")
    assert r.returncode == 0, r.stderr
    pid = json.loads(r.stdout)["id"]
    rec = nelly_pending.list_pending(str(repo))[0]
    assert rec["id"] == pid and rec["reason"] == "uncommitted" and rec["symbols"] == ["save"]
    bad = _cli(isolated_base, "add", "--cwd", str(repo), "--summary", "x", "--paths", "src/nope.py")
    assert bad.returncode == 3


def test_symlinked_cwd_uses_the_lexical_store(repo, tmp_path):
    link = tmp_path / "link"
    os.symlink(str(repo), str(link))
    (repo / "src" / "store.py").write_text(V1)
    pid = nelly_pending.add(str(link), "s", ["src/store.py"], [], "uncommitted")
    assert os.path.isfile(os.path.join(nelly_memory.memory_dir(str(link)), "pending-findings", pid + ".json"))
    assert [r["id"] for r in nelly_pending.list_pending(str(link))] == [pid]
