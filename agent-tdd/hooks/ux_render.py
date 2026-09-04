#!/usr/bin/env python3
"""
Agent-UX rendering hook for TDD — token-optimized for cache-backed rendering.

Integrates with agent-cache and agent-ux to render TDD phase indicators efficiently:
- High-frequency path: breadcrumb_only with cached phase_state (~100 tokens)
- Low-frequency path: phase_transition on RED/GREEN/REFACTOR changes (~400 tokens)

TDD phases: Plan → Red → Green → Review → Refactor → Validate
Detected from phase_state pattern: "TDD:red", "TDD:green", "TDD:refactor", etc.

Called from SubagentStop hook after phase state finalized.
"""
import json
import os
import sys
import re

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def get_feature_slug(state_path):
    """Extract feature slug from tdd-memory path."""
    match = re.search(r'/tdd-memory/([^/]+)/', state_path)
    return match.group(1) if match else os.path.basename(os.path.dirname(state_path))


def read_workflow_state(feature_dir):
    """Read workflow-state.json from feature directory."""
    workflow_json = os.path.join(feature_dir, "workflow-state.json")
    try:
        with open(workflow_json, 'r') as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def cache_read_via_mcp(key, scope):
    """Read from agent-cache via MCP tool."""
    sys.stderr.write(f"[ux-hook-tdd] cache_read({key}, {scope})\n")
    return {"hit": False}


def cache_write_via_mcp(key, value, scope, ttl_seconds=3600):
    """Write to agent-cache via MCP tool."""
    sys.stderr.write(f"[ux-hook-tdd] cache_write({key}, {scope}, ttl={ttl_seconds})\n")
    return {"success": True}


def render_breadcrumb_only(phase_state, feature_slug):
    """
    Call agent-ux with minimal breadcrumb_only event (~100 tokens).

    For TDD, phase_state follows pattern: "TDD:red", "TDD:green", "TDD:refactor"
    """
    sys.stderr.write(f"[ux-hook-tdd] agent-ux breadcrumb_only: {phase_state}\n")
    return {"success": True, "breadcrumb": f"TDD: {phase_state}"}


def render_phase_transition(from_phase, to_phase, feature_slug, phase_state, summary=""):
    """
    Call agent-ux with phase_transition event (~400 tokens).

    Note: agent-ux automatically excludes chapter marking for TDD:* phase_states
    per INTEROP.md "TDD-internal stage exclusion" rule.
    """
    sys.stderr.write(f"[ux-hook-tdd] agent-ux phase_transition: {from_phase} → {to_phase}\n")
    return {"success": True}


def is_phase_change(old_phase, new_phase):
    """Detect if this is an actual TDD stage transition."""
    if not old_phase or not new_phase:
        return False
    return old_phase.strip() != new_phase.strip()


def main():
    """
    Hook: Runs after SubagentStop (TDD phase state finalized).

    TDD phases: Plan → Red → Green → Review → Refactor → Validate
    """
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        payload = {}

    cwd = payload.get("cwd") or os.getcwd()
    state_path = payload.get("state_path")

    if not state_path:
        sys.exit(0)

    feature_dir = os.path.dirname(state_path)
    feature_slug = get_feature_slug(state_path)
    cache_scope = f"agent-tdd:{feature_slug}"

    # Read current workflow state
    workflow_state = read_workflow_state(feature_dir)
    current_phase = workflow_state.get("current_phase", "")

    if not current_phase:
        sys.exit(0)

    # Normalize to TDD phase format for caching
    if not current_phase.startswith("TDD:"):
        current_phase = f"TDD:{current_phase.lower()}"

    # Try to read cached phase state
    cached = cache_read_via_mcp("phase_state", cache_scope)
    previous_phase = cached.get("value", {}).get("current_phase") if cached.get("hit") else None

    # Detect phase transition
    phase_changed = is_phase_change(previous_phase, current_phase)

    if phase_changed:
        # TDD STAGE TRANSITION: Write cache + render transition
        sys.stderr.write(f"[ux-hook-tdd] Stage transition: {previous_phase} → {current_phase}\n")

        # Write phase state to cache
        phase_data = {
            "current_phase": current_phase,
            "phase_state": workflow_state.get("phase_state", "Unknown"),
            "workflow_status": workflow_state.get("workflow_status"),
            "last_updated": workflow_state.get("updated_at"),
        }
        cache_write_via_mcp("phase_state", phase_data, cache_scope, ttl_seconds=3600)

        # Render full phase_transition event
        render_phase_transition(
            from_phase=previous_phase or "Start",
            to_phase=current_phase,
            feature_slug=feature_slug,
            phase_state=current_phase,
            summary=f"TDD stage: {current_phase}"
        )

        print(json.dumps({
            "systemMessage": f"UX: TDD {previous_phase or 'Start'} → {current_phase}"
        }))

    else:
        # SAME STAGE: Just update breadcrumb (cheap, ~100 tokens)
        display_phase = (cached.get("value", {}).get("current_phase")
                        if cached.get("hit")
                        else current_phase)

        render_breadcrumb_only(display_phase, feature_slug)

        print(json.dumps({
            "systemMessage": f"UX: TDD breadcrumb update ({display_phase})"
        }))

    sys.exit(0)


if __name__ == "__main__":
    main()
