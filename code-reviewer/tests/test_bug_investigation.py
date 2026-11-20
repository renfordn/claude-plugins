"""Slice 1B (R13): bug-investigation skill + read-only bug-investigator agent."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / "skills" / "bug-investigation" / "SKILL.md"
AGENT = ROOT / "agents" / "bug-investigator.md"
MARKER = "<!--BUG-INVESTIGATION-REPORT-->"


def _fm(path):
    return path.read_text().split("---", 2)[1]


def _desc(path):
    fm = _fm(path)
    m = re.search(r"^description:\s*(?:>-?|\|)?\s*\n((?:[ \t]+.*\n)+)", fm, re.M)
    if m:
        return " ".join(l.strip() for l in m.group(1).splitlines())
    return re.search(r"^description:\s*(.*)$", fm, re.M).group(1).strip().strip('"')


def test_descriptions_within_slice_budget_and_routing():
    sd, ad = _desc(SKILL), _desc(AGENT)
    assert len(sd) <= 280, len(sd)
    assert len(ad) <= 200, len(ad)
    assert ad.startswith("Use this agent when") and "<example>" not in ad
    low = sd.lower()
    for phrase in ("why is this broken", "fails since", "error in production", "failing test"):
        assert phrase in low, phrase


def test_skill_flow():
    t = SKILL.read_text()
    assert re.search(r"^name:\s*bug-investigation\s*$", _fm(SKILL), re.M)
    for word in ("symptom", "expected behavior", "environment", "time window", "outcome"):
        assert word in t.lower(), word
    assert "one focused question" in t.lower()
    assert "code-reviewer:bug-investigator" in t
    assert "code-reviewer:finding-verifier" in t and "Hypotheses" in t
    assert "confirmed" in t and "candidate" in t
    assert "reproduction" in t and "before/after" in t
    assert "/tdd" in t and "agent-tdd" in t
    assert "never fix" in t.lower()
    for hyp in ("id", "summary", "failure_scenario", "tier"):
        assert hyp in t


def test_skill_report_shape_and_no_review_fields():
    t = SKILL.read_text()
    assert MARKER in t
    assert "<!--CODE-REVIEWER-REPORT-->" not in t
    assert "ReportFindings" not in t
    for part in ("competing hypotheses", "counterevidence", "leading hypothesis", "next action",
                 "owner", "verification condition", "smallest missing input"):
        assert part in t.lower(), part
    assert "no review findings" in t.lower()


def test_agent_rules_and_tools():
    fm, t = _fm(AGENT), AGENT.read_text()
    assert re.search(r"^name:\s*bug-investigator\s*$", fm, re.M)
    assert re.search(r"^tools:\s*Read, Grep, Glob, Bash\s*$", fm, re.M)
    assert re.search(r"^model:\s*opus\s*$", fm, re.M)
    assert re.search(r"^effort:\s*medium\s*$", fm, re.M)
    low = t.lower()
    assert "3 passes" in low or "three passes" in low
    assert "information gain" in low and "smallest discriminating check" in low
    for stop in ("no new evidence", "blocked", "approval boundary", "pass limit"):
        assert stop in low, stop
    assert "unchanged query" in low
    for label in ("observed", "inferred", "associated", "unverified"):
        assert label in low, label
    assert "temporal overlap is not causation" in low
    for status in ("verified read", "available but unverified", "unavailable", "blocked"):
        assert status in low, status
    assert "never edit" in low and "tool list" in low
    assert MARKER in t
    assert "ReportFindings" not in t


def test_eval_case_present():
    case = ROOT / "evals" / "trigger-bug-investigation"
    assert (case / "prompt.md").is_file()
    assert any((case / "graders").glob("*.md"))
    g = "".join(p.read_text() for p in (case / "graders").glob("*.md"))
    assert "bug-investigation" in g


def test_amended_contract_h_ids_leading_only_marker_first_line():
    s, a = SKILL.read_text(), AGENT.read_text()
    for t in (s, a):
        assert "H1" in t and "H2" in t, "hypotheses use ids H1, H2, ..."
        assert "first line" in t.lower() and MARKER in t
    assert re.search(r"only the leading hypothesis", s, re.I)
    assert re.search(r"(never|not|don't) send (the )?other hypotheses", s, re.I)
    assert "hypothesis id" in s.lower()
    assert re.search(r"first line[^\n]*\n?[^\n]*" + re.escape(MARKER), s, re.I)


def _flat(path):
    return " ".join(path.read_text().split())


def test_frontmatter_is_valid_yaml():
    import yaml
    for path in (SKILL, AGENT):
        data = yaml.safe_load(_fm(path))
        assert isinstance(data, dict), path
        assert data.get("name") and data.get("description"), path


def test_confirmed_requires_upheld_and_proof_not_or():
    s = _flat(SKILL)
    assert re.search(r"confirmed\*\* only if the verifier upholds it AND there is a verified "
                     r"mechanism plus a reproduction or before/after proof", s)
    assert not re.search(r"upholds it OR", s)
    assert re.search(r"upheld[^.]{0,40}without (that )?proof[^.]{0,40}candidate", s)
    assert re.search(r"downgraded[^.]{0,60}candidate", s, re.I)


def test_refuted_leader_rule():
    s = _flat(SKILL)
    assert re.search(r"refutes[^.]{0,80}\*\*refuted\*\*[^.]{0,80}counterevidence", s, re.I)
    assert re.search(r"discriminating check of the next[- ]ranked hypothesis", s, re.I)
    assert re.search(r"re-spawning[^.]{0,80}counts toward the 3-pass limit", s, re.I)


def test_label_to_tier_mapping_for_verifier_brief():
    s = _flat(SKILL)
    for label, tier in (("observed and reproduced", "tier-1"), ("observed", "tier-2"),
                        ("inferred", "tier-3"), ("associated", "tier-4"),
                        ("unverified", "tier-5")):
        assert re.search(rf"`?{label}`?\s*(?:->|→)\s*`?{tier}`?", s), (label, tier)


def test_description_routes_away_from_review_and_research():
    d = _desc(SKILL)
    assert len(d) <= 280, len(d)
    assert re.search(r"not for reviewing a change \(code-reviewer\) or code research "
                     r"\(feature-finder\)", d, re.I)


def test_agent_rule_proximity():
    t = _flat(AGENT)
    assert re.search(r"at most 3 passes", t, re.I)
    assert re.search(r"never repeat an unchanged query", t, re.I)
    assert re.search(r"enforced by your tool list", t, re.I)
    assert re.search(r"Temporal overlap is not causation", t)
    assert re.search(r"observed[^.]{0,20}inferred[^.]{0,20}associated[^.]{0,20}unverified|"
                     r"`observed`[^.]{0,300}`inferred`[^.]{0,300}`associated`[^.]{0,300}`unverified`", t)


def test_eval_has_llm_grader_with_three_checks():
    graders = ROOT / "evals" / "trigger-bug-investigation" / "graders"
    llm = [p.read_text() for p in graders.glob("*.md") if "type: llm" in p.read_text()]
    assert llm, "needs an llm grader"
    g = " ".join(llm[0].split()).lower()
    assert re.search(r"deploy[^.]{0,80}not[^.]{0,40}cause", g)
    assert re.search(r"mechanism[^.]{0,120}zerodivisionerror|zerodivisionerror[^.]{0,120}mechanism", g)
    assert "candidate" in g
    assert re.search(r"(no|nothing)[^.]{0,40}edit", g)
