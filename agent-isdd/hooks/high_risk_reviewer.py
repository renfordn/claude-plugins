#!/usr/bin/env python3
"""
High-risk slice code-reviewer auto-invite.

Tracks high-risk slices from tasks.md and reminds user to run code-reviewer
during agent-tdd's Green→Refactor pauses. Surfaces a checkpoint after all
slices complete to verify code-reviewer was run on each high-risk slice.
"""
import datetime
import json
import os
import sys
import re

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from sdd_state import active_state_file, is_user_led, parse_state, parse_state_json, write_test_author_pending
except ImportError:
    def parse_state(path):
        return {}
    def is_user_led(fields):
        return False
    def active_state_file(cwd):
        return None
    def parse_state_json(path):
        return {}
    def write_test_author_pending(path, slices, detected_at):
        pass

import markers
import review_tracking

try:
    from subagent_report import report_text_from_payload
except ImportError:
    def report_text_from_payload(payload):
        return payload.get("last_assistant_message") or ""


# Regex patterns for markdown parsing
# Slice heading and Risk Tier parsing live in review_tracking (shared, alphanumeric ids).
_FILES_PATTERN = r'\*\*Files:\*\*\s+(.+?)(?=\n\n|\n###|\Z)'
_FILE_PATH_PATTERN = r'`([^`]+)`'


def _extract_backtick_paths(text: str) -> list:
    """Extract all backtick-quoted paths from text.

    Args:
        text: Text containing backtick-quoted paths

    Returns:
        List of paths found in backticks
    """
    return re.findall(_FILE_PATH_PATTERN, text)


def parse_agent_tdd_phase(report_text: str) -> tuple[bool, str]:
    """
    Parse AGENT-TDD-PHASE marker from agent-tdd SubagentStop report.

    Extracts the phase marker from agent-tdd's report to determine if the
    slice is in green_pause (needs code review) or other terminal phases.

    Args:
        report_text: agent-tdd SubagentStop report text (max 16KB, may contain
                    large handoff details)

    Returns:
        tuple[bool, str]: (is_green_pause, phase_name)
        - is_green_pause: True if phase is 'green_pause', False otherwise
        - phase_name: Extracted phase name ('green_pause', 'refactor_complete',
                     'slicing_complete', 'all_slices_complete') or 'unknown'
                     if no valid marker found

    Note:
        If multiple markers exist, returns the first one found.
        If marker is malformed or phase name is unrecognized, returns
        (False, 'unknown') with no exceptions.
    """
    # Regex: match <!--AGENT-TDD-PHASE:phase_name-->
    pattern = r"<!--AGENT-TDD-PHASE:(green_pause|refactor_complete|slicing_complete|all_slices_complete)-->"
    match = re.search(pattern, report_text)

    if not match:
        return (False, "unknown")

    phase_name = match.group(1)
    is_green_pause = phase_name == "green_pause"
    return (is_green_pause, phase_name)


def read_tasks_md(feature_dir):
    """Read tasks.md and extract all phases with Risk Tier and Files.

    Supports both old format (## Phase N: ... ### Risk Tier) and new format
    (**Risk Tier:** ... **Files:** ...).

    Args:
        feature_dir: Directory containing tasks/tasks.md

    Returns:
        List of phase objects with structure:
        {
            "name": "Phase description",
            "risk": "high-risk" | "standard",
            "files": ["file1.py", "file2.py", ...]
        }
    """
    tasks_file = os.path.join(feature_dir, "tasks", "tasks.md")
    try:
        with open(tasks_file, 'r', encoding='utf-8') as f:
            content = f.read()
    except (OSError, FileNotFoundError):
        return []

    phases = []
    heads = list(review_tracking._HEADING.finditer(content))

    for i, phase_match in enumerate(heads):
        line_end = content.find("\n", phase_match.end())
        line_end = len(content) if line_end == -1 else line_end
        phase_name = content[phase_match.end():line_end].strip()
        phase_start = phase_match.start()
        phase_end = heads[i + 1].start() if i + 1 < len(heads) else len(content)
        phase_text = content[phase_start:phase_end]

        # New format (**Risk Tier:** x) first, then old (### Risk Tier\n- `x`)
        risk_match = (review_tracking._TIER_NEW.search(phase_text)
                      or review_tracking._TIER_OLD.search(phase_text))

        if not risk_match:
            # No risk tier found, skip this phase
            continue

        risk_tier = risk_match.group(1).lower()

        # Extract Files: **Files:** `file1`, `file2`, ...
        files = []
        files_match = re.search(_FILES_PATTERN, phase_text, re.DOTALL)
        if files_match:
            files_text = files_match.group(1)
            files = _extract_backtick_paths(files_text)

        phases.append({
            "id": markers.normalize_slice_id(phase_match.group(1)),
            "name": phase_name,
            "risk": risk_tier,
            "files": files
        })

    return phases


def _waves_stamped(feature_dir):
    """True when tasks.md carries `**Wave:**` stamps (parallel_plan waves --write, Parallel: on)."""
    try:
        with open(os.path.join(feature_dir, "tasks", "tasks.md"), encoding="utf-8") as fh:
            return bool(re.search(r"^\*\*Wave:\*\*\s*\d", fh.read(), re.M))
    except OSError:
        return False


def get_high_risk_phases(tasks_md_phases):
    """Filter phases to only high-risk ones.

    Whether each high-risk slice was reviewed is decided by review_tracking, not here.

    Args:
        tasks_md_phases: List of phase objects from read_tasks_md()

    Returns:
        List of phases with risk_tier = "high-risk"
    """
    return [p for p in tasks_md_phases if p.get("risk") == "high-risk"]


def get_code_reviewer_checkpoint(feature_dir):
    """Checkpoint about high-risk slices; reviewed state comes from review_tracking
    (the workflow-state.json `reviewed` map and any Review Fallback)."""
    high_risk = get_high_risk_phases(read_tasks_md(feature_dir))

    if not high_risk:
        return None  # No high-risk slices; no checkpoint needed

    unreviewed_ids = review_tracking.unreviewed_high_risk(feature_dir)
    titles = {p["id"]: p["name"] for p in high_risk}
    unreviewed = [f"Slice {i}: {titles.get(i, '')}".rstrip(": ") for i in unreviewed_ids]
    reviewed_count = len(high_risk) - len(unreviewed_ids)

    if unreviewed:
        return {
            "type": "checkpoint",
            "high_risk_count": len(high_risk),
            "reviewed_count": reviewed_count,
            "unreviewed_phases": unreviewed,
            "message": (
                f"\u26a0\ufe0f  **Code Review Checkpoint**\n\n"
                f"**High-Risk Slices**: {len(high_risk)} total\n"
                f"**Reviewed**: {reviewed_count}\n"
                f"**Pending Review**: {len(unreviewed)}\n\n"
                f"Recommended: Run `code-reviewer` on these high-risk slices if not already done:\n"
            ) + "\n".join(f"- {p}" for p in unreviewed) +
                f"\n\nagent-tdd's review gate blocks resuming a paused agent-TDD until a review "
                f"is recorded; this list only tracks which high-risk slices have been reviewed."
        }

    return {
        "type": "success",
        "message": (
            f"\u2705 **All high-risk slices reviewed** ({len(high_risk)} total)\n\n"
            f"code-reviewer was run on all {len(high_risk)} high-risk slices."
        )
    }


def main(payload=None):
    """
    Hook entry point: fires on SubagentStop (when agent-tdd:agent-TDD completes).

    Initializes high-risk phase tracking and surfaces a checkpoint reminding
    the user to run code-reviewer on any high-risk slices before proceeding.

    Integration: Wired to hooks.json SubagentStop event after subagent_report.py
    so it runs immediately when agent-tdd finishes. Returns the systemMessage text (or
    None) instead of printing it directly, so subagent_dispatch.py can run this alongside
    the other SubagentStop hooks in one process, in that same order, and merge their
    messages. Standalone invocation (tests, direct hooks.json entry) still reads stdin and
    prints exactly as before via the __main__ block below.
    """
    if payload is None:
        try:
            payload = json.load(sys.stdin)
        except (json.JSONDecodeError, ValueError):
            payload = {}

    # review_tracking is the sole writer of the `reviewed` map; fail open.
    try:
        review_tracking.evaluate(payload)
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write(f"[high_risk_reviewer] review_tracking failed: {exc}\n")

    # The passive reminder/checkpoint only applies to agent-TDD and code-reviewer stops.
    # (A payload with no agent_type, e.g. a legacy standalone invocation, is not filtered.)
    agent = str(payload.get("agent_type") or "").split(":")[-1].lower()
    if agent and agent not in ("agent-tdd", "code-reviewer"):
        return None

    cwd = payload.get("cwd") or os.getcwd()
    state_path = active_state_file(cwd)

    if not state_path:
        return None

    feature_dir = os.path.dirname(state_path)

    # Initialize tracking on first pass
    tasks_md_phases = read_tasks_md(feature_dir)
    high_risk = get_high_risk_phases(tasks_md_phases)

    # Conditional slicing_complete pause (design.md touchpoint 2): when agent-tdd's own
    # report is at the slicing_complete checkpoint and >=1 slice is high-risk, write
    # test_author_pending so the caller's Implementation Handoff step can spawn test-author
    # and resume. Zero high-risk slices: no write (inertness), fall through to the existing
    # green_pause checkpoint logic below unchanged.
    report_text = report_text_from_payload(payload)
    if report_text:
        _, phase_name = parse_agent_tdd_phase(report_text)
        if phase_name == "slicing_complete" and high_risk:
            slices = [{"name": p["name"], "files": p.get("files", [])} for p in high_risk]
            names = "\n".join(f"- {s['name']}" for s in slices)
            if is_user_led(parse_state(state_path)):
                return (
                    f"agent-TDD: wave plan ready with {len(slices)} high-risk slice(s):\n{names}\n\n"
                    "This is user-led mode (Implementation Mode: user): do not run agent-tdd:tdd-parallel "
                    "or resume agent-TDD. Walk the slices with the isdd-coach skill; high-risk "
                    "slices still need a scoped code-reviewer review (or the AskUserQuestion "
                    "fallback) before Complete."
                )
            if _waves_stamped(feature_dir):
                # Parallel: on — the tdd-parallel lead owns test-author per wave; a serial
                # resume here would make agent-TDD implement everything alongside the workers.
                return (
                    f"agent-TDD: wave plan ready with {len(slices)} high-risk slice(s):\n{names}\n\n"
                    "Run agent-tdd:tdd-parallel as lead; it spawns test-author for each "
                    "high-risk slice in its wave before the implementers."
                )
            json_path = os.path.join(feature_dir, "workflow-state.json")
            detected_at = datetime.datetime.now().isoformat(timespec="seconds")
            write_test_author_pending(json_path, slices, detected_at)
            return (
                f"agent-TDD: {len(slices)} high-risk slice(s) need test-author before "
                f"implementation can proceed:\n{names}\n\n"
                "Recorded as test_author_pending in workflow-state.json. Spawn test-author "
                "for each, then resume agent-TDD via SendMessage with the bundled results."
            )

    # Get checkpoint message
    checkpoint = get_code_reviewer_checkpoint(feature_dir)
    if checkpoint:
        return checkpoint["message"]

    return None


if __name__ == "__main__":
    _msg = main()
    if _msg:
        print(json.dumps({"systemMessage": _msg}))
    sys.exit(0)
