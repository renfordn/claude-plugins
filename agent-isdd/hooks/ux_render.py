#!/usr/bin/env python3
"""
Agent-UX rendering hook (SubagentStop) -- inline breadcrumb refresh.

Reads the current phase from workflow-state.json and emits a cheap breadcrumb-refresh
systemMessage. Phase *transitions* are not detected or rendered here: the
spec-driven-development skill delegates the `phase_transition` envelope to agent-ux:ux-agent
itself at every phase change, so this hook only ever needs the same-phase path.

Note: an earlier version tried to read/write a "previous phase" via agent-cache-plugin over
HTTP (localhost:7771) to detect transitions. That server never existed (see cache_hook.py),
so the read always missed and the transition branch never fired; it was removed as dead code.
"""
import json
import os
import sys
import re

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def get_feature_slug(state_path):
    """Extract feature slug from sdd-memory or tdd-memory path."""
    for pattern in [r'/sdd-memory/([^/]+)/', r'/tdd-memory/([^/]+)/']:
        match = re.search(pattern, state_path)
        if match:
            return match.group(1)
    return os.path.basename(os.path.dirname(state_path))


def read_workflow_state(feature_dir):
    """Read workflow-state.json from feature directory."""
    workflow_json = os.path.join(feature_dir, "workflow-state.json")
    try:
        with open(workflow_json, 'r') as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def render_breadcrumb_only(phase_state, feature_slug):
    """Breadcrumb renders inline in the skill response; no agent-ux subagent call needed."""
    sys.stderr.write(f"[ux-hook] breadcrumb inline: {phase_state}\n")
    return None


def main(payload=None):
    """
    Hook: Runs after SubagentStop (phase state finalized).

    Reads current_phase from workflow-state.json and returns a breadcrumb-refresh
    systemMessage (or None when there is no active feature / phase).

    Returns the systemMessage text (or None) rather than printing it directly, so the
    subagent_dispatch.py dispatcher can run this alongside the other SubagentStop hooks in one
    process and merge their messages. Standalone invocation (tests, direct hooks.json entry)
    still reads stdin and prints exactly as before via the __main__ block below.
    """
    if payload is None:
        try:
            payload = json.load(sys.stdin)
        except (json.JSONDecodeError, ValueError):
            payload = {}

    state_path = payload.get("state_path")
    if not state_path:
        return None

    feature_dir = os.path.dirname(state_path)
    feature_slug = get_feature_slug(state_path)

    workflow_state = read_workflow_state(feature_dir)
    current_phase = workflow_state.get("current_phase", "")
    if not current_phase:
        return None

    render_breadcrumb_only(current_phase, feature_slug)
    return f"UX: breadcrumb update ({current_phase})"


if __name__ == "__main__":
    _msg = main()
    if _msg:
        print(json.dumps({"systemMessage": _msg}))
    sys.exit(0)
