"""
Test: scripts/review_plan.py turns a real git diff into the facts the Review Pipeline needs --
contract breaks, removed symbols, test gaps, fan-out groups -- and validates findings.json.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(_SCRIPTS))
import review_plan  # noqa: E402


def _git(repo, *args):
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", *args], cwd=repo,
                   check=True, capture_output=True)


def _write(repo, rel, text):
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


@pytest.fixture
def pr_repo(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _write(repo, "app/users.py", "def get_user(conn, uid):\n    return conn.get(uid)\n\n\n"
                                 "def old_helper(x):\n    return x\n")
    _write(repo, "app/pricing.py", "def price(total):\n    return total\n")
    _write(repo, "app/shipping.py", "def ship(order):\n    return order\n")
    _write(repo, "tests/test_shipping.py", "def test_ship():\n    assert True\n")
    _write(repo, "README.md", "# x\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "base")
    _git(repo, "checkout", "-q", "-b", "feature")
    _write(repo, "app/users.py", "def get_user(conn, uid, include_deleted):\n    return conn.get(uid)\n")
    _write(repo, "app/pricing.py", "def price(total):\n    return round(total, 2)\n")
    _write(repo, "app/shipping.py", "def ship(order):\n    return dict(order)\n")
    _write(repo, "tests/test_shipping.py", "def test_ship():\n    assert ship({}) == {}\n")
    _write(repo, "README.md", "# x\n\nmore docs\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "feature")
    monkeypatch.chdir(repo)
    return repo


def _plan(**kw):
    text, source = review_plan.read_diff(**kw)
    return review_plan.build_plan(text, source)


def test_reads_branch_diff_against_main(pr_repo):
    plan = _plan()
    assert plan["source"] == "main...HEAD"
    assert plan["skipped"] == ["README.md"]
    assert {f["path"] for f in plan["files"]} == {
        "app/users.py", "app/pricing.py", "app/shipping.py", "tests/test_shipping.py"}


def test_reports_changed_signature_and_removed_symbol(pr_repo):
    plan = _plan()
    assert [s["symbol"] for s in plan["changed_signatures"]] == ["get_user"]
    assert plan["changed_signatures"][0]["new"] == "def get_user(conn, uid, include_deleted):"
    assert [s["symbol"] for s in plan["removed_symbols"]] == ["old_helper"]


def test_body_only_change_counts_as_touched(pr_repo):
    pricing = next(f for f in _plan()["files"] if f["path"] == "app/pricing.py")
    assert pricing["symbols"] == ["price"]


def test_test_gaps_exclude_files_whose_tests_changed(pr_repo):
    plan = _plan()
    assert "app/pricing.py" in plan["test_gaps"]
    assert "app/users.py" in plan["test_gaps"]
    assert "app/shipping.py" not in plan["test_gaps"]
    shipping = next(f for f in plan["files"] if f["path"] == "app/shipping.py")
    assert shipping["tests_changed"] == ["tests/test_shipping.py"]


def test_diff_file_matches_git_mode(pr_repo):
    (pr_repo / "PR.diff").write_text(
        subprocess.run(["git", "diff", "main...feature"], cwd=pr_repo, capture_output=True,
                       text=True, check=True).stdout)
    from_file = _plan(diff_file="PR.diff")
    from_git = _plan()
    assert from_file["changed_signatures"] == from_git["changed_signatures"]
    assert from_file["test_gaps"] == from_git["test_gaps"]


def test_small_diff_is_one_group_large_diff_fans_out(pr_repo, monkeypatch):
    plan = _plan()
    assert plan["large"] is False and len(plan["groups"]) == 1
    monkeypatch.setattr(review_plan, "LARGE_LINES", 1)
    text, source = review_plan.read_diff()
    big = review_plan.build_plan(text, source, group_lines=3)
    assert big["large"] is True and len(big["groups"]) > 1
    grouped = [p for g in big["groups"] for p in g]
    assert sorted(grouped) == sorted(f["path"] for f in big["files"])
    assert big["groups"][0][0] == big["files"][0]["path"], "riskiest file should lead"


def test_sql_comment_removal_is_not_a_header(tmp_path):
    diff = ("diff --git a/m.sql b/m.sql\n--- a/m.sql\n+++ b/m.sql\n@@ -1,2 +1,1 @@\n"
            "--- old comment\n SELECT 1;\n")
    parsed = review_plan.parse_diff(diff)
    assert parsed["m.sql"]["removed"] == ["-- old comment"]


def test_findings_path_prefers_state_dir(pr_repo, tmp_path):
    assert review_plan.findings_path(str(tmp_path)) == str(tmp_path / "findings.json")
    assert review_plan.findings_path().endswith(os.path.join(".git", "code-review", "findings.json"))


def _finding(**over):
    f = {"id": "F1", "file": "a.py", "summary": "s", "failure_scenario": "x", "severity": "high",
         "decision": "block", "category": "correctness", "workflow_action": "block_commit",
         "confidence": "high", "evidence_tier": "tier-1"}
    f.update(over)
    return f


def test_validate_accepts_skill_example():
    skill = (_SCRIPTS.parent / "skills" / "code-reviewer" / "SKILL.md").read_text()
    section = skill[skill.index("## findings.json"):]
    example = section[section.index("```json") + 7:section.index("```", section.index("```json") + 7)]
    assert review_plan.validate(json.loads(example.replace("…", "x"))) == []


def test_validate_rejects_bad_enums_and_missing_keys():
    doc = {"scope": "s", "level": "Standard", "findings": [_finding(severity="huge")],
           "followups": [{"kind": "rewrite", "title": "t", "files": [], "why": "w"}]}
    errs = review_plan.validate(doc)
    assert any("severity" in e for e in errs)
    assert any("followups[0].kind" in e for e in errs)
    assert any("missing 'steps'" in e for e in errs)


def test_cli_validate_exit_codes(tmp_path):
    good = tmp_path / "good.json"
    good.write_text(json.dumps({"scope": "s", "level": "Quick", "findings": [_finding()], "followups": []}))
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"findings": []}))
    run = lambda p: subprocess.run([sys.executable, str(_SCRIPTS / "review_plan.py"), "validate", str(p)],
                                   capture_output=True, text=True)
    assert run(good).returncode == 0
    assert run(bad).returncode == 1
