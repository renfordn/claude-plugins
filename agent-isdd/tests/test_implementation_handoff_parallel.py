"""implementation-handoff.md: Parallel: on, tdd-parallel, Implementation Mode, approval CLI."""
from pathlib import Path

REF = (Path(__file__).resolve().parent.parent / "skills" / "spec-driven-development"
       / "references" / "implementation-handoff.md")
RAW = REF.read_text(encoding="utf-8")
TEXT = " ".join(RAW.split())  # whitespace-normalised: phrases may wrap


def test_parallel_on_for_four_plus_slices():
    assert "`Parallel: on`" in TEXT
    assert "every Standard-track handoff" in TEXT
    assert "4+ slices" not in TEXT


def test_runs_tdd_parallel_on_slicing_complete_waves():
    assert "agent-tdd:tdd-parallel" in TEXT
    assert "slicing_complete" in TEXT and "wave" in TEXT


def test_old_no_drive_rule_replaced():
    assert "Do not resume, monitor, or drive" not in TEXT
    assert "never resumes `agent-TDD` for an ordinary per-slice" not in TEXT


def test_implementation_mode_question():
    assert "Implementation Mode" in TEXT
    assert "AskUserQuestion" in TEXT
    assert "isdd-coach" in TEXT
    assert "never production code" in TEXT


def test_approval_cli_documented():
    assert 'hooks/approval.py" approve' in TEXT
    assert 'hooks/approval.py" refreeze' in TEXT
    assert "design_spec_gate" in TEXT


def _step(n):
    start = RAW.index(f"\n{n}. ")
    end = RAW.find(f"\n{n + 1}. ", start)
    return " ".join(RAW[start:end].split())


def test_step6_serial_only():
    assert "serial runs only" in _step(6).lower()
    assert "do not resume agent-TDD to implement serially" in TEXT


def test_complete_only_after_all_slices_complete():
    assert "all_slices_complete" in TEXT
    assert "active_state_file" in TEXT


def test_mode_question_before_spawn():
    assert TEXT.index("Implementation Mode: <answer>") < TEXT.index("5. Spawn `agent-tdd:agent-TDD`")
    assert "never change it without the user's say-so" in TEXT


def test_approve_conditioned_on_user_approval():
    i = TEXT.index("approval.py")
    assert "only after the user approves via `AskUserQuestion`" in TEXT
    assert "only after the user re-approves a changed scope" in TEXT


def test_approval_command_runnable_form():
    assert 'CLAUDE_PLUGIN_DATA="${CLAUDE_PLUGIN_DATA}" python3 "${CLAUDE_PLUGIN_ROOT}/hooks/approval.py" approve' in TEXT
    assert "resolved absolute paths" in TEXT
    assert "every agent-TDD spawn" in TEXT
