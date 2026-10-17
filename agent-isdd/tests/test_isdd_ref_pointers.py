"""Pointer checks for the weight-reduction split: every moved section leaves a stub in its
SKILL.md naming the reference (with a literal read-when trigger), every new reference exists,
opens "Read by", is named by exactly one stub, and stays <= 400 lines. No dangling
`references/...` path may remain in any SKILL.md."""
import hashlib
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SKILLS = ROOT / "skills"

# (skill, reference file, triggers that must appear in the stub paragraph and the
#  reference's first 5 lines)
REGISTRY = [
    ("design-author", "nelly-cache-lookup.md", ["file summary lookup", "research digest lookup"]),
    ("design-author", "nelly-persistence.md", ["file summaries", "folder summaries", "research digest"]),
    ("design-author", "deep-review.md", ["Design Validation", "Deep Review"]),
    ("design-author", "diagrams.md", ["show_widget"]),
    ("spec-driven-development", "start-protocol.md", ["intent/intent.md", "Fast Track classification"]),
    ("spec-driven-development", "subagent-delegation.md", ["spec-reviewer", "research-consolidator"]),
    ("spec-driven-development", "requirements-gate.md", ["Requirements Gate", "EARS"]),
    ("spec-driven-development", "writing-style.md", ["Writing Style", "tasks.md"]),
    ("spec-driven-development", "continue-protocol.md", ["continue", "Rollback Request Check"]),
    ("spec-driven-development", "routing-and-task-tracker.md",
     ["Internal Routing Rule", "TaskCreate"], 2),
    ("workflow-manager", "native-plan-mode.md", ["EnterPlanMode", "ExitPlanMode"]),
    ("workflow-manager", "goal-and-intent-contract.md", ["nelly_brief_cache", "before-continue"]),
    ("workflow-manager", "hook-write-back-notes.md", ["after-design", "after-tasks", "Facts worth persisting"], 4),
    ("workflow-manager", "action-rules-detail.md", ["Current Phase: Tasks", "resync", "Tasks row"], 3),
    ("workflow-manager", "scaffolding.md", ["scaffold"]),
]


def _paragraph_with(text: str, needle: str) -> str:
    for para in re.split(r"\n\s*\n", text):
        if needle in para:
            return para
    return ""


@pytest.mark.parametrize("entry", REGISTRY, ids=lambda e: f"{e[0]}/{e[1]}")
def test_reference_has_exactly_one_stub_and_read_by_header(entry):
    skill, ref, triggers = entry[:3]
    stubs = entry[3] if len(entry) > 3 else 1  # headings whose stub names this file
    ref_path = SKILLS / skill / "references" / ref
    assert ref_path.is_file(), ref_path
    lines = ref_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) <= 400, len(lines)
    head = "\n".join(lines[:5])
    assert "Read by" in head
    for t in triggers:
        assert t in head, (ref, t)
    main = (SKILLS / skill / "SKILL.md").read_text(encoding="utf-8")
    needle = f"references/{ref}"
    assert main.count(needle) == stubs, (ref, main.count(needle))
    paras = [p for p in re.split(r"\n\s*\n", main) if needle in p]
    # Several stubs may share one blank-line-delimited paragraph (e.g. table cells).
    assert 1 <= len(paras) <= stubs
    assert all("read" in p.lower() for p in paras)
    for t in triggers:
        assert any(t in p for p in paras), (ref, t)


def test_every_skill_reference_path_resolves():
    pat = re.compile(r"(?<![\w/.-])((?:\.\./[\w-]+/)?references/[a-z][\w-]*\.md)(?![\w.])")
    for skill_md in SKILLS.glob("*/SKILL.md"):
        for m in pat.finditer(skill_md.read_text(encoding="utf-8")):
            rel = m.group(1)
            target = skill_md.parent / rel
            if not target.is_file():
                # plugin-level references live at <plugin>/references (named via CLAUDE_PLUGIN_ROOT)
                target = ROOT / rel
            assert target.is_file(), (skill_md.parent.name, rel)


def test_design_author_fast_track_moved_to_shared_fast_track_reference():
    main = (SKILLS / "design-author" / "SKILL.md").read_text(encoding="utf-8")
    ft = (SKILLS / "spec-driven-development" / "references" / "fast-track.md").read_text(encoding="utf-8")
    ptr = "../spec-driven-development/references/fast-track.md"
    assert main.count(ptr) == 1
    assert "Track: Fast" in _paragraph_with(main, ptr)
    # Moved text is verbatim in the shared reference.
    for marker in ("Ready to move to Tasks", "ready for direct Slice Spec handoff to `agent-tdd`",
                   "**Escape hatch**: if satisfying the Design Gate turns out to need real"):
        assert marker in ft, marker
    assert (SKILLS / "design-author" / "SKILL.md").stat().st_size <= 13457


def test_sdd_turn_management_is_byte_identical():
    """Stall-bug guard: the Continuation Guarantee section must never be moved or reworded."""
    text = (SKILLS / "spec-driven-development" / "SKILL.md").read_text(encoding="utf-8")
    i = text.index("## Turn Management: Continuation Guarantee")
    j = text.index("## Internal Routing Rule")
    assert hashlib.sha256(text[i:j].encode()).hexdigest() == (
        "3c862a522c491ddde750bb32bd6cb3636a80884b384c6f963c70751f6f4b69a4"
    )
    assert "Subagents cannot talk to the user" in text


def test_sdd_artifact_tree_not_duplicated_but_not_lost():
    sdd = (SKILLS / "spec-driven-development" / "SKILL.md").read_text(encoding="utf-8")
    assert "<sdd-memory-dir>/" not in sdd
    assert "workflow-manager" in sdd.split("## Artifact Convention", 1)[1][:600]
    wm = SKILLS / "workflow-manager"
    wm_text = (wm / "SKILL.md").read_text(encoding="utf-8")
    wm_text += (wm / "references" / "scaffolding.md").read_text(encoding="utf-8")
    assert "<sdd-memory-dir>/" in wm_text and "recap/recap.md" in wm_text


def test_sdd_size_gate_and_handoff_intro_preserved():
    sdd_dir = SKILLS / "spec-driven-development"
    main = (sdd_dir / "SKILL.md").read_text(encoding="utf-8")
    assert (sdd_dir / "SKILL.md").stat().st_size <= 13580
    ref = (sdd_dir / "references" / "implementation-handoff.md").read_text(encoding="utf-8")
    assert "a single, one-directional handoff, not an orchestrated" in ref
    assert "**Second trigger: `Current Phase: Tasks` on continue.**" in main


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
    assert (wm_dir / "SKILL.md").stat().st_size <= 21140
    assert len(wm.splitlines()) <= 400
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


def test_no_stub_says_same_reference_without_a_path():
    """Review F3: every moved-section stub names its file explicitly."""
    for skill_md in SKILLS.glob("*/SKILL.md"):
        for line in skill_md.read_text(encoding="utf-8").splitlines():
            assert "same reference" not in line.lower(), (skill_md.parent.name, line[:100])
            assert "reference named in the table" not in line, line[:100]


def test_sdd_continue_and_start_inline_triggers_are_concrete():
    """Review F2: Continue Protocol and Start steps 3/4/6 run on every continue/start, so the
    inline text carries an imperative, concrete trigger rather than a vague read-when."""
    sdd = (SKILLS / "spec-driven-development" / "SKILL.md").read_text(encoding="utf-8")
    cont = sdd.split("## Continue Protocol", 1)[1].split("\n## ", 1)[0]
    assert "On continue/resume: FIRST run the Rollback Request Check" in cont
    assert "`rollback_pending`" in cont and "`workflow-state.json`" in cont
    assert "THEN read `references/continue-protocol.md` before acting" in cont
    start = sdd.split("## Start Protocol", 1)[1].split("\n## ", 1)[0]
    assert "Before step 5 read `references/start-protocol.md`" in start
    for t in ("steps 3, 4, 6", "intent/intent.md", "Intent Hash", "Track"):
        assert t in start, t


def test_sdd_native_plan_mode_and_artifact_stubs_point_directly_at_workflow_manager():
    """Review F5: no 3-hop chain; the stubs name the workflow-manager references themselves,
    and carry the 'user-facing approval checkpoint' reason inline."""
    sdd = (SKILLS / "spec-driven-development" / "SKILL.md").read_text(encoding="utf-8")
    npm = sdd.split("## Native Plan Mode", 1)[1].split("\n## ", 1)[0]
    assert "../workflow-manager/references/native-plan-mode.md" in npm
    assert "user-facing approval checkpoint" in npm
    art = sdd.split("## Artifact Convention", 1)[1].split("\n## ", 1)[0]
    assert "../workflow-manager/references/scaffolding.md" in art
    ref = (SKILLS / "spec-driven-development" / "references" / "routing-and-task-tracker.md").read_text(encoding="utf-8")
    assert "phase gates above" not in ref and "stays here in the orchestrator" not in ref


def test_design_author_deep_review_gate_and_findings_rule_inline_and_numbered_sanely():
    """Review F5: the findings rule keeps its reason (they travel with design_md; no separate
    handoff channel), and the inline list no longer starts at '3.'."""
    da = (SKILLS / "design-author" / "SKILL.md").read_text(encoding="utf-8")
    sec = da.split("## Design Validation: Deep Review", 1)[1].split("\n## ", 1)[0]
    assert "design_md" in sec and "no separate handoff channel" in sec
    assert "**Critical findings**" in sec and "**Non-critical findings**" in sec
    assert "\n3. " not in sec and "\n4. " not in sec
