"""agent-tdd release 3 consumers: BLOCKED/coverage-only docs and phase-less report tolerance."""
import sys
from pathlib import Path

import hook_test_utils as h

sys.path.insert(0, h.HOOKS_DIR)
import high_risk_reviewer  # noqa: E402
import impl_progress  # noqa: E402
import subagent_report  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
HANDOFF = (ROOT / "skills/spec-driven-development/references/implementation-handoff.md").read_text()
INTEROP = (ROOT / "references/interop-agent-tdd.md").read_text()
COACH = (ROOT / "skills/isdd-coach/SKILL.md").read_text()

BLOCKED = ('<!--AGENT-TDD-REPORT-->\n<!--AGENT-TDD-BLOCKED: reason="no e2e harness: searched"-->\n'
           "**Plan** — Slice 3: ui form\n")


def test_handoff_handles_blocked_report():
    for s in ("AGENT-TDD-BLOCKED", "AskUserQuestion", "add a harness slice", "without E2E",
              "Hook Notes", "dependents", "independent slices", "AGENT-TDD-OUTCOME: coverage-only"):
        assert s in HANDOFF, s


def test_interop_documents_markers_fields_guard_and_bypass():
    for s in ("AGENT-TDD-OUTCOME", "AGENT-TDD-BLOCKED", "`ui`", "**UI:**", "**Blocked:**",
              "red_first_guard", "Bash", "bypass"):
        assert s in INTEROP, s


def test_coach_covers_release3_flow():
    for s in ("tdd_check.py start", "done", "coverage --mutant", "bypass", "red_first_guard",
              "user_led_guard", "BLOCKED"):
        assert s in COACH, s
    assert len(COACH.splitlines()) <= 130


def test_phaseless_blocked_report_is_tolerated(tmp_path):
    assert high_risk_reviewer.parse_agent_tdd_phase(BLOCKED) == (False, "unknown")
    assert impl_progress.record(str(tmp_path), BLOCKED)
    data = impl_progress.load(str(tmp_path))
    assert data["slices"] == {} and data["events"][-1]["phase"] is None
    assert subagent_report.extract_rollback_request(BLOCKED) is None
    assert subagent_report.extract_plan_validity_flag(BLOCKED) is None
