"""Release 3 slice 2F: slice-discipline procedures are documented and linked."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _t(rel):
    return (ROOT / rel).read_text()


def test_slice_discipline_procedures():
    sd = _t("references/slice-discipline.md")
    for needle in ("Read by", "TEST-STRATEGY-REPORT", "tdd_check.py", "start", "--risks", "--inspected",
                   "--run", "unverified", "coverage --mutant", "mktemp -d", "AGENT-TDD-OUTCOME: coverage-only",
                   "bypass", "done", "e2e_harness.py", "harness", "AGENT-TDD-BLOCKED", "no e2e harness",
                   "green_pause", "evidence-log.md", "test-strategist"):
        assert needle in sd, needle


def test_agent_tdd_points_to_discipline_and_drops_contrived_red():
    t = _t("agents/agent-TDD.md")
    assert "references/slice-discipline.md" in t
    assert "fix the test, don't\nproceed" not in t
    assert "AGENT-TDD-BLOCKED" in t and len(t.splitlines()) < 300


def test_schemas_accept_ui_and_blocked():
    props = json.loads(_t("references/tasks-schema.json"))["properties"]["tasks"]["items"]["properties"]
    assert props["ui"]["type"] == "boolean" and props["blocked"]["type"] == "string"
    assert json.loads(_t("references/slice-spec.schema.json"))["properties"]["ui"]["type"] == "boolean"
    assert "**UI:**" in _t("references/tasks-format.md") and "**Blocked:**" in _t("references/tasks-format.md")
    assert "ui" in _t("skills/slice-spec/SKILL.md").lower()


def test_other_docs_point_to_discipline():
    for rel in ("INTEROP.md", "references/escalation-paths.md", "references/parallel-delivery.md",
                "agents/test-strategist.md", "skills/test-budget/SKILL.md"):
        assert "slice-discipline.md" in _t(rel) or "evidence-log.md" in _t(rel), rel
    assert "BLOCKED" in _t("references/escalation-paths.md") and "coverage-only" in _t("references/escalation-paths.md")
    assert "BLOCKED" in _t("references/parallel-delivery.md")
    assert "evidence-log.md" in _t("INTEROP.md")


def _marker_examples(tag):
    import re
    out = []
    for rel in ("INTEROP.md", "references/slice-discipline.md", "agents/agent-TDD.md",
                "references/escalation-paths.md"):
        out += re.findall(r"<!--\s*AGENT-TDD-%s.*?-->" % tag, _t(rel))
    return out


def test_marker_examples_parse():
    import sys
    sys.path.insert(0, str(ROOT / "hooks"))
    import markers
    blocked, outcome = _marker_examples("BLOCKED"), _marker_examples("OUTCOME")
    assert blocked and outcome
    for b in blocked:
        assert markers.parse_blocked(b) is not None, b
    assert any(markers.parse_blocked(b) for b in blocked)
    for o in outcome:
        assert markers.parse_outcome(o) in ("coverage-only", "refactor"), o


def test_tdd_check_commands_in_slice_discipline_parse():
    import re
    import shlex
    import sys
    sys.path.insert(0, str(ROOT / "scripts"))
    import tdd_check
    text = _t("references/slice-discipline.md")
    cmds = re.findall(r"^tdd_check\.py ((?:red|green|start|coverage|bypass|done) .*)$", text, re.M)
    cmds += re.findall(r"`tdd_check\.py ((?:red|green|start|coverage|bypass|done) [^`]*)`", text)
    assert len(cmds) >= 4
    for c in cmds:
        _parse_only(tdd_check, shlex.split(c))


class _Parsed(Exception):
    pass


def _parse_only(tdd_check, argv):
    """Run tdd_check.main's real argparse on argv, stopping right after parsing."""
    import argparse
    orig = argparse.ArgumentParser.parse_args
    seen = []

    def spy(self, args=None, namespace=None):
        seen.append(orig(self, args, namespace))
        raise _Parsed

    argparse.ArgumentParser.parse_args = spy
    try:
        try:
            tdd_check.main(argv)
        except _Parsed:
            pass
    finally:
        argparse.ArgumentParser.parse_args = orig
    assert seen, argv
