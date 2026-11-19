"""workflow-manager SKILL.md is lean (<=160 lines, Input/Output/Done when) and documents the R2
guards (Risk, Implementation Mode, approval hash, Complete guard) accurately against the hooks."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WM = ROOT / "skills" / "workflow-manager"
SKILL = (WM / "SKILL.md").read_text(encoding="utf-8")
SWR = (WM / "references" / "state-write-responsibilities.md").read_text(encoding="utf-8")
TRACK = (WM / "references" / "track-and-availability-details.md").read_text(encoding="utf-8")
CLI = 'CLAUDE_PLUGIN_DATA="${CLAUDE_PLUGIN_DATA}" python3 "${CLAUDE_PLUGIN_ROOT}/hooks/approval.py"'


def _frontmatter():
    return SKILL.split("---", 2)[1]


def _section(text, heading):
    return text.split(heading, 1)[1].split("\n## ", 1)[0]


def test_skill_is_at_most_160_lines_and_byte_capped():
    assert len(SKILL.splitlines()) <= 160
    assert (WM / "SKILL.md").stat().st_size <= 17500


def test_frontmatter_is_user_invocable_false_without_internal_prefix():
    fm = _frontmatter()
    assert re.search(r"^user-invocable:\s*false\s*$", fm, re.M)
    assert "disable-model-invocation" not in fm
    assert "[Internal" not in fm


def test_input_output_done_when_sections_present():
    for h in ("## Input", "## Output", "## Done when"):
        assert h in SKILL, h


def test_visible_progress_citation_retargeted_to_ux_conventions():
    assert "Visible Progress" not in SKILL
    assert "references/ux-conventions.md" in SKILL
    assert (ROOT / "references" / "ux-conventions.md").is_file()


def test_risk_and_mode_fields_documented_with_pointers_not_restatement():
    for needle in ("Risk Reason", "Implementation Mode", "Approval Hash", "Review Fallback",
                   "references/risk-depth.md", "references/implementation-handoff.md"):
        assert needle in SKILL, needle
    # source wording lives in the pointed-to files; the signal table is not restated here
    assert "auth/authz" not in SKILL


def test_guards_documented_as_the_hooks_behave():
    assert "state_guard" in SKILL and "complete_guard" in SKILL
    sec = SKILL
    assert "Risk only rises" in sec or "Risk can only rise" in sec
    assert "Standard" in sec and "Fast" in sec
    assert "Accepted via AskUserQuestion: <slice ids | all>: <reason>" in SKILL
    assert "stop_check" in SWR and "once per change" in SWR
    assert "Named ids" in SWR and "`all` waives everything" in SWR
    assert "Track leaving Standard" in SKILL
    assert "Standard leaving Standard" not in SKILL
    assert "does not deny a change but logs it in `hook_history`" in SKILL


def test_approval_cli_form_and_gate_described():
    assert CLI + ' approve "<spec_dir>"' in SKILL or "approve|refreeze" in SKILL
    assert CLI in SKILL
    assert "AskUserQuestion" in SKILL
    assert "design_spec_gate" in SKILL
    assert "Implementation Requested" in SKILL
    low = SKILL.lower()
    assert "freez" in low or "records the hash" in low


def test_handoff_row_notes_tdd_parallel_and_implementation_mode():
    row = next(l for l in SKILL.splitlines() if l.startswith("| `handoff` |"))
    assert "tdd-parallel" in row and "Parallel: on" in row
    assert "Implementation Mode" in row


def test_write_responsibilities_ref_covers_new_fields():
    for needle in ("risk", "risk_reason", "implementation_mode", "approval_hash",
                   "approval_pending", "approval.py", "reviewed", "review_tracking"):
        assert needle in SWR, needle
    assert "sdd_state.update_json" in SWR


def test_track_ref_covers_risk_gate_and_goal_detail():
    assert "Risk: low" in TRACK and "state_guard" in TRACK
    assert "Intent Alignment Status" in TRACK
    assert "drift" in TRACK


def test_swr_mirrored_list_matches_post_write_check_field_map():
    import sys
    sys.path.insert(0, str(ROOT / "hooks"))
    import post_write_check
    mirrored = SWR.split("- **Mirrored fields**", 1)[1].split("- **Hook-owned", 1)[0]
    for key in post_write_check.FIELD_MAP.values():
        assert f"`{key}`" in mirrored, key


def test_handoff_row_pins_serial_fast_complete_timing():
    row = next(l for l in SKILL.splitlines() if l.startswith("| `handoff` |"))
    assert "serial Fast: set Complete after the Slice Spec report" in row


def test_after_requirements_facts_inline_and_long_lines_broken():
    row = next(l for l in SKILL.splitlines() if l.startswith("| `after-requirements` |"))
    assert "interface assumptions" in row and "non-goals" in row
    assert max(len(l) for l in SKILL.splitlines() if not l.startswith("|")) <= 700
    assert "full rules" not in SKILL and "only `all` waives" not in SKILL  # single statement lives in the ref
