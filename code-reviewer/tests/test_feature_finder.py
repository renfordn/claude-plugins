"""Test: `feature-finder` is a read-only fact-finding skill (lanes, tiers, tags), never a review."""
import re
from pathlib import Path

_PLUGIN = Path(__file__).resolve().parent.parent
_DIR = _PLUGIN / "skills" / "feature-finder"
_SKILL = _DIR / "SKILL.md"
_EVALS = _PLUGIN / "evals"


def _fm():
    return _SKILL.read_text().split("---", 2)[1]


def _desc():
    import yaml
    return yaml.safe_load(_fm())["description"]


def test_frontmatter_routes_and_forks():
    fm = _fm()
    assert re.search(r"^name: feature-finder$", fm, re.M)
    assert re.search(r"^context: fork$", fm, re.M)
    assert re.search(r"^agent: Explore$", fm, re.M)
    d = _desc()
    assert len(d) <= 300, len(d)
    for phrase in ("where is", "how does", "what calls", "impact"):
        assert phrase in d.lower(), phrase
    assert "Not" in d and "why is this broken" in d and "any bugs" in d
    assert "text" in d.lower() and "code-brief" in d


def test_skill_is_lean_and_points_at_references():
    text = _SKILL.read_text()
    assert len(text.splitlines()) <= 120
    assert "references/lanes.md" in text and "references/tiers.md" in text
    assert (_DIR / "references" / "lanes.md").is_file()
    assert (_DIR / "references" / "tiers.md").is_file()


def test_body_defines_lanes_tiers_and_tags():
    text = _SKILL.read_text()
    for lane in ("Locate", "Explain", "Trace", "Impact", "Research"):
        assert lane in text, lane
    for tier in range(5):
        assert f"Tier {tier}" in text, tier
    assert "lowest" in text.lower()
    for tag in ("observed", "inferred", "unverified"):
        assert tag in text.lower(), tag
    assert re.search(r"memory\b.{0,60}\bnever\b.{0,40}\bevidence", text, re.I | re.S)
    assert re.search(r"never calls\b.{0,20}agent-nelly|agent-nelly.{0,40}never", text, re.I)
    assert re.search(r"next action and stop", text)
    assert "current checkout" in text
    assert "coverage" in text and "execution" in text
    assert re.search(r"boundary\b.{0,80}(consent|say-so)", text, re.I | re.S)
    assert "stop" in text.lower()
    assert "Investigation complete." in text


def test_report_marker_and_ledger():
    text = _SKILL.read_text()
    assert text.count("<!--FEATURE-FINDER-REPORT-->") >= 1
    assert re.search(r"claim.*evidence.*status", text, re.I | re.S)


def test_lane_and_tier_references_cover_each():
    lanes = (_DIR / "references" / "lanes.md").read_text()
    tiers = (_DIR / "references" / "tiers.md").read_text()
    for lane in ("Locate", "Explain", "Trace", "Impact", "Research"):
        assert f"## {lane}" in lanes, lane
    for tier in range(5):
        assert f"## Tier {tier}" in tiers, tier


def test_no_review_findings_or_cache_claims():
    text = "\n".join(p.read_text() for p in _DIR.rglob("*.md")) if _DIR.exists() else ""
    assert text
    guardrails = _SKILL.read_text().split("## Guardrails", 1)[1]
    assert "ReportFindings" in guardrails
    for field in ("decision", "workflow_action", "severity", "evidence_tier"):
        assert f"`{field}`" in guardrails, field
    assert "%" not in text, "no savings percentages"
    assert not re.search(r"\bcach(e|ed|ing)\b", text, re.I), "no cache claims"
    assert "<!--CODE-REVIEWER-REPORT-->" not in text


def test_eval_case_for_where_is_x():
    case = _EVALS / "feature-finder-where-is"
    spec = (case / "case.yaml").read_text()
    assert "where is" in spec.lower() and "scaffold_script: scaffold.sh" in spec
    assert not (case / "prompt.md").exists()
    assert '"code-reviewer:feature-finder"' in spec
    for tag in ("observed", "inferred", "unverified"):
        assert tag in spec.lower()
    assert re.search(r"unverified or contradicted", spec) and "silently ignoring" in spec
    assert "no review findings" in spec
    scaffold = (case / "scaffold.sh").read_text()
    assert "client.py" in scaffold and "retry.py" in scaffold
    client = scaffold.split("cat > client.py", 1)[1].split("EOF", 2)[1]
    assert "backoff" not in client.lower() and "sleep" not in client
