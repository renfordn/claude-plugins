"""R3 coherence fixes (slice 4H): F1 guard carries ids, F2 done command, F3 coverage-then-green,
F4 mutant tail in note, F5 blocked slices surfaced."""
import json
import os
import re
import shlex
import subprocess
import sys

import pytest

PLUGIN = os.path.realpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.join(PLUGIN, "scripts"))
sys.path.insert(0, os.path.join(PLUGIN, "hooks"))
import tdd_check  # noqa: E402
import tdd_state  # noqa: E402

GUARD = os.path.join(PLUGIN, "hooks", "red_first_guard.py")
CHECK = os.path.join(PLUGIN, "scripts", "tdd_check.py")
SUBSTOP = os.path.join(PLUGIN, "hooks", "tdd_subagent_stop.py")
START_HOOK = os.path.join(PLUGIN, "hooks", "tdd_session_start.py")
STOP_HOOK = os.path.join(PLUGIN, "hooks", "tdd_stop.py")
FAIL = [sys.executable, "-c", "raise SystemExit(1)"]
PASS = [sys.executable, "-c", "pass"]
MUT = shlex.join([sys.executable, "-c", "raise SystemExit(1)"])


def _env():
    return {k: v for k, v in os.environ.items() if k not in ("GIT_DIR", "GIT_WORK_TREE")}


@pytest.fixture
def repo(tmp_path):
    root = os.path.realpath(tmp_path / "repo")
    os.makedirs(root)
    for a in (["init", "-q"], ["commit", "-q", "--allow-empty", "-m", "i"]):
        subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *a], cwd=root, check=True,
                       capture_output=True, env=_env())
    return root


def check(cwd, *args):
    return subprocess.run([sys.executable, CHECK, *args], cwd=cwd, capture_output=True, text=True, env=_env())


def guard(repo):
    p = {"tool_name": "Edit", "tool_input": {"file_path": os.path.join(repo, "src", "app.py")}, "cwd": repo}
    r = subprocess.run([sys.executable, GUARD], input=json.dumps(p), capture_output=True, text=True,
                       cwd=repo, env=_env())
    return json.loads(r.stdout)["hookSpecificOutput"]["permissionDecisionReason"]


def test_cli_id_args():
    assert tdd_check.cli_id_args({"slice_id": "2", "base": "abc"}) == ["--slice-id", "2", "--base", "abc"]
    assert tdd_check.cli_id_args({"slice_id": "2"}) == ["--slice-id", "2"]
    assert tdd_check.cli_id_args({}) == []


def test_f1_f2_guard_commands_carry_ids_and_done(repo):
    title = "Slice 2: ids"
    assert check(repo, "start", "--slice", title, "--slice-id", "2", "--base", "abc").returncode == 0
    reason = guard(repo)
    assert "red --slice %s --slice-id 2 --base abc" % shlex.quote(title) in reason
    assert "bypass --slice %s --slice-id 2 --base abc" % shlex.quote(title) in reason
    done = re.search(r"`<P> (done --slice '[^']*' --slice-id 2 --base abc)`", reason)
    assert done and "no slice should be open here" in reason
    prefix = re.search(r"<P> = `(cd \S+ && python3 \S+)`", reason).group(1)
    assert reason.count(prefix) == 1
    assert check(repo, "red", "--slice", title, "--slice-id", "2", "--base", "abc", "--", *FAIL).returncode == 0
    g = check(repo, "green", "--slice", title, "--slice-id", "2", "--base", "abc", "--", *PASS)
    assert g.returncode == 0 and "CONFIRMED" in g.stdout
    assert subprocess.run(prefix + " " + done.group(1), shell=True, capture_output=True, text=True,
                          env=_env()).returncode == 0
    assert tdd_check.open_slice(tdd_check.read_log(repo), os.path.realpath(repo)) is None


def test_f2_done_without_ids(repo):
    title = "Slice Z: plain"
    check(repo, "start", "--slice", title)
    reason = guard(repo)
    assert "done --slice %s" % shlex.quote(title) in reason
    assert "--slice-id" not in reason


def test_f3_refactor_coverage_then_green(repo):
    t = "Slice R: refactor"
    check(repo, "start", "--slice", t, "--kind", "refactor")
    c = check(repo, "coverage", "--slice", t, "--mutant", MUT, "--", *PASS)
    assert c.returncode == 0, c.stdout
    g = check(repo, "green", "--slice", t, "--", *PASS)
    assert g.returncode == 0 and "NOT CONFIRMED" not in g.stdout


def test_f3_green_without_red_or_coverage_still_fails(repo):
    t = "Slice R: none"
    check(repo, "start", "--slice", t, "--kind", "refactor")
    assert check(repo, "green", "--slice", t, "--", *PASS).returncode == 1
    check(repo, "coverage", "--slice", t, "--mutant", "true", "--", *PASS)  # survived: unconfirmed
    assert check(repo, "green", "--slice", t, "--", *PASS).returncode == 1


@pytest.mark.parametrize("kind", ["feature", "fix", "validation", "ui"])
def test_f3_non_refactor_kind_coverage_does_not_prove_green(repo, kind):
    t = "Slice F: feat"
    check(repo, "start", "--slice", t, "--kind", kind)
    assert check(repo, "coverage", "--slice", t, "--mutant", MUT, "--", *PASS).returncode == 0
    g = check(repo, "green", "--slice", t, "--", *PASS)
    assert g.returncode == 1 and "NOT CONFIRMED" in g.stdout


def test_f3_contract_kind_coverage_then_green(repo):
    t = "Slice C: contract"
    check(repo, "start", "--slice", t, "--kind", "contract")
    check(repo, "coverage", "--slice", t, "--mutant", MUT, "--", *PASS)
    assert check(repo, "green", "--slice", t, "--", *PASS).returncode == 0


def test_f3_legacy_coverage_does_not_count_without_start(repo):
    t = "Slice L: legacy"
    assert check(repo, "coverage", "--slice", t, "--mutant", MUT, "--", *PASS).returncode == 0
    assert check(repo, "green", "--slice", t, "--", *PASS).returncode == 1


def _stop(repo, t, kind, outcome):
    check(repo, "start", "--slice", t, "--kind", kind)
    cov = check(repo, "coverage", "--slice", t, "--mutant", MUT, "--", *PASS).stdout
    grn = check(repo, "green", "--slice", t, "--", *PASS).stdout
    lines = [ln for ln in (cov + grn).splitlines() if ln.startswith("TDD-EVIDENCE")]
    msg = ("<!--AGENT-TDD-REPORT-->\n<!--AGENT-TDD-PHASE:green_pause-->\n"
           + ("<!--AGENT-TDD-OUTCOME: refactor-->\n" if outcome else "")
           + "**Plan**\nrefactor it\n\n**Validation Evidence**\n" + "\n".join(lines) + "\n")
    r = subprocess.run([sys.executable, SUBSTOP], input=json.dumps({"cwd": repo, "last_assistant_message": msg}),
                       capture_output=True, text=True, env=_env())
    return json.loads(r.stdout)["systemMessage"]


def test_f3_stop_hook_no_warning_for_refactor_outcome(repo):
    assert "was not verified" not in _stop(repo, "Slice R: refactor", "refactor", True)


def test_f3_stop_hook_warns_for_coverage_green_without_refactor_outcome(repo):
    assert "was not verified" in _stop(repo, "Slice R: refactor", "refactor", False)


def test_f4_mutant_tail_in_note(repo):
    survive = shlex.join([sys.executable, "-c", "print('TAILMARK')"])
    ok, _, _ = tdd_check.run_coverage("Slice M: m", survive, PASS, cwd=repo)
    assert ok is False
    n = tdd_check.read_log(repo)[-1]["note"]
    assert "TAILMARK" in n
    norun = shlex.join([sys.executable, "-c", "print('NR-" + "y" * 700 + "-END'); raise SystemExit(127)"])
    tdd_check.run_coverage("Slice M: m", norun, PASS, cwd=repo)
    n = tdd_check.read_log(repo)[-1]["note"]
    assert n.startswith("mutant did not run") and n.rstrip().endswith("-END") and len(n) < 600


def _hook(path, cwd):
    return subprocess.run([sys.executable, path], input=json.dumps({"cwd": cwd}), capture_output=True,
                          text=True, env=_env())


@pytest.mark.parametrize("reason_key,expected", [("blocked_reason", "no harness"), (None, "desc text")])
def test_f5_blocked_listed(tmp_path, reason_key, expected):
    cwd = str(tmp_path)
    s = {"id": 7, "description": "desc text", "status": "blocked"}
    if reason_key:
        s[reason_key] = "no harness"
    tdd_state.write_tdd_progress(cwd, {"slices": [s]})
    for hook in (START_HOOK, STOP_HOOK):
        out = json.loads(_hook(hook, cwd).stdout)
        text = out.get("systemMessage") or out["hookSpecificOutput"]["additionalContext"]
        assert "waiting on the user: " + expected in text and "[7]" in text


def test_f5_subagent_stop_stores_blocked_reason(repo):
    msg = '<!--AGENT-TDD-REPORT-->\n<!--AGENT-TDD-BLOCKED: reason="need creds"-->\n**Plan**\nthing\n'
    subprocess.run([sys.executable, SUBSTOP], input=json.dumps({"cwd": repo, "last_assistant_message": msg}),
                   capture_output=True, text=True, env=_env())
    data = tdd_state.read_tdd_progress(repo)
    assert data["slices"][0]["blocked_reason"] == "need creds"


def test_f1_coverage_unlocks_only_refactor_contract(repo):
    wt = os.path.realpath(repo)
    for kind, expect in (("feature", False), ("fix", False), ("ui", False), ("refactor", True),
                         ("contract", True)):
        t = "Slice K: %s" % kind
        check(repo, "start", "--slice", t, "--kind", kind)
        check(repo, "coverage", "--slice", t, "--mutant", MUT, "--", *PASS)
        log = tdd_check.read_log(repo)
        assert tdd_check.unlocked(log, wt) is expect, kind
        if not expect:
            p = {"tool_name": "Edit", "tool_input": {"file_path": os.path.join(repo, "src", "a.py")}, "cwd": repo}
            r = subprocess.run([sys.executable, GUARD], input=json.dumps(p), capture_output=True, text=True,
                               cwd=repo, env=_env())
            assert "deny" in r.stdout
        check(repo, "bypass", "--slice", t, "--reason", "x")
        assert tdd_check.unlocked(tdd_check.read_log(repo), wt) is True
        check(repo, "done", "--slice", t)


def test_counts_as_red_helper():
    c = tdd_check._counts_as_red
    red, cov, byp = ({"phase": p, "confirmed": True} for p in ("red", "coverage", "bypass"))
    assert c(red, {"kind": "feature"}) and not c(cov, {"kind": "feature"}) and not c(cov, None)
    assert c(cov, {"kind": "refactor"}) and c(cov, {"kind": "contract"})
    assert not c(byp, {"kind": "refactor"}) and c(byp, {"kind": "feature"}, unlock=True)
    assert not c({"phase": "red", "confirmed": False}, {"kind": "feature"})


def test_guard_deny_text_compact_and_refactor_names_coverage(repo):
    check(repo, "start", "--slice", "Slice 2: ids", "--slice-id", "2", "--base", "abc")
    assert len(guard(repo)) < 700
    check(repo, "start", "--slice", "Slice 3: rf", "--kind", "refactor")
    r = guard(repo)
    assert "coverage --slice" in r and "--mutant" in r and " red --slice" not in r and len(r) < 700


def test_f1_stop_coverage_only_with_green_is_unproven(repo):
    t = "Slice U: cov"
    check(repo, "start", "--slice", t, "--kind", "refactor")
    cov = check(repo, "coverage", "--slice", t, "--mutant", MUT, "--", *PASS).stdout
    grn = check(repo, "green", "--slice", t, "--", *PASS).stdout
    for evid, warn in ((cov, False), (cov + grn, True)):
        lines = [ln for ln in evid.splitlines() if ln.startswith("TDD-EVIDENCE")]
        msg = ("<!--AGENT-TDD-REPORT-->\n<!--AGENT-TDD-PHASE:green_pause-->\n<!--AGENT-TDD-OUTCOME: coverage-only-->\n"
               "**Plan**\nx\n\n" + "\n".join(lines) + "\n")
        r = subprocess.run([sys.executable, SUBSTOP], input=json.dumps({"cwd": repo, "last_assistant_message": msg}),
                           capture_output=True, text=True, env=_env())
        assert ("was not verified" in json.loads(r.stdout)["systemMessage"]) is warn


def test_f2_stop_message_shows_outcome_and_kind(repo):
    t = "Slice V: v"
    msg = _stop(repo, t, "refactor", True)
    assert "outcome=refactor" in msg and "kind=refactor" in msg and "multiple starts" not in msg
    msg = _stop(repo, t, "contract", False)  # second start for the same title
    assert "outcome=none" in msg and "kind=contract" in msg and "(multiple starts)" in msg


def test_f2_start_token_in_report_wins(repo):
    t = "Slice W: w"
    st = check(repo, "start", "--slice", t, "--kind", "fix").stdout.strip()
    check(repo, "start", "--slice", t, "--kind", "feature")
    msg = ("<!--AGENT-TDD-REPORT-->\n<!--AGENT-TDD-PHASE:green_pause-->\n**Plan**\nx\n\n" + st + "\n")
    r = subprocess.run([sys.executable, SUBSTOP], input=json.dumps({"cwd": repo, "last_assistant_message": msg}),
                       capture_output=True, text=True, env=_env())
    assert "kind=fix" in json.loads(r.stdout)["systemMessage"]


NOW = __import__("datetime").datetime(2026, 11, 19, 12, 0, 0)


def _blocked(i, hours):
    return {"id": i, "description": "d%d" % i, "status": "blocked", "blocked_reason": "r%d" % i,
            "timestamp": (NOW - __import__("datetime").timedelta(hours=hours)).isoformat()}


def test_f3_summarize_age_filter_and_cap():
    data = {"slices": [_blocked(1, 100), _blocked(2, 1), _blocked(3, 2)]}
    pending, blocked = tdd_state.summarize_open_slices(data, now=NOW)
    assert pending == [] and len(blocked) == 3  # 2 rows + "(+1 older)"
    assert "waiting on the user: r2" in blocked[0] and "(+1 older)" in blocked[-1]
    many = {"slices": [_blocked(i, 1 + i) for i in range(1, 9)]}
    _, blocked = tdd_state.summarize_open_slices(many, now=NOW)
    assert len(blocked) == 6 and "(+3 older)" in blocked[-1]
    pending, _ = tdd_state.summarize_open_slices(
        {"slices": [{"id": 4, "description": "p", "status": "green_pending_review"}]}, now=NOW)
    assert pending == ["  - [4] p"]


def test_f3_old_blocked_only_is_silent_beyond_count(tmp_path):
    cwd = str(tmp_path)
    s = _blocked(1, 100)
    s["timestamp"] = "2020-01-01T00:00:00"
    tdd_state.write_tdd_progress(cwd, {"slices": [s]})
    for hook in (START_HOOK, STOP_HOOK):
        out = json.loads(_hook(hook, cwd).stdout)
        text = out.get("systemMessage") or out["hookSpecificOutput"]["additionalContext"]
        assert "(+1 older)" in text and "waiting on the user" not in text


def test_f3_rereport_clears_blocked_row(repo):
    blocked = '<!--AGENT-TDD-REPORT-->\n<!--AGENT-TDD-BLOCKED: reason="need creds"-->\n**Plan**\nthing\n'
    ok = '<!--AGENT-TDD-REPORT-->\n<!--AGENT-TDD-PHASE:green_pause-->\n**Plan**\nthing\n'
    for m in (blocked, ok):
        subprocess.run([sys.executable, SUBSTOP], input=json.dumps({"cwd": repo, "last_assistant_message": m}),
                       capture_output=True, text=True, env=_env())
    sl = tdd_state.read_tdd_progress(repo)["slices"]
    assert len(sl) == 1 and sl[0]["status"] == "green_pending_review" and "blocked_reason" not in sl[0]
