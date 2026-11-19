"""No agent-isdd markdown (outside CHANGELOG.md) may cite the deleted SKILL "Visible Progress" section."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REF = ROOT / "skills" / "spec-driven-development" / "references" / "routing-and-task-tracker.md"


def test_no_visible_progress_citations():
    offenders = [
        str(p.relative_to(ROOT))
        for p in ROOT.rglob("*.md")
        if p.name != "CHANGELOG.md"
        and "tests" not in p.relative_to(ROOT).parts
        and "Visible Progress" in p.read_text(encoding="utf-8")
    ]
    assert offenders == []


def test_routing_header_not_claiming_verbatim_skill_text():
    assert "verbatim from SKILL.md" not in REF.read_text(encoding="utf-8")


def test_task_tracker_sync_text_deleted_triggers_remain():
    text = REF.read_text(encoding="utf-8")
    for gone in ("repo-persisted planning artifact", "self-loaded", "directly from this skill",
                 "slug", "mirrored", "Mirrored"):
        assert gone not in text, gone
    head = "\n".join(text.splitlines()[:5])
    assert "Internal Routing Rule" in head and "TaskCreate" in head
    assert "Internal Routing Rule" in text
    assert "Phase tick list" in text
    assert len(text.splitlines()) <= 25
