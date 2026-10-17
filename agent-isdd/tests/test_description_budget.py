"""Description budget: always-listed agent-isdd descriptions stay short, triggers kept."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FILES = (
    sorted(ROOT.glob("skills/*/SKILL.md"))
    + sorted(ROOT.glob("agents/*.md"))
    + sorted(ROOT.glob("commands/*.md"))
)
BASELINE_TOTAL = 5030  # description chars before the weight-reduction feature


def description(path: Path) -> str:
    text = path.read_text()
    fm = text.split("---", 2)[1]
    lines = fm.splitlines()
    for i, ln in enumerate(lines):
        m = re.match(r"description:\s*(.*)$", ln)
        if not m:
            continue
        val = m.group(1).strip()
        if val in (">", ">-", "|"):
            out = []
            for nxt in lines[i + 1:]:
                if nxt.startswith((" ", "\t")):
                    out.append(nxt.strip())
                else:
                    break
            return " ".join(out)
        return val.strip('"')
    raise AssertionError(f"no description in {path}")


def d(rel: str) -> str:
    return description(ROOT / rel)


def test_skill_descriptions_trimmed():
    pickup = d("skills/isdd-pickup/SKILL.md")
    assert len(pickup) <= 420
    assert "proactively at the start of every /isdd" in pickup or "proactively at start of /isdd" in pickup
    for phrase in ("what should I work on next", "what's stalled"):
        assert phrase in pickup
    pr = d("skills/plan-reviewer/SKILL.md")
    assert len(pr) <= 320
    for phrase in ("verify this design", "sanity-check my plan", "NOT for"):
        assert phrase in pr
    for rel in ("skills/design-author/SKILL.md", "skills/workflow-manager/SKILL.md",
                "skills/requirements-agent/SKILL.md"):
        assert d(rel).startswith("[Internal — use /isdd instead]")


def test_agent_descriptions_have_no_examples():
    for p in sorted(ROOT.glob("agents/*.md")):
        desc = description(p)
        assert "<example>" not in desc, p.name
        assert desc.startswith("Use this agent when"), p.name


def test_total_description_chars_reduced_40_percent():
    total = sum(len(description(p)) for p in FILES)
    assert total <= BASELINE_TOTAL * 0.6, (total, BASELINE_TOTAL)


def test_trigger_phrases_dropped_by_the_first_trim_are_restored():
    """Review F6: shortening must not lose trigger conditions."""
    pickup = d("skills/isdd-pickup/SKILL.md")
    for ph in ("what's on the brief board", "avoid overlap", "what to do next"):
        assert ph in pickup, ph
    assert "before writing design.md/tasks.md" in d("skills/plan-reviewer/SKILL.md")
    aud = d("skills/doc-consistency-auditor/SKILL.md")
    for ph in ("duplicated", "every plugin's INTEROP.md", "interop drift"):
        assert ph in aud, ph
    assert "Delegate from requirements-agent review mode" in d("agents/spec-reviewer.md") or \
        "delegate from requirements-agent review mode" in d("agents/spec-reviewer.md")
    assert "stale or missing records" in d("commands/isdd-board-sync.md")
