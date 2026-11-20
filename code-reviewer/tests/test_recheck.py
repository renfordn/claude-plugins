"""
Test: scripts/recheck.py runs a per-finding re-check loop. The verifier is stubbed via
REVIEW_RECHECK_CMD (gets the brief as last argv). Stop conditions are fixed: resolved, escalate,
no new evidence, pass limit (3), blocked. Stopped findings are never cleared.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(_SCRIPTS))
import recheck  # noqa: E402
import review_plan  # noqa: E402

STUB = r'''
import json, os, sys
d = os.environ["STUB_DIR"]
n = len([p for p in os.listdir(d) if p.startswith("brief")]) + 1
open(os.path.join(d, f"brief{n}"), "w").write(sys.argv[-1])
reports = json.load(open(os.path.join(d, "reports.json")))
r = reports[min(n, len(reports)) - 1]
if r is None:
    print("no report here")
else:
    print("<!--FINDING-RECHECK-REPORT-->\n```json\n" + json.dumps(r) + "\n```")
'''


def _finding(i="F2"):
    return {"id": i, "file": "a.py", "line": 3, "summary": "s", "failure_scenario": "y",
            "severity": "high", "decision": "flag", "category": "correctness",
            "workflow_action": "pause_for_review", "confidence": "high", "evidence_tier": "tier-2"}


class _Env:
    def __init__(self, repo, state, base, sd, g):
        self.repo, self.state, self.base, self.sd, self.g = repo, state, base, sd, g
        self.findings = str(state / "findings.json")

    def reports(self, *rs):
        (self.sd / "reports.json").write_text(json.dumps(list(rs)))

    def cli(self, *args):
        return recheck.main(list(args))

    def run(self, i="F2"):
        return self.cli("run", i, "--findings", self.findings)

    def snap(self):
        return json.loads((self.state / "recheck.json").read_text())["F2"]

    def res(self, i="F2"):
        doc = json.loads((self.state / "findings.json").read_text())
        assert review_plan.validate(doc) == []
        return next(f for f in doc["findings"] if f["id"] == i).get("resolution")


@pytest.fixture
def env(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()

    def g(*a):
        return subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", *a], cwd=repo,
                              check=True, capture_output=True, text=True).stdout.strip()
    g("init", "-q")
    (repo / "a.py").write_text("x = 1\n")
    g("add", ".")
    g("commit", "-qm", "base")
    state = tmp_path / "state"
    state.mkdir()
    doc = {"scope": "s", "level": "Standard", "findings": [_finding("F1"), _finding("F2")], "followups": []}
    (state / "findings.json").write_text(json.dumps(doc))
    stub = tmp_path / "stub.py"
    stub.write_text(STUB)
    sd = tmp_path / "stubdir"
    sd.mkdir()
    monkeypatch.setenv("STUB_DIR", str(sd))
    monkeypatch.setenv("REVIEW_RECHECK_CMD", f"{sys.executable} {stub}")
    monkeypatch.chdir(repo)
    return _Env(repo, state, g("rev-parse", "HEAD"), sd, g)


def _rep(outcome, new=True, id="F2"):
    return {"id": id, "outcome": outcome, "evidence": "e", "new_evidence": new}


def test_start_snapshots_finding(env):
    assert env.cli("start", "F2", "--findings", env.findings, "--base", env.base) == 0
    s = env.snap()
    assert s["finding"]["id"] == "F2" and s["passes"] == [] and s["status"] == "open"
    assert s["base"] == env.base and s["stop_reason"] is None


def test_start_defaults_base_to_head(env):
    env.cli("start", "F2", "--findings", env.findings)
    assert env.snap()["base"] == env.base


def test_start_missing_id_errors(env):
    with pytest.raises(SystemExit):
        env.cli("start", "F9", "--findings", env.findings)


def test_resolved_is_done(env):
    env.cli("start", "F2", "--findings", env.findings)
    env.reports(_rep("resolved"))
    env.run()
    s = env.snap()
    assert s["status"] == "resolved" and len(s["passes"]) == 1
    assert s["passes"][0]["outcome"] == "resolved" and "at" in s["passes"][0]
    assert env.res() == "resolved" and env.res("F1") is None


def test_still_open_continues_then_pass_limit(env):
    env.cli("start", "F2", "--findings", env.findings)
    env.reports(_rep("still-open"), _rep("partially-resolved"), _rep("still-open"))
    env.run()
    assert env.snap()["status"] == "open"
    env.run()
    assert env.snap()["status"] == "open"
    env.run()
    s = env.snap()
    assert s["status"] == "stopped" and s["stop_reason"] == "pass limit"
    assert env.res() == "open"
    with pytest.raises(SystemExit):  # stopped findings are not re-run
        env.run()


def test_needs_detailed_review_escalates(env):
    env.cli("start", "F2", "--findings", env.findings)
    env.reports(_rep("needs-detailed-review"))
    env.run()
    s = env.snap()
    assert s["status"] == "stopped"
    assert s["stop_reason"] == "escalate (blocker, earlier phase or approval boundary)"
    assert env.res() == "open"


def test_parse_report_fenced_and_bare():
    rep = _rep("resolved")
    fenced = "<!--FINDING-RECHECK-REPORT-->\n```json\n" + json.dumps(rep) + "\n```\n"
    bare = "<!--FINDING-RECHECK-REPORT-->\n" + json.dumps(rep) + "\n"
    assert recheck.parse_report(fenced, "F2") == rep
    assert recheck.parse_report(bare, "F2") == rep
    assert recheck.parse_report("```json\n" + json.dumps(rep) + "\n```", "F2") is None  # no marker
    assert recheck.parse_report(bare, "F3") is None


def test_brief_carries_previous_evidence_lines(env):
    env.cli("start", "F2", "--findings", env.findings)
    env.reports({**_rep("still-open"), "evidence": "guard still missing"},
                {**_rep("still-open"), "evidence": "second look"})
    env.run()
    env.run()
    brief = (env.sd / "brief2").read_text()
    assert "Previous evidence: pass 1: guard still missing" in brief
    assert "Previous evidence" not in (env.sd / "brief1").read_text()


def test_no_new_evidence_stops(env):
    env.cli("start", "F2", "--findings", env.findings)
    env.reports(_rep("still-open", new=False))
    env.run()
    s = env.snap()
    assert s["status"] == "stopped" and s["stop_reason"] == "no new evidence"
    assert env.res() == "open"


@pytest.mark.parametrize("bad", [None,
                                 {"id": "F2", "outcome": "bogus", "evidence": "e", "new_evidence": True},
                                 {"id": "F7", "outcome": "resolved", "evidence": "e", "new_evidence": True}])
def test_malformed_report_blocks(env, bad):
    env.cli("start", "F2", "--findings", env.findings)
    env.reports(bad)
    env.run()
    s = env.snap()
    assert s["status"] == "stopped" and s["stop_reason"] == "blocked"
    assert env.res() != "resolved"


def test_brief_has_finding_diff_and_direct_tests_only(env):
    env.cli("start", "F2", "--findings", env.findings, "--base", env.base)
    (env.repo / "a.py").write_text("x = 2\n")
    (env.repo / "test_a.py").write_text("def test_a(): pass\n")
    env.g("add", "-A")
    env.g("commit", "-qm", "fix")
    env.reports(_rep("still-open"))
    env.cli("run", "F2", "--findings", env.findings, "--paths", "test_a.py")
    brief = (env.sd / "brief1").read_text()
    assert "Re-check: F2" in brief and "failure_scenario" in brief
    assert "+x = 2" in brief and "test_a.py" in brief
    assert "Re-check scope" in brief and '"id": "F1"' not in brief


def test_status_prints_json(env, capsys):
    env.cli("start", "F2", "--findings", env.findings)
    capsys.readouterr()
    env.cli("status", "F2", "--findings", env.findings)
    assert json.loads(capsys.readouterr().out)["status"] == "open"


def test_never_emits_review_markers(env, capsys):
    env.cli("start", "F2", "--findings", env.findings)
    env.reports(_rep("resolved"))
    env.run()
    env.cli("status", "F2", "--findings", env.findings)
    out = capsys.readouterr().out
    assert "<!--CODE-REVIEWER" not in out and "REVIEW-SCOPE" not in out


def test_atomic_write_leaves_no_temp_files(env):
    env.cli("start", "F2", "--findings", env.findings)
    assert sorted(p.name for p in env.state.iterdir()) == ["findings.json", "recheck.json", "recheck.json.lock"]


MIDPASS = r'''
import json, os, sys
sys.path.insert(0, os.environ["SCRIPTS"])
import recheck
p = os.environ["RECHECK_JSON"]
with recheck._lock(p):
    st = recheck._load(p, {})
    st["F1"]["status"] = "resolved"
    recheck._write_atomic(p, st)
print("<!--FINDING-RECHECK-REPORT-->\n```json\n" + json.dumps({"id": "F2", "outcome": "resolved", "evidence": "e", "new_evidence": True}) + "\n```")
'''


def test_concurrent_other_id_record_survives(env, tmp_path, monkeypatch):
    env.cli("start", "F1", "--findings", env.findings)
    env.cli("start", "F2", "--findings", env.findings)
    stub = tmp_path / "mid.py"
    stub.write_text(MIDPASS)
    monkeypatch.setenv("REVIEW_RECHECK_CMD", f"{sys.executable} {stub}")
    monkeypatch.setenv("SCRIPTS", str(_SCRIPTS))
    monkeypatch.setenv("RECHECK_JSON", str(env.state / "recheck.json"))
    env.run()
    st = json.loads((env.state / "recheck.json").read_text())
    assert st["F1"]["status"] == "resolved" and st["F2"]["status"] == "resolved"


def test_start_refuses_stopped_entry_and_restart_once(env):
    env.cli("start", "F2", "--findings", env.findings)
    env.reports(_rep("needs-detailed-review"), _rep("still-open"), _rep("still-open"))
    env.run()
    with pytest.raises(SystemExit):
        env.cli("start", "F2", "--findings", env.findings)
    assert env.snap()["status"] == "stopped" and len(env.snap()["passes"]) == 1
    env.cli("start", "F2", "--findings", env.findings, "--restart", "--reason", "lead approved")
    s = env.snap()
    assert s["status"] == "open" and s["stop_reason"] is None
    assert s["passes"][0]["outcome"] == "needs-detailed-review"
    assert "restart" in s["passes"][1] and s["passes"][1]["reason"] == "lead approved"
    env.run()
    env.run()  # pass 3 overall (restart marker is not a pass): pass limit counts every pass
    assert env.snap()["stop_reason"] == "pass limit"
    with pytest.raises(SystemExit):  # second restart refused
        env.cli("start", "F2", "--findings", env.findings, "--restart")


def test_start_open_entry_is_not_reset(env):
    env.cli("start", "F2", "--findings", env.findings)
    env.reports(_rep("still-open"))
    env.run()
    env.cli("start", "F2", "--findings", env.findings)
    assert len(env.snap()["passes"]) == 1


def test_scope_limited_to_finding_file_and_paths(env):
    env.cli("start", "F2", "--findings", env.findings)
    (env.repo / "unrelated.py").write_text("u = 1\n")
    env.g("add", "unrelated.py")
    env.g("commit", "-qm", "u")
    (env.repo / "unrelated.py").write_text("u = 2  # dirty\n")
    (env.repo / "a.py").write_text("x = 3\n")
    (env.repo / "test_other.py").write_text("import a\n")
    env.g("add", "test_other.py")
    env.g("commit", "-qm", "t")
    (env.repo / "test_new.py").write_text("def test_new(): assert 1\n")
    env.reports(_rep("still-open"))
    env.cli("run", "F2", "--findings", env.findings, "--paths", "test_new.py")
    brief = (env.sd / "brief1").read_text()
    assert "+x = 3" in brief
    assert "dirty" not in brief and "u = 1" not in brief
    assert "def test_new(): assert 1" in brief  # untracked file in --paths, full content
    assert "test_other.py" in brief  # tracked test referencing the finding file's stem


def test_diff_truncated_for_argv(env):
    env.cli("start", "F2", "--findings", env.findings)
    (env.repo / "a.py").write_text("y = 1\n" * 30000)
    env.reports(_rep("still-open"))
    env.run()
    brief = (env.sd / "brief1").read_text()
    assert "diff truncated" in brief and len(brief) < 70000


def _stale(env, mutate):
    env.cli("start", "F2", "--findings", env.findings)
    doc = json.loads((env.state / "findings.json").read_text())
    mutate(doc)
    (env.state / "findings.json").write_text(json.dumps(doc))
    env.reports(_rep("resolved"))
    env.run()
    s = env.snap()
    assert s["status"] == "stopped" and s["stop_reason"] == "stale finding id"
    return doc


def test_stale_id_mismatch_leaves_resolution_unwritten(env):
    def m(doc):
        doc["findings"][1]["summary"] = "a different finding now"
    doc = _stale(env, m)
    assert "resolution" not in doc["findings"][1]
    assert env.res() is None


def test_stale_id_missing_leaves_findings_untouched(env):
    def m(doc):
        doc["findings"] = doc["findings"][:1]
    _stale(env, m)
    assert [f["id"] for f in json.loads((env.state / "findings.json").read_text())["findings"]] == ["F1"]


def test_launch_failure_is_blocked_pass(env, monkeypatch):
    env.cli("start", "F2", "--findings", env.findings)
    monkeypatch.setenv("REVIEW_RECHECK_CMD", "/nonexistent/verifier-binary")
    env.run()
    s = env.snap()
    assert s["status"] == "stopped" and s["stop_reason"] == "blocked"
    assert "launch" in s["passes"][0]["evidence"]


def test_timeout_is_blocked_pass(env, monkeypatch, tmp_path):
    env.cli("start", "F2", "--findings", env.findings)
    slow = tmp_path / "slow.py"
    slow.write_text("import time; time.sleep(10)\n")
    monkeypatch.setenv("REVIEW_RECHECK_CMD", f"{sys.executable} {slow}")
    monkeypatch.setenv("REVIEW_RECHECK_TIMEOUT", "0.5")
    env.run()
    s = env.snap()
    assert s["status"] == "stopped" and s["stop_reason"] == "blocked"
    assert "timed out" in s["passes"][0]["evidence"]
