"""
Test: scripts/review_loop.py runs fresh reviewer passes until one adds nothing, briefs each
later pass with the findings so far, and merges without duplicates. The reviewer is stubbed
via REVIEW_LOOP_CMD so no claude CLI or tokens are needed.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(_SCRIPTS))
import review_loop  # noqa: E402

STUB = r'''
import json, os, sys
brief = sys.argv[-1]
n = int(open(os.environ["STUB_COUNTER"]).read() or 0) + 1 if os.path.exists(os.environ["STUB_COUNTER"]) else 1
open(os.environ["STUB_COUNTER"], "w").write(str(n))
open(os.environ["STUB_COUNTER"] + f".brief{n}", "w").write(brief)
passes = json.loads(os.environ["STUB_PASSES"])
findings = passes[min(n, len(passes)) - 1]
print("<!--CODE-REVIEWER-REPORT-->\nVerdict: clear\n```json\n" + json.dumps({"findings": findings, "level": "medium"}) + "\n```")
'''


def _f(file, line, s="x"):
    return {"file": file, "line": line, "summary": s, "failure_scenario": "y", "short_summary": s}


@pytest.fixture
def repo(tmp_path, monkeypatch):
    r = tmp_path / "repo"
    r.mkdir()
    g = lambda *a: subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", *a], cwd=r,
                                  check=True, capture_output=True)
    g("init", "-q", "-b", "main")
    (r / "a.py").write_text("def f(x):\n    return x\n")
    g("add", "-A"); g("commit", "-qm", "base"); g("checkout", "-q", "-b", "feature")
    (r / "a.py").write_text("def f(x, y):\n    return x + y\n")
    g("add", "-A"); g("commit", "-qm", "feat")
    stub = tmp_path / "stub.py"
    stub.write_text(STUB)
    monkeypatch.chdir(r)
    monkeypatch.setenv("REVIEW_LOOP_CMD", f"{sys.executable} {stub}")
    monkeypatch.setenv("STUB_COUNTER", str(tmp_path / "count"))
    return tmp_path


def _run(passes, capsys, monkeypatch, *args):
    monkeypatch.setenv("STUB_PASSES", json.dumps(passes))
    code = review_loop.main(list(args))
    return code, json.loads(capsys.readouterr().out)


def test_stops_when_a_pass_adds_nothing(repo, capsys, monkeypatch):
    code, out = _run([[_f("a.py", 1)], [_f("a.py", 2, "dup of line 1")], [_f("b.py", 9)]],
                     capsys, monkeypatch)
    assert code == 0
    assert [p["new"] for p in out["passes"]] == [1, 0]
    assert [f["file"] for f in out["findings"]] == ["a.py"]


def test_merges_new_findings_across_passes_up_to_max(repo, capsys, monkeypatch):
    passes = [[_f("a.py", 1)], [_f("a.py", 40)], [_f("b.py", 3)], [_f("c.py", 3)]]
    code, out = _run(passes, capsys, monkeypatch, "--max-passes", "3")
    assert [(f["file"], f["line"]) for f in out["findings"]] == [("a.py", 1), ("a.py", 40), ("b.py", 3)]
    assert len(out["passes"]) == 3


def test_later_passes_are_briefed_with_prior_findings(repo, capsys, monkeypatch):
    _run([[_f("a.py", 1, "first bug")], []], capsys, monkeypatch)
    first = Path(str(repo / "count") + ".brief1").read_text()
    second = Path(str(repo / "count") + ".brief2").read_text()
    assert "Changed signatures: f (a.py)" in first
    assert "Earlier independent passes" not in first
    assert "a.py:1 — first bug" in second and "Report ONLY defects not in that list" in second


def test_missing_payload_is_reported_not_crashed(repo, capsys, monkeypatch, tmp_path):
    bad = tmp_path / "bad.py"
    bad.write_text("print('no report here')")
    monkeypatch.setenv("REVIEW_LOOP_CMD", f"{sys.executable} {bad}")
    code = review_loop.main([])
    out = json.loads(capsys.readouterr().out)
    assert code == 1 and "no findings payload" in out["passes"][0]["error"]


def test_parse_report_skips_non_payload_json():
    text = ("```json\n{\"results\": []}\n```\n<!--CODE-REVIEWER-REPORT-->\n```json\n{\"note\": 1}\n```\n"
            "```json\n{\"findings\": [{\"file\": \"a\"}]}\n```")
    assert review_loop.parse_report(text) == [{"file": "a"}]
