"""
Test: SKILL.md documents the ReportFindings payload contract the model must hand over.

Regression for "Failed to report review findings" (too_big on findings[N].short_summary):
the limits used to live only in INTEROP.md, which the model never reads at review time.
"""

import json
import re
from pathlib import Path

_SKILL_PATH = Path(__file__).resolve().parent.parent / "skills" / "code-reviewer" / "SKILL.md"

_ALLOWED_FIELDS = {"file", "line", "short_summary", "summary", "failure_scenario", "category", "verdict", "outcome"}
_REQUIRED_FIELDS = {"file", "summary", "failure_scenario"}


def _section(content: str) -> str:
    match = re.search(r"## ReportFindings Payload.*?(?=\n## )", content, re.S)
    assert match, "SKILL.md is missing the '## ReportFindings Payload' section"
    return match.group(0)


def test_payload_section_states_hard_limits():
    section = _section(_SKILL_PATH.read_text())
    assert "60" in section and "short_summary" in section
    assert "32" in section, "max findings per call not documented"
    assert "failure_scenario" in section


def test_payload_section_maps_review_level_to_tool_level():
    section = _section(_SKILL_PATH.read_text())
    for mapping in ("Quick→`low`", "Standard→`medium`", "Deep→`high`", "Ultra→`xhigh`"):
        assert mapping in section, f"missing level mapping {mapping}"


def test_example_finding_is_schema_valid():
    section = _section(_SKILL_PATH.read_text())
    block = re.search(r"```json\n(.*?)```", section, re.S)
    assert block, "payload section needs a JSON example finding"
    finding = json.loads(block.group(1))
    assert set(finding) <= _ALLOWED_FIELDS, f"example uses non-tool fields: {set(finding) - _ALLOWED_FIELDS}"
    assert _REQUIRED_FIELDS <= set(finding)
    assert len(finding["short_summary"]) <= 60
    assert len(finding["category"]) <= 40
    assert finding["verdict"] in {"CONFIRMED", "PLAUSIBLE"}


def test_payload_section_says_retry_on_validation_error():
    section = _section(_SKILL_PATH.read_text())
    assert "path" in section and "call again" in section
