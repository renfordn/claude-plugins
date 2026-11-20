"""Test: hooks/pre_push_offer.py offers one whole-diff review before pushing an unreviewed HEAD (R15)."""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

_HOOK = Path(__file__).resolve().parent.parent / "hooks" / "pre_push_offer.py"
sys.path.insert(0, str(_HOOK.parent))
import pre_push_offer  # noqa: E402


def _git(repo, *args):
    return subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", *args], cwd=repo,
                          check=True, capture_output=True, text=True).stdout.strip()


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "repo"
    r.mkdir()
    _git(r, "init", "-q", "-b", "main")
    (r / "a.txt").write_text("a\n")
    _git(r, "add", ".")
    _git(r, "commit", "-qm", "init")
    return r


def _env(**extra):
    env = {k: v for k, v in os.environ.items()
           if k not in ("GIT_DIR", "GIT_WORK_TREE", "CODE_REVIEWER_PREPUSH")}
    env.update(extra)
    return env


def _run(command, cwd, **env):
    payload = {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": str(cwd)}
    return subprocess.run([sys.executable, str(_HOOK)], input=json.dumps(payload),
                          capture_output=True, text=True, env=_env(**env))


def _state(repo):
    p = repo / ".git" / "code-review" / "pre-push.json"
    return json.loads(p.read_text()) if p.exists() else {}


def _denied(res):
    assert res.returncode == 0
    out = json.loads(res.stdout)["hookSpecificOutput"]
    assert out["hookEventName"] == "PreToolUse" and out["permissionDecision"] == "deny"
    return out["permissionDecisionReason"]


@pytest.mark.parametrize("cmd", [
    "git push", "git -C /x/y push", "cd x && git push origin main",
    "git push --force-with-lease", "echo hi; git push",
])
def test_detects_push(cmd):
    assert pre_push_offer.is_push(cmd)


@pytest.mark.parametrize("cmd", [
    "git pushx", 'echo "git push"', "git log --grep=push", "ls", "git status",
])
def test_not_a_push(cmd):
    assert not pre_push_offer.is_push(cmd)


def test_fast_path_non_push_no_output(repo):
    t = time.monotonic()
    res = _run("ls -la", repo)
    assert res.stdout == "" and res.returncode == 0
    assert time.monotonic() - t < 1.0  # interpreter start dominates; real work skipped
    assert _state(repo) == {}


def test_offer_once_then_allow_and_record_declined(repo):
    head = _git(repo, "rev-parse", "HEAD")
    reason = _denied(_run("git push origin main", repo))
    assert "review_plan.py" in reason and "mark-reviewed" in reason
    assert "declined" in reason and "accepted risk" in reason
    assert _state(repo)[head]["status"] == "offered"
    res = _run("git push origin main", repo)
    assert res.stdout == "" and res.returncode == 0
    assert _state(repo)[head]["status"] == "declined"
    res = _run("git push origin main", repo)  # never deny twice
    assert res.stdout == "" and _state(repo)[head]["status"] == "declined"


def test_reviewed_allows_silently(repo):
    head = _git(repo, "rev-parse", "HEAD")
    m = subprocess.run([sys.executable, str(_HOOK), "mark-reviewed", "--cwd", str(repo)],
                       capture_output=True, text=True, env=_env())
    assert m.returncode == 0
    assert _state(repo)[head]["status"] == "reviewed"
    res = _run("git push", repo)
    assert res.stdout == "" and res.returncode == 0
    assert _state(repo)[head]["status"] == "reviewed"


def test_dash_C_resolves_repo(repo, tmp_path):
    other = tmp_path / "elsewhere"
    other.mkdir()
    assert _denied(_run(f"git -C {repo} push", other))
    assert _state(repo)[_git(repo, "rev-parse", "HEAD")]["status"] == "offered"


def test_new_head_is_offered_again(repo):
    _denied(_run("git push", repo))
    (repo / "b.txt").write_text("b\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "two")
    _denied(_run("git push", repo))


def test_escape_hatch(repo):
    res = _run("git push", repo, CODE_REVIEWER_PREPUSH="off")
    assert res.stdout == "" and res.returncode == 0 and _state(repo) == {}


def test_base_prefers_upstream(repo):
    _git(repo, "branch", "up")
    _git(repo, "branch", "--set-upstream-to=up")
    (repo / "b.txt").write_text("b\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "two")
    assert "--base up" in _denied(_run("git push", repo))


@pytest.mark.parametrize("payload", ["not json", "{}", '{"tool_input": 5}'])
def test_fail_open_bad_payload(payload):
    res = subprocess.run([sys.executable, str(_HOOK)], input=payload, capture_output=True,
                         text=True, env=_env())
    assert res.stdout == "" and res.returncode == 0


def test_fail_open_not_a_repo(tmp_path):
    res = _run("git push", tmp_path)
    assert res.stdout == "" and res.returncode == 0


def test_fail_open_unwritable_state(repo):
    (repo / ".git" / "code-review").write_text("file, not dir")
    res = _run("git push", repo)
    assert res.stdout == "" and res.returncode == 0


def test_strips_git_dir_env(repo, tmp_path):
    res = _run("git push", repo, GIT_DIR=str(tmp_path / "nope" / ".git"))
    assert json.loads(res.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"


def _stop(repo, agent_type="agent-code-reviewer:code-reviewer", text="<!--CODE-REVIEWER-REPORT-->\nok",
          transcript=None, **extra):
    payload = {"hook_event_name": "SubagentStop", "agent_type": agent_type, "cwd": str(repo), **extra}
    if transcript is None:
        payload["last_assistant_message"] = text
    else:
        payload["agent_transcript_path"] = str(transcript)
    return subprocess.run([sys.executable, str(_HOOK)], input=json.dumps(payload),
                          capture_output=True, text=True, env=_env())


def test_unscoped_reviewer_stop_marks_reviewed(repo):
    head = _git(repo, "rev-parse", "HEAD")
    res = _stop(repo)
    assert res.stdout == "" and res.returncode == 0
    assert _state(repo)[head]["status"] == "reviewed"
    push = _run("git push", repo)
    assert push.stdout == "" and push.returncode == 0
    assert _state(repo)[head]["status"] == "reviewed"


def test_unscoped_reviewer_stop_reads_agent_transcript(repo, tmp_path):
    t = tmp_path / "agent.jsonl"
    _write_transcript(t, [_assistant("<!--CODE-REVIEWER-REPORT-->\nok")])
    _stop(repo, transcript=t)
    assert _state(repo)[_git(repo, "rev-parse", "HEAD")]["status"] == "reviewed"


def _assistant(text):
    return {"type": "assistant", "message": {"role": "assistant",
                                             "content": [{"type": "text", "text": text}]}}


def _write_transcript(path, events):
    path.write_text("\n".join(json.dumps(e) for e in events) + "\n")


def test_transcript_marker_only_in_tool_result_does_not_mark(repo, tmp_path):
    t = tmp_path / "agent.jsonl"
    _write_transcript(t, [
        {"type": "user", "message": {"role": "user", "content": [
            {"type": "tool_result", "content": "<!--CODE-REVIEWER-REPORT-->"}]}},
        _assistant("all done, no report"),
    ])
    _stop(repo, transcript=t)
    assert _state(repo) == {}


def test_transcript_marker_in_earlier_assistant_message_does_not_mark(repo, tmp_path):
    t = tmp_path / "agent.jsonl"
    _write_transcript(t, [_assistant("<!--CODE-REVIEWER-REPORT-->"), _assistant("later text")])
    _stop(repo, transcript=t)
    assert _state(repo) == {}


def test_agent_type_must_match_exactly(repo):
    _stop(repo, agent_type="xcode-reviewer")
    assert _state(repo) == {}
    _stop(repo, agent_type="code-reviewer")
    assert _state(repo)[_git(repo, "rev-parse", "HEAD")]["status"] == "reviewed"


@pytest.mark.parametrize("cmd", ["git status\ngit push", "cd x\ngit push origin main", "ls;\ngit push"])
def test_newline_separates_commands(cmd):
    assert pre_push_offer.is_push(cmd)


def test_newline_does_not_join_words():
    assert not pre_push_offer.is_push("echo hi\npush")


def test_deny_text_mark_reviewed_has_cwd_and_quoted_script(repo):
    import shlex
    reason = _denied(_run("git push", repo))
    assert f"mark-reviewed --cwd {shlex.quote(str(repo.resolve()))}" in reason
    assert shlex.quote(str(_HOOK)) in reason or str(_HOOK) in reason


@pytest.mark.parametrize("cmd", ["git push --dry-run", "git push -n origin main", "git push --help"])
def test_dry_run_and_help_skip_offer(repo, cmd):
    res = _run(cmd, repo)
    assert res.stdout == "" and res.returncode == 0 and _state(repo) == {}
    _denied(_run("git push", repo))  # offer not consumed


def test_nothing_to_push_allows_silently(repo):
    _git(repo, "branch", "up")
    _git(repo, "branch", "--set-upstream-to=up")
    res = _run("git push", repo)
    assert res.stdout == "" and _state(repo) == {}


@pytest.mark.parametrize("cmd", ["git push origin --delete old", "git push origin :old",
                                 "git push --tags", "git push origin --tags"])
def test_delete_and_tags_only_allow_silently(repo, cmd):
    res = _run(cmd, repo)
    assert res.stdout == "" and _state(repo) == {}


def test_base_falls_back_to_main_then_omits(repo):
    assert "--base main" in _denied(_run("git push", repo))
    _git(repo, "branch", "-m", "feature")
    _git(repo, "update-ref", "-d", "refs/heads/main")
    (repo / "b.txt").write_text("b\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "two")
    assert "--base" not in _denied(_run("git push", repo))


def test_concurrent_records_all_kept(repo):
    import threading
    path = pre_push_offer._state_path(str(repo))
    heads = [f"{i:040x}" for i in range(16)]
    ts = [threading.Thread(target=pre_push_offer._record, args=(path, h, "reviewed")) for h in heads]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert set(_state(repo)) == set(heads)


@pytest.mark.parametrize("kwargs", [
    {"text": "<!--CODE-REVIEWER-REPORT-->\n<!--REVIEW-SCOPE: slice 3-->\nok"},
    {"agent_type": "agent-code-reviewer:finding-verifier"},
    {"text": "no report marker"},
    {"agent_type": "something-else"},
])
def test_other_stops_do_not_mark(repo, kwargs):
    res = _stop(repo, **kwargs)
    assert res.stdout == "" and res.returncode == 0
    assert _state(repo) == {}


def test_parent_transcript_path_ignored(repo, tmp_path):
    t = tmp_path / "parent.jsonl"
    t.write_text("<!--CODE-REVIEWER-REPORT-->")
    res = subprocess.run([sys.executable, str(_HOOK)], capture_output=True, text=True, env=_env(),
                         input=json.dumps({"hook_event_name": "SubagentStop", "cwd": str(repo),
                                           "agent_type": "code-reviewer", "transcript_path": str(t)}))
    assert res.stdout == "" and _state(repo) == {}


def test_subagent_stop_fails_open_not_a_repo(tmp_path):
    res = _stop(tmp_path)
    assert res.stdout == "" and res.returncode == 0


def _write_findings(repo, findings):
    d = repo / ".git" / "code-review"
    d.mkdir(parents=True, exist_ok=True)
    (d / "findings.json").write_text(json.dumps(
        {"scope": "x", "level": "Standard", "findings": findings, "followups": []}))


def test_offer_lists_open_blocking_findings(repo):
    _write_findings(repo, [
        {"id": "F1", "file": "a.py", "line": 3, "summary": "drops the lock",
         "workflow_action": "block_commit", "decision": "block", "resolution": "open"},
        {"id": "F2", "file": "b.py", "summary": "already fixed",
         "workflow_action": "block_commit", "decision": "block", "resolution": "resolved"},
        {"id": "F3", "file": "c.py", "summary": "style nit",
         "workflow_action": "log_only", "decision": "flag"},
        {"id": "F4", "file": "d.py", "summary": "no resolution field yet",
         "workflow_action": "pause_for_review", "decision": "block"},
    ])
    reason = _denied(_run("git push origin main", repo))
    assert "F1" in reason and "a.py:3" in reason and "drops the lock" in reason
    assert "F4" in reason
    assert "F2" not in reason and "F3" not in reason


def test_offer_without_findings_file_has_no_blocker_list(repo):
    reason = _denied(_run("git push origin main", repo))
    assert "Unresolved blocking findings" not in reason


def test_no_upstream_but_head_already_on_a_remote_skips_offer(repo, tmp_path):
    bare = tmp_path / "remote.git"
    _git(tmp_path, "init", "-q", "--bare", str(bare))
    _git(repo, "remote", "add", "origin", str(bare))
    _git(repo, "push", "-q", "origin", "main")  # remote-tracking ref exists, no upstream set
    res = _run("git push origin main", repo)
    assert res.stdout == "" and _state(repo) == {}


def _on_upstream(repo, tmp_path):
    bare = tmp_path / "up.git"
    _git(tmp_path, "init", "-q", "--bare", str(bare))
    _git(repo, "remote", "add", "origin", str(bare))
    _git(repo, "push", "-q", "-u", "origin", "main")


@pytest.mark.parametrize("cmd", [
    "git commit -qm b && git push",
    "git add . && git commit -m b; git push origin main",
    "git merge feature && git push",
])
def test_commit_chained_before_push_is_offered_even_when_head_is_on_upstream(repo, tmp_path, cmd):
    _on_upstream(repo, tmp_path)
    reason = _denied(_run(cmd, repo))
    assert "separate" in reason
    res = _run(cmd, repo)  # never deny twice: the re-run goes through, recorded declined
    assert res.stdout == ""
    assert "declined" in json.dumps(_state(repo))


def test_commit_chained_before_push_ignores_reviewed_pre_commit_head(repo, tmp_path):
    _on_upstream(repo, tmp_path)
    _git(repo, "commit", "-q", "--allow-empty", "-m", "local")
    subprocess.run([sys.executable, str(_HOOK), "mark-reviewed", "--cwd", str(repo)],
                   capture_output=True, text=True, env=_env(), check=True)
    _denied(_run("git commit -qm b && git push", repo))


def test_auto_mark_skipped_when_report_has_open_blockers(repo):
    head = _git(repo, "rev-parse", "HEAD")
    text = ('<!--CODE-REVIEWER-REPORT-->\n```json\n{"findings": [{"id": "F1", '
            '"workflow_action": "block_commit", "decision": "block"}]}\n```')
    _stop(repo, text=text)
    assert head not in _state(repo)


def test_auto_mark_uses_review_cwd_line_not_stop_cwd(repo, tmp_path):
    other = tmp_path / "wt"
    other.mkdir()
    _git(other, "init", "-q", "-b", "main")
    (other / "x").write_text("x")
    _git(other, "add", ".")
    _git(other, "commit", "-qm", "x")
    other_head = _git(other, "rev-parse", "HEAD")
    _stop(repo, text=f"<!--CODE-REVIEWER-REPORT-->\nok\nReview cwd: {other}")
    assert _state(repo) == {}
    state = json.loads((other / ".git" / "code-review" / "pre-push.json").read_text())
    assert state[other_head]["status"] == "reviewed"


def test_offer_tells_model_to_ask_user_before_skipping(repo):
    reason = _denied(_run("git push origin main", repo))
    assert "Ask the user" in reason


def _transcript(path, prompt, report):
    with open(path, "w") as fh:
        fh.write(json.dumps({"type": "user", "message": {"role": "user", "content": prompt}}) + "\n")
        fh.write(json.dumps({"type": "assistant", "message": {
            "role": "assistant", "content": [{"type": "text", "text": report}]}}) + "\n")
    return str(path)


def test_prompt_scoped_review_without_echoed_marker_is_not_unscoped(tmp_path):
    report = "<!--CODE-REVIEWER-REPORT-->\nverdict: clear"
    scoped = _transcript(tmp_path / "s.jsonl", "Gate.\nReview scope: slice=3\nFocus: gate.py", report)
    payload = {"agent_type": "code-reviewer:code-reviewer", "agent_transcript_path": scoped}
    assert pre_push_offer._unscoped_review_text(payload) is None
    payload["last_assistant_message"] = report          # report inline, prompt still in the transcript
    assert pre_push_offer._unscoped_review_text(payload) is None
    plain = _transcript(tmp_path / "p.jsonl", "Pre-push review of the outgoing diff.", report)
    assert pre_push_offer._unscoped_review_text(
        {"agent_type": "code-reviewer:code-reviewer", "agent_transcript_path": plain}) == report
