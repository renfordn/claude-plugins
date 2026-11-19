"""Pins for workflow-manager/SKILL.md and its references (split from test_isdd_ref_pointers.py)."""
import re

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILLS = ROOT / "skills"


def _paragraph_with(text: str, needle: str) -> str:
    for para in re.split(r"\n\s*\n", text):
        if needle in para:
            return para
    return ""


def test_wm_native_plan_mode_summary_keeps_the_exit_rule_inline():
    wm = (SKILLS / "workflow-manager" / "SKILL.md").read_text(encoding="utf-8")
    sec = wm.split("## Native Plan Mode Gate", 1)[1].split("\n## ", 1)[0]
    assert "ExitPlanMode" in sec and "only at handoff" in sec
    assert len(sec) < 1200
    ref = (SKILLS / "workflow-manager" / "references" / "native-plan-mode.md").read_text(encoding="utf-8")
    assert "Only call `ExitPlanMode` once Design is approved and implementation has been requested" in ref


def test_wm_table_rows_and_plan_board_paragraph_stay_inline():
    wm = (SKILLS / "workflow-manager" / "SKILL.md").read_text(encoding="utf-8")
    for needle in ("| `after-design` |", "| `after-tasks` |", "| `continue` |", "| `handoff` |",
                   "| Tasks |", "**Verification Step", "**Plan Board sync", "## Guardrails"):
        assert needle in wm, needle
    ref = (SKILLS / "workflow-manager" / "references" / "action-rules-detail.md").read_text(encoding="utf-8")
    assert "**`Current Phase: Tasks` special case (added 2026-09-24)**" in ref
    assert "resync every field that still reflects the pre-handoff state" in ref
    notes = (SKILLS / "workflow-manager" / "references" / "hook-write-back-notes.md").read_text(encoding="utf-8")
    assert "design-gate discoveries" in notes and "task-slicing discoveries" in notes


def test_wm_size_gate_and_scaffolding_anchor():
    wm_dir = SKILLS / "workflow-manager"
    wm = (wm_dir / "SKILL.md").read_text(encoding="utf-8")
    assert (wm_dir / "SKILL.md").stat().st_size <= 17500
    assert len(wm.splitlines()) <= 160
    assert "sdd_memory.py" in wm and "--spec-path" in wm  # path resolution stays inline
    scaf = (wm_dir / "references" / "scaffolding.md").read_text(encoding="utf-8")
    assert "<sdd-memory-dir>/" in scaf and "only `tasks.md` inside it is conditional on `Track`" in scaf
    notes = (wm_dir / "references" / "hook-write-back-notes.md").read_text(encoding="utf-8")
    assert "there is no agent-isdd-evaluated `Tasks` checklist to run here" in notes


def test_wm_nelly_write_back_paragraph_moved_verbatim():
    ref = (SKILLS / "workflow-manager" / "references" / "hook-write-back-notes.md").read_text(encoding="utf-8")
    assert "call `agent-nelly:agent-nelly` with a\n`new facts` batch of project-level discoveries from this phase" in ref
    wm = (SKILLS / "workflow-manager" / "SKILL.md").read_text(encoding="utf-8")
    assert "**Nelly write-back" in wm and "`new facts`" in wm and "`error lesson`" in wm  # trigger terms stay


def test_wm_nelly_writeback_stub_keeps_filter_and_names_reference_path():
    """Review F1: the filter and the fact-vs-error-lesson pointer stay inline, and the
    paragraph names the reference path itself (reachable at after-requirements). The path
    count for hook-write-back-notes.md is therefore 4 (this paragraph + 3 table cells)."""
    wm = (SKILLS / "workflow-manager" / "SKILL.md").read_text(encoding="utf-8")
    para = _paragraph_with(wm, "**Nelly write-back")
    assert "independently of this feature's own artifacts" in para
    assert "ephemeral workflow state never qualifies" in para
    assert "INTEROP.md" in para and "agent-nelly" in para
    assert "references/hook-write-back-notes.md" in para
