"""Tests for hooks/nelly_stop_capture.py -- the Stop capture hook (R18, slice 1C).

Isolated like test_nelly_session_start.py: nelly_memory.BASE/LOCAL_BASE point at a tmp dir and
main() runs in-process with a monkeypatched stdin. Every repo is a real temp git repo so
committed-clean vs modified/untracked files are real git states.
"""
import hashlib
import io
import json
import os
import subprocess

import pytest

import shlex
import sys

import nelly_memory
import nelly_stop_capture

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import nelly_evidence  # noqa: E402

FINDING = "`save()` in src/store.py writes the cache to disk."
STORE_V1 = "def save(cache):\n    open('cache.json', 'w').write(cache)\n"


@pytest.fixture(autouse=True)
def isolated_base(tmp_path, monkeypatch):
    base = str(tmp_path / "data" / "agent-nelly-memory")
    monkeypatch.setattr(nelly_memory, "BASE", base)
    monkeypatch.setattr(nelly_memory, "LOCAL_BASE", base)
    monkeypatch.delenv("NELLY_CAPTURE", raising=False)
    return base


def _git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], check=True,
                          capture_output=True, text=True).stdout.strip()


@pytest.fixture
def repo(tmp_path):
    r = (tmp_path / "repo").resolve()
    (r / "src").mkdir(parents=True)
    (r / "src" / "store.py").write_text(STORE_V1)
    _git(r, "init", "-q", "-b", "main")
    _git(r, "config", "user.email", "t@example.com")
    _git(r, "config", "user.name", "t")
    _git(r, "add", "-A")
    _git(r, "commit", "-q", "-m", "init")
    return r


def _transcript(tmp_path, answer, user_prompt="How does the cache get saved?", name="t.jsonl"):
    path = tmp_path / name
    events = [
        {"type": "user", "message": {"role": "user", "content": user_prompt}},
        {"type": "assistant", "message": {"role": "assistant",
                                          "content": [{"type": "tool_use", "id": "x", "name": "Read",
                                                       "input": {}}]}},
        {"type": "user", "message": {"role": "user",
                                     "content": [{"type": "tool_result", "tool_use_id": "x",
                                                  "content": "file text"}]}},
        {"type": "assistant", "message": {"role": "assistant",
                                          "content": [{"type": "text", "text": answer}]}},
    ]
    path.write_text("\n".join(json.dumps(e) for e in events) + "\n")
    return str(path)


def _payload(cwd, transcript, session="s1", **over):
    p = {"hook_event_name": "Stop", "session_id": session, "transcript_path": transcript,
         "cwd": str(cwd), "permission_mode": "default", "stop_hook_active": False}
    p.update(over)
    return p


def _run(monkeypatch, capsys, payload):
    raw = payload if isinstance(payload, str) else json.dumps(payload)
    monkeypatch.setattr("sys.stdin", io.StringIO(raw))
    try:
        code = nelly_stop_capture.main()
    except SystemExit as exc:
        code = exc.code
    assert code in (0, None)
    return capsys.readouterr().out


def _blocked(out):
    assert out.strip(), "expected a block decision on stdout, got nothing"
    data = json.loads(out)
    assert data["decision"] == "block"
    assert isinstance(data["reason"], str) and data["reason"].strip()
    return data


def _write_index(cwd, records):
    d = nelly_memory.memory_dir(str(cwd))
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "nelly-index.json"), "w") as fh:
        json.dump(records, fh)


def _pending_files(cwd):
    d = os.path.join(nelly_memory.memory_dir(str(cwd)), "pending-findings")
    return sorted(os.listdir(d)) if os.path.isdir(d) else []


# 1 -------------------------------------------------------------------------------------------

def test_clear_source_linked_finding_requests_one_continuation(tmp_path, repo, monkeypatch, capsys):
    t = _transcript(tmp_path, FINDING)
    data = _blocked(_run(monkeypatch, capsys, _payload(repo, t)))
    reason = data["reason"]
    assert "nelly_evidence.py record" in reason or "agent-nelly" in reason
    assert _pending_files(repo) == []


def test_finding_from_last_assistant_message_field(tmp_path, repo, monkeypatch, capsys):
    t = _transcript(tmp_path, "Nothing to see here.")
    _blocked(_run(monkeypatch, capsys, _payload(repo, t, last_assistant_message=FINDING)))


@pytest.mark.parametrize("verb", ["writes", "calls", "returns", "routes", "validates", "persists",
                                  "reads", "stores", "emits", "raises", "loads", "parses",
                                  "registers", "handles"])
def test_each_behaviour_verb_counts(tmp_path, repo, monkeypatch, capsys, verb):
    t = _transcript(tmp_path, f"`save()` in src/store.py {verb} the cache.")
    _blocked(_run(monkeypatch, capsys, _payload(repo, t)))


# 2 -------------------------------------------------------------------------------------------

def _commit_file(repo, rel, content="x = 1\n"):
    (repo / rel).write_text(content)
    _git(repo, "add", rel)
    _git(repo, "commit", "-q", "-m", rel)


def test_no_repeat(tmp_path, repo, monkeypatch, capsys):
    t = _transcript(tmp_path, FINDING)
    assert _run(monkeypatch, capsys, _payload(repo, t, stop_hook_active=True)) == ""

    _blocked(_run(monkeypatch, capsys, _payload(repo, t)))
    marker = os.path.join(nelly_memory.local_state_dir(str(repo)), "stop-capture.json")
    with open(marker) as fh:
        state = json.load(fh)
    assert set(state) == {"s1"}
    assert state["s1"]["blocks"] == 1
    assert state["s1"]["paths"] == ["src/store.py"]
    assert state["s1"]["hashes"] == [hashlib.sha256(FINDING.encode()).hexdigest()]

    # Same session, same final answer: silent.
    assert _run(monkeypatch, capsys, _payload(repo, t)) == ""

    # Same session, new answer on the SAME path: silent (already asked about it).
    t2 = _transcript(tmp_path, "`load()` in src/store.py reads the cache from disk.", name="t2.jsonl")
    assert _run(monkeypatch, capsys, _payload(repo, t2)) == ""

    # New answer on a NEW unrecorded path: may ask once more.
    _commit_file(repo, "src/other.py")
    t3 = _transcript(tmp_path, "`run()` in src/other.py calls the cache.", name="t3.jsonl")
    _blocked(_run(monkeypatch, capsys, _payload(repo, t3)))


def test_at_most_two_blocks_per_session(tmp_path, repo, monkeypatch, capsys):
    for i in range(3):
        _commit_file(repo, f"src/m{i}.py")
    outs = []
    for i in range(3):
        t = _transcript(tmp_path, f"`run()` in src/m{i}.py calls the cache.", name=f"m{i}.jsonl")
        outs.append(_run(monkeypatch, capsys, _payload(repo, t)))
    assert outs[0] and outs[1] and outs[2] == ""


# 3 -------------------------------------------------------------------------------------------

@pytest.mark.parametrize("answer", [
    "`save()` in src/store.py may write the cache to disk.",
    "`save()` in src/store.py might write the cache to disk.",
    "`save()` in src/store.py could write the cache to disk.",
    "`save()` in src/store.py should write the cache to disk.",
    "`save()` in src/store.py probably writes the cache to disk.",
    "Unverified: `save()` in src/store.py writes the cache to disk.",
    "Hypothesis: `save()` in src/store.py writes the cache to disk.",
    "Does `save()` in src/store.py write the cache to disk?",
    "Which part of src/store.py writes the cache?",
    "I will check whether src/store.py writes the cache to disk.",
    "I'll confirm that src/store.py writes the cache to disk.",
    "Next: verify src/store.py writes the cache to disk.",
    "`save()` in src/missing.py writes the cache to disk.",
    "The function writes the cache to disk.",
])
def test_ambiguous_or_unknown_source_does_not_continue(tmp_path, repo, monkeypatch, capsys, answer):
    t = _transcript(tmp_path, answer)
    assert _run(monkeypatch, capsys, _payload(repo, t)) == ""
    assert _pending_files(repo) == []


# 4 -------------------------------------------------------------------------------------------

def test_indexed_symbol_is_source_linked(repo):
    records = [
        {"slug": "cache-writer", "type": "fact", "sources": [{"path": "src/store.py", "hash": "x"}],
         "symbols": ["CacheWriter", "Foo"]},
        {"slug": "ghost", "type": "fact", "sources": [{"path": "src/gone.py", "hash": "y"}],
         "symbols": ["GhostThing"]},
    ]
    found = nelly_stop_capture.find_findings("CacheWriter persists the cache to disk.", str(repo), records)
    assert len(found) == 1
    assert "CacheWriter" in found[0]["symbols"]
    assert "persists" in found[0]["line"]

    # Symbol shorter than 4 chars does not count.
    assert nelly_stop_capture.find_findings("Foo persists the cache.", str(repo), records) == []
    # Symbol whose record's source path does not exist does not count.
    assert nelly_stop_capture.find_findings("GhostThing persists the cache.", str(repo), records) == []
    # Unindexed symbol with no path does not count.
    assert nelly_stop_capture.find_findings("OtherThing persists the cache.", str(repo), records) == []


def test_find_findings_path_shape(repo):
    found = nelly_stop_capture.find_findings("Intro text.\n" + FINDING, str(repo), [])
    assert len(found) == 1
    f = found[0]
    assert set(f) >= {"line", "paths", "symbols"}
    assert f["paths"] == ["src/store.py"]
    assert "src/store.py" in f["line"]


# 5 -------------------------------------------------------------------------------------------

@pytest.mark.parametrize("record", [
    {"slug": "store", "type": "fact", "sources": [{"path": "src/store.py", "hash": "abc"}]},
    {"slug": "store", "type": "fact", "stale": False, "sources": [{"path": "src/store.py", "hash": "abc"}]},
])
def test_already_recorded_paths_do_not_continue(tmp_path, repo, monkeypatch, capsys, record):
    _write_index(repo, [record])
    t = _transcript(tmp_path, FINDING)
    assert _run(monkeypatch, capsys, _payload(repo, t)) == ""


def test_stale_record_does_not_count_as_recorded(tmp_path, repo, monkeypatch, capsys):
    _write_index(repo, [{"slug": "store", "type": "fact", "stale": True,
                         "sources": [{"path": "src/store.py", "hash": "abc"}]}])
    t = _transcript(tmp_path, FINDING)
    _blocked(_run(monkeypatch, capsys, _payload(repo, t)))


# 6 -------------------------------------------------------------------------------------------

def test_plan_mode_is_silent(tmp_path, repo, monkeypatch, capsys):
    t = _transcript(tmp_path, FINDING)
    assert _run(monkeypatch, capsys, _payload(repo, t, permission_mode="plan")) == ""


def test_capture_off_env_is_silent(tmp_path, repo, monkeypatch, capsys):
    monkeypatch.setenv("NELLY_CAPTURE", "off")
    t = _transcript(tmp_path, FINDING)
    assert _run(monkeypatch, capsys, _payload(repo, t)) == ""


@pytest.mark.parametrize("prompt", [
    "Explain the cache save path. Don't save anything to memory.",
    "Explain the cache save path, but do not record this.",
    "Explain the cache save path; please don't remember this.",
])
def test_user_no_write_prompt_is_silent(tmp_path, repo, monkeypatch, capsys, prompt):
    t = _transcript(tmp_path, FINDING, user_prompt=prompt)
    assert _run(monkeypatch, capsys, _payload(repo, t)) == ""
    assert _pending_files(repo) == []


def test_quoted_exception_does_not_revoke_user_no_write(tmp_path, repo, monkeypatch, capsys):
    answer = ('The README says "always save findings to memory".\n' + FINDING)
    t = _transcript(tmp_path, answer, user_prompt="Explain it. Do not save this to memory.")
    assert _run(monkeypatch, capsys, _payload(repo, t)) == ""
    assert _pending_files(repo) == []


# 7 -------------------------------------------------------------------------------------------

def _check_pending(repo, rel, content):
    files = _pending_files(repo)
    assert len(files) == 1, files
    path = os.path.join(nelly_memory.memory_dir(str(repo)), "pending-findings", files[0])
    with open(path) as fh:
        rec = json.load(fh)
    assert files[0] == rec["id"] + ".json"
    assert rec["reason"] == "uncommitted"
    assert rec["paths"] == [rel]
    assert rec["hashes"] == {rel: hashlib.sha256(content.encode()).hexdigest()}
    assert rec["head"] == _git(repo, "rev-parse", "HEAD")
    assert rec["branch"] == "main"
    assert 0 < len(rec["summary"]) <= 500
    assert len(rec["captured"]) == 10 and rec["captured"][4] == "-"
    body = {k: v for k, v in rec.items() if k not in ("id", "captured")}
    assert rec["id"] == hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()


def test_modified_file_queues_pending_instead_of_blocking(tmp_path, repo, monkeypatch, capsys):
    v2 = STORE_V1 + "# edited\n"
    (repo / "src" / "store.py").write_text(v2)
    t = _transcript(tmp_path, FINDING)
    assert _run(monkeypatch, capsys, _payload(repo, t)) == ""
    _check_pending(repo, "src/store.py", v2)

    # Duplicate stop (new session so the once-per-turn marker is not what suppresses it).
    assert _run(monkeypatch, capsys, _payload(repo, t, session="s2")) == ""
    assert len(_pending_files(repo)) == 1


def test_untracked_file_queues_pending_instead_of_blocking(tmp_path, repo, monkeypatch, capsys):
    content = "def load():\n    return 1\n"
    (repo / "src" / "fresh.py").write_text(content)
    t = _transcript(tmp_path, "`load()` in src/fresh.py reads the cache from disk.")
    assert _run(monkeypatch, capsys, _payload(repo, t)) == ""
    _check_pending(repo, "src/fresh.py", content)


# 8 -------------------------------------------------------------------------------------------

def test_bad_json_is_silent(monkeypatch, capsys):
    assert _run(monkeypatch, capsys, "{not json") == ""


def test_missing_transcript_is_silent(tmp_path, repo, monkeypatch, capsys):
    assert _run(monkeypatch, capsys, _payload(repo, str(tmp_path / "nope.jsonl"))) == ""


def test_non_git_cwd_is_silent(tmp_path, monkeypatch, capsys):
    d = (tmp_path / "plain").resolve()
    (d / "src").mkdir(parents=True)
    (d / "src" / "store.py").write_text(STORE_V1)
    t = _transcript(tmp_path, FINDING)
    assert _run(monkeypatch, capsys, _payload(d, t)) == ""
    assert _pending_files(d) == []


def test_oversized_message_is_skipped(tmp_path, repo, monkeypatch, capsys):
    answer = FINDING + "\n" + ("x" * 30001)
    t = _transcript(tmp_path, answer)
    assert _run(monkeypatch, capsys, _payload(repo, t)) == ""
    assert _run(monkeypatch, capsys, _payload(repo, t, session="s2", last_assistant_message=answer)) == ""


# decision 1: block reason content ----------------------------------------------------------------

def test_block_reason_names_path_quotes_line_and_constrains_pass(tmp_path, repo, monkeypatch, capsys):
    long_line = "`save()` in src/store.py writes the cache to disk " + ("and more " * 60)
    t = _transcript(tmp_path, long_line)
    reason = _blocked(_run(monkeypatch, capsys, _payload(repo, t)))["reason"]
    assert "src/store.py" in reason
    assert "`save()` in src/store.py writes the cache" in reason
    assert long_line not in reason  # quoted line is truncated (~200 chars)
    assert "nelly_evidence.py" in reason and "record" in reason
    assert "--type project" in reason and "--basis observed" in reason and f"--cwd {repo}" in reason
    low = reason.lower()
    assert "one" in low and "unchanged" in low and "do not" in low


# ---- review round: F1 F3 F5 F11 F12 F13 F14 F15 F16 ------------------------------------------------

def _events_transcript(tmp_path, events, name="e.jsonl"):
    path = tmp_path / name
    path.write_text("\n".join(json.dumps(e) for e in events) + "\n")
    return str(path)


def _user(text, **extra):
    return dict({"type": "user", "message": {"role": "user", "content": text}}, **extra)


def _assistant(text):
    return {"type": "assistant", "message": {"role": "assistant",
                                             "content": [{"type": "text", "text": text}]}}


def test_block_reason_command_is_runnable_shape(tmp_path, repo, monkeypatch, capsys):
    t = _transcript(tmp_path, FINDING)
    reason = _blocked(_run(monkeypatch, capsys, _payload(repo, t)))["reason"]
    script = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          "scripts", "nelly_evidence.py")
    assert "CLAUDE_PLUGIN_ROOT" not in reason
    assert script in reason and "CLAUDE_PLUGIN_DATA=" in reason
    assert "--type project" in reason and "--type technique" not in reason


def test_file_summary_record_does_not_count_as_recorded(tmp_path, repo, monkeypatch, capsys):
    _write_index(repo, [{"slug": "store", "type": "file-summary", "files": ["src/store.py"]}])
    t = _transcript(tmp_path, FINDING)
    _blocked(_run(monkeypatch, capsys, _payload(repo, t)))


def test_sources_must_cover_all_finding_paths(tmp_path, repo, monkeypatch, capsys):
    _commit_file(repo, "src/b.py")
    _write_index(repo, [{"slug": "s", "type": "fact", "sources": [{"path": "src/store.py", "hash": "h"}]}])
    t = _transcript(tmp_path, "`save()` in src/store.py writes through src/b.py to disk.")
    _blocked(_run(monkeypatch, capsys, _payload(repo, t)))


def test_meta_user_text_is_not_the_prompt(tmp_path, repo, monkeypatch, capsys):
    events = [_user("Explain it. Do not save this to memory."),
              _user("Base directory for this skill: /x", isMeta=True),
              _user("Stop hook feedback: record something"),
              _user("<local-command-stdout>ok</local-command-stdout>"),
              _user("Another Claude session says hi"),
              _user("[SYSTEM NOTIFICATION] go on"),
              _assistant(FINDING)]
    assert _run(monkeypatch, capsys, _payload(repo, _events_transcript(tmp_path, events))) == ""


def test_no_real_prompt_fails_closed(tmp_path, repo, monkeypatch, capsys):
    events = [_user("<system-reminder>x</system-reminder>", isMeta=True), _assistant(FINDING)]
    assert _run(monkeypatch, capsys, _payload(repo, _events_transcript(tmp_path, events))) == ""
    assert _pending_files(repo) == []


def test_prompt_found_beyond_first_tail_chunk(tmp_path, repo, monkeypatch, capsys):
    big = {"type": "user", "message": {"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": "x", "content": "z" * 400000}]}}
    events = [_user("Explain it. Do not save this to memory."), big, _assistant(FINDING)]
    assert _run(monkeypatch, capsys, _payload(repo, _events_transcript(tmp_path, events))) == ""


@pytest.mark.parametrize("answer", [
    "Updated README.md: it now reads more clearly.",
    "I fixed it: `save()` now returns None.",
    "Refactored `save()` in src/store.py, which writes the cache.",
    "```\n`save()` in src/store.py writes the cache to disk.\n```",
    "src/store.py writes the cache to disk.",
])
def test_noise_is_silent(tmp_path, repo, monkeypatch, capsys, answer):
    (repo / "README.md").write_text("hi\n")
    t = _transcript(tmp_path, answer)
    assert _run(monkeypatch, capsys, _payload(repo, t)) == ""
    assert _pending_files(repo) == []


def test_absolute_paths_inside_repo_count_outside_do_not(repo, tmp_path):
    found = nelly_stop_capture.find_findings(f"`save()` in {repo}/src/store.py writes the cache.", str(repo), [])
    assert [f["paths"] for f in found] == [["src/store.py"]]
    outside = tmp_path / "elsewhere.py"
    outside.write_text("x\n")
    assert nelly_stop_capture.find_findings(f"`save()` in {outside} writes the cache.", str(repo), []) == []


def test_clean_and_dirty_findings_split(tmp_path, repo, monkeypatch, capsys):
    _commit_file(repo, "src/a.py")
    (repo / "src" / "a.py").write_text("x = 2\n")
    answer = "`f()` in src/a.py writes the log.\n`save()` in src/store.py writes the cache."
    reason = _blocked(_run(monkeypatch, capsys, _payload(repo, _transcript(tmp_path, answer))))["reason"]
    assert "src/store.py" in reason and "src/a.py" not in reason
    assert len(_pending_files(repo)) == 1


def test_git_status_failure_drops_only_that_finding(tmp_path, repo, monkeypatch, capsys):
    _commit_file(repo, "src/bad.py")
    real = nelly_stop_capture._git

    def flaky(cwd, *args):
        if "status" in args and ("src/bad.py" in args or len([a for a in args if a.startswith("src/")]) > 1):
            return None
        return real(cwd, *args)

    monkeypatch.setattr(nelly_stop_capture, "_git", flaky)
    answer = "`f()` in src/bad.py writes the log.\n`save()` in src/store.py writes the cache."
    reason = _blocked(_run(monkeypatch, capsys, _payload(repo, _transcript(tmp_path, answer))))["reason"]
    assert "src/store.py" in reason and "src/bad.py" not in reason
    assert _pending_files(repo) == []


# round 2: F18 F20 F21 F22 -----------------------------------------------------------------------

def test_block_reason_command_parses_with_nelly_evidence(tmp_path, repo, monkeypatch, capsys):
    import re
    reason = _blocked(_run(monkeypatch, capsys, _payload(repo, _transcript(tmp_path, FINDING))))["reason"]
    cmd = re.search(r"run (CLAUDE_PLUGIN_DATA=.*?) \(or use agent-nelly\)", reason, re.S).group(1)
    toks = shlex.split(cmd)
    argv = toks[next(i for i, t in enumerate(toks) if t.endswith("nelly_evidence.py")) + 1:]
    args = nelly_evidence._parser().parse_args(argv)
    assert args.slug == "<kebab-slug>" and args.paths == ["src/store.py"] and args.body
    assert args.type == "project" and args.basis == "observed" and args.cwd == str(repo)


def test_symlinked_cwd_uses_the_lexical_store(tmp_path, repo, monkeypatch, capsys):
    link = tmp_path / "link"
    os.symlink(str(repo), str(link))
    (repo / "src" / "store.py").write_text(STORE_V1 + "# edited\n")
    t = _transcript(tmp_path, FINDING)
    assert _run(monkeypatch, capsys, _payload(link, t)) == ""
    assert len(_pending_files(link)) == 1
    (repo / "src" / "store.py").write_text(STORE_V1)
    _git(repo, "checkout", "-q", "--", "src/store.py")
    _blocked(_run(monkeypatch, capsys, _payload(link, t, session="s9")))
    marker = os.path.join(nelly_memory.local_state_dir(str(link)), "stop-capture.json")
    assert os.path.isfile(marker)


def test_slash_command_args_are_the_prompt(tmp_path, repo, monkeypatch, capsys):
    events = [_user("Explain the cache."),
              _user("<command-message>explain</command-message>\n<command-name>/explain</command-name>\n"
                    "<command-args>cache; don't save to memory</command-args>"),
              _assistant(FINDING)]
    assert _run(monkeypatch, capsys, _payload(repo, _events_transcript(tmp_path, events))) == ""


def test_slash_command_without_no_save_still_captures(tmp_path, repo, monkeypatch, capsys):
    events = [_user("Do not save this to memory."),
              _user("<command-message>explain</command-message>\n<command-name>/explain</command-name>\n"
                    "<command-args>the cache</command-args>"),
              _assistant(FINDING)]
    _blocked(_run(monkeypatch, capsys, _payload(repo, _events_transcript(tmp_path, events))))


def test_investigation_finding_is_kept_but_edit_summary_is_not(tmp_path, repo, monkeypatch, capsys):
    (repo / "src" / "api.py").write_text("def route(): pass\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "api")
    kept = nelly_stop_capture.find_findings("I confirmed `route()` in src/api.py returns the handler.",
                                            str(repo), [])
    assert len(kept) == 1
    for line in ["I implemented `save()` in src/store.py, which writes the cache.",
                 "We replaced `save()` in src/store.py so it writes the cache.",
                 "I have added `save()` in src/store.py, it writes the cache."]:
        assert nelly_stop_capture.find_findings(line, str(repo), []) == []
