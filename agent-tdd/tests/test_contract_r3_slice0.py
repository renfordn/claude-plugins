"""Release 3 slice 0: shared contract for R7/R8/R9/R11 (markers, evidence phases, guard registration)."""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "hooks"))
import markers  # noqa: E402


def test_outcome_and_blocked_markers_parse():
    assert markers.parse_outcome("x <!--AGENT-TDD-OUTCOME: coverage-only--> y") == "coverage-only"
    assert markers.parse_outcome("no marker") is None
    assert markers.parse_blocked('<!--AGENT-TDD-BLOCKED: reason="no e2e harness"-->') == "no e2e harness"
    assert markers.parse_blocked("nothing") is None


def test_evidence_phases_are_declared():
    for p in ("red", "green", "integration", "start", "coverage", "bypass", "done"):
        assert p in markers.EVIDENCE_PHASES


def test_red_first_guard_registered_with_timeout():
    hooks = json.loads((ROOT / "hooks" / "hooks.json").read_text())["hooks"]["PreToolUse"]
    entry = next(e for e in hooks if "Write" in e.get("matcher", ""))
    assert entry["matcher"] == "Write|Edit|MultiEdit|NotebookEdit"
    h = entry["hooks"][0]
    assert h["command"].endswith('/hooks/red_first_guard.py"') and h["timeout"] == 5


def test_red_first_guard_stub_fails_open():
    out = subprocess.run([sys.executable, str(ROOT / "hooks" / "red_first_guard.py")],
                         input="not json", capture_output=True, text=True, timeout=10)
    assert out.returncode == 0 and out.stdout.strip() == ""


def test_contract_docs_exist():
    ev = (ROOT / "references" / "evidence-log.md").read_text()
    for p in ("start", "coverage", "bypass", "done", "worktree", "slice_id"):
        assert p in ev
    sd = (ROOT / "references" / "slice-discipline.md").read_text()
    assert "Read by" in sd


def test_evidence_line_regex_covers_all_phases():
    m = markers.EVIDENCE_LINE_RE.search("TDD-EVIDENCE red 0123abcd exit=1 CONFIRMED")
    assert m.group("phase") == "red" and m.group("token") == "0123abcd" and m.group("exit") == "1"
    assert m.group("status") == "CONFIRMED"
    m = markers.EVIDENCE_LINE_RE.search("TDD-EVIDENCE bypass 89abcdef CONFIRMED")
    assert m.group("phase") == "bypass" and m.group("exit") is None
    m = markers.EVIDENCE_LINE_RE.search("TDD-EVIDENCE coverage 89abcdef exit=0 NOT CONFIRMED (mutant passed)")
    assert m.group("status") == "NOT CONFIRMED"
    assert markers.format_evidence_line("start", "0123abcd", None, True) == "TDD-EVIDENCE start 0123abcd CONFIRMED"
    assert markers.format_evidence_line("red", "0123abcd", 1, False, "x") == \
        "TDD-EVIDENCE red 0123abcd exit=1 NOT CONFIRMED (x)"


def test_marker_variants():
    assert markers.parse_outcome("<!--AGENT-TDD-OUTCOME: Coverage-Only-->") == "coverage-only"
    assert markers.parse_blocked("<!--AGENT-TDD-BLOCKED: reason='no harness'-->") == "no harness"
    assert markers.parse_blocked("<!--AGENT-TDD-BLOCKED-->") == ""
    assert markers.parse_blocked('<!--AGENT-TDD-BLOCKED: reason=""-->') == ""


def test_evidence_log_contract_is_specific():
    ev = (ROOT / "references" / "evidence-log.md").read_text()
    for needle in ("append order", "naive local", "--mutant", "TDD-EVIDENCE <phase> <token>",
                   "no open `start`", "gaps", "confirmed: true", "no `worktree`"):
        assert needle in ev, needle
    after = (ROOT / "CHANGELOG.md").read_text().split("## [Unreleased]", 1)[1].split("\n## [")
    assert any("### Added" in s for s in after[:2])  # [Unreleased] until CUPS dates it
