"""Isolated utility for parsing and detecting the MODEL-ESCALATE marker
agent-tdd emits in a handoff report when it needs to escalate to a higher
model tier mid-slice (see agent-tdd/references/escalation-paths.md, Phase
3.4). Deliberately independent of agent-isdd's before_continue hook so it
can be developed and tested on its own; before_continue.py (Task 8) imports
`detect_model_escalate_in_report` rather than re-implementing detection.

Two marker vocabularies exist in the wild and are both accepted here:
  - from_model="Haiku" to_model="Sonnet"        (agent-isdd/agent-tdd hook contract)
  - attempted_at_haiku=true suggest_tier="sonnet" (escalation-paths.md's documented example)
`suggest_tier` is treated as an alias for `to_model`, and `attempted_at_haiku=true`
implies `from_model="haiku"` when `from_model` isn't otherwise present.
"""
import re
from datetime import datetime, timezone

_MARKER_PATTERN = re.compile(r"<!--AGENT-TDD-MODEL-ESCALATE:\s*([^>]*?)-->", re.DOTALL)
_FIELD_PATTERN = re.compile(r'(\w+)\s*=\s*"([^"]*)"')
_BOOL_FIELD_PATTERN = re.compile(r"(\w+)\s*=\s*(true|false)", re.IGNORECASE)


def parse_model_escalate_marker(marker_text):
    """Parse a single MODEL-ESCALATE marker's raw text into a structured dict.

    Args:
        marker_text: The full marker comment, e.g.
            '<!--AGENT-TDD-MODEL-ESCALATE: reason="..." from_model="Haiku" to_model="Sonnet"-->'
            A bare fields fragment (without the comment delimiters) also works.

    Returns:
        Dict with keys {reason, from_model, to_model, timestamp} on success,
        or None if the marker is missing a reason, missing to_model (there is
        nothing usable to escalate to), or doesn't parse as key="value" pairs
        at all (malformed).
    """
    if not marker_text:
        return None

    match = _MARKER_PATTERN.search(marker_text)
    body = match.group(1) if match else marker_text

    fields = dict(_FIELD_PATTERN.findall(body))
    for key, value in _BOOL_FIELD_PATTERN.findall(body):
        fields.setdefault(key, value)

    if not fields:
        return None

    reason = fields.get("reason")
    if not reason:
        return None

    to_model = fields.get("to_model") or fields.get("suggest_tier")
    if not to_model:
        return None

    from_model = fields.get("from_model")
    if not from_model and fields.get("attempted_at_haiku", "").lower() == "true":
        from_model = "haiku"

    return {
        "reason": reason,
        "from_model": from_model,
        "to_model": to_model,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def escalation_message(escalation):
    """The systemMessage telling the caller how to re-spawn agent-TDD at the higher tier."""
    reason = escalation.get("reason") or "unknown issue"
    from_model = escalation.get("from_model") or "Haiku"
    to_model = escalation.get("to_model") or "Sonnet"
    return (
        f"🚀 **Model Escalation Detected**\n\n"
        f"**Issue:** {reason}\n\n"
        f"**Action:** Call the `get_spawn_context` tool from plugin-harness's bundled "
        f"`spawn-context` MCP server (args: agent_type=\"agent-tdd\", cwd=this project) to "
        f"pull accumulated context from the {from_model}-tier attempt, then re-spawn "
        f"`agent-TDD` at **{to_model}** tier with that context so it can continue from where "
        f"the lower tier left off. The tool's exact callable name is harness-prefixed (not "
        f"the bare string `get_spawn_context`) — if it isn't already visible, use ToolSearch "
        f"with query \"get_spawn_context\" to find and load it before calling it.\n"
    )


def detect_model_escalate_in_report(handoff_text):
    """Find and parse the first MODEL-ESCALATE marker in a free-text report.

    Args:
        handoff_text: Full handoff report text (may contain other markers,
            prose, or code blocks around the marker).

    Returns:
        Parsed dict (see parse_model_escalate_marker) for the first
        well-formed marker found, or None if no marker is present or the
        only marker(s) present are malformed.
    """
    if not handoff_text:
        return None

    for match in _MARKER_PATTERN.finditer(handoff_text):
        parsed = parse_model_escalate_marker(match.group(0))
        if parsed is not None:
            return parsed

    return None
