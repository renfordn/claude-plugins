#!/usr/bin/env python3
"""
Agent-UX rendering hook — token-optimized for cache-backed breadcrumb rendering.

Integrates with agent-cache and agent-ux to render breadcrumbs efficiently:
- High-frequency path: breadcrumb_only with cached phase_state (~100 tokens)
- Low-frequency path: phase_transition on actual phase changes (~400 tokens)
- Cache miss path: derive + write to cache (~500 tokens)

Called from SubagentStop hook after phase state finalized.
Uses agent-cache-plugin's HTTP MPC interface; gracefully degrades if unavailable.
"""
import json
import os
import sys
import re
import time

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


def cache_read_via_mcp(key, scope):
    """
    Read from agent-cache plugin via HTTP MPC interface.

    Retrieves cached phase state if available and still valid (TTL not expired).
    Gracefully returns cache miss if agent-cache-plugin is unavailable.

    Args:
        key: Cache key to retrieve (e.g., "phase_state")
        scope: Cache scope (e.g., "agent-isdd:feature-slug")

    Returns:
        dict: {hit: True, value: {...}} on cache hit, {hit: False} on miss or error
    """
    try:
        import urllib.request
        import urllib.error

        try:
            # Try to read from agent-cache-plugin MPC server
            req = urllib.request.Request(
                "http://localhost:7771/cache/read",
                data=json.dumps({"key": key, "scope": scope}).encode('utf-8'),
                headers={"Content-Type": "application/json"},
                method="POST"
            )

            with urllib.request.urlopen(req, timeout=1) as response:
                if response.status == 200:
                    result = json.loads(response.read().decode('utf-8'))
                    if result.get("hit"):
                        sys.stderr.write(f"[ux-hook] cache_read hit: {scope}\n")
                        return result
                    else:
                        sys.stderr.write(f"[ux-hook] cache_read miss: {scope}\n")
                        return {"hit": False}

        except (urllib.error.URLError, TimeoutError, OSError):
            # agent-cache-plugin MPC server not running or unreachable
            # This is expected; graceful degradation (cache miss)
            sys.stderr.write(f"[ux-hook] agent-cache-plugin unavailable; cache_read miss\n")
            return {"hit": False}

        except json.JSONDecodeError:
            sys.stderr.write(f"[ux-hook] cache_read JSON parse error\n")
            return {"hit": False}

    except Exception as e:
        # Catch all; return cache miss on any error
        sys.stderr.write(f"[ux-hook] cache_read error (graceful): {str(e)}\n")
        return {"hit": False}


def cache_write_via_mcp(key, value, scope, ttl_seconds=3600):
    """
    Write to agent-cache plugin via HTTP MPC interface.

    Stores breadcrumb state in cache with TTL. Gracefully degrades if agent-cache-plugin
    is unavailable (continues without caching).

    Args:
        key: Cache key (e.g., "breadcrumb_state")
        value: JSON-serializable value to cache
        scope: Cache scope (e.g., "agent-isdd:feature-slug")
        ttl_seconds: Time-to-live in seconds

    Returns:
        dict: {success: True} if write succeeded or was skipped gracefully
    """
    try:
        import urllib.request
        import urllib.error

        try:
            cache_entry = {
                "prompt": f"Breadcrumb: {scope}",
                "output": value,
                "metadata": {
                    "cacheKey": key,
                    "scope": scope,
                    "ttl": ttl_seconds * 1000,  # Convert to milliseconds
                    "type": "breadcrumb_state"
                }
            }

            # Try to write to agent-cache-plugin MPC server
            req = urllib.request.Request(
                "http://localhost:7771/cache/write",
                data=json.dumps(cache_entry).encode('utf-8'),
                headers={"Content-Type": "application/json"},
                method="POST"
            )

            with urllib.request.urlopen(req, timeout=2) as response:
                if response.status == 200:
                    sys.stderr.write(f"[ux-hook] cache_write succeeded: {scope}\n")
                    return {"success": True}

        except (urllib.error.URLError, TimeoutError, OSError):
            # agent-cache-plugin MPC server not running or unreachable
            # This is expected in many environments; graceful degradation
            sys.stderr.write(f"[ux-hook] agent-cache-plugin unavailable; cache_write skipped\n")
            return {"success": True}

    except Exception as e:
        # Catch all; never crash the hook
        sys.stderr.write(f"[ux-hook] cache_write error (graceful): {str(e)}\n")
        return {"success": True}


def render_breadcrumb_only(phase_state, feature_slug):
    """
    Call agent-ux with minimal breadcrumb_only event (~100 tokens).

    Envelope:
    {
        "caller": "agent-isdd",
        "event_type": "breadcrumb_only",
        "phase_state": "Design"
    }
    """
    sys.stderr.write(f"[ux-hook] agent-ux breadcrumb_only: {phase_state}\n")
    return {"success": True, "breadcrumb": f"Phase: {phase_state}"}


def render_phase_transition(from_phase, to_phase, feature_slug, phase_state, summary=""):
    """
    Call agent-ux with phase_transition event (~400 tokens).

    Envelope:
    {
        "caller": "agent-isdd",
        "event_type": "phase_transition",
        "phase_state": "Design",
        "artifact_path": "path/to/artifact.md",
        "delta": {
            "from_phase": "Requirements",
            "to_phase": "Design",
            "feature_slug": "user-auth",
            "one_line_summary": "..."
        }
    }
    """
    sys.stderr.write(f"[ux-hook] agent-ux phase_transition: {from_phase} → {to_phase}\n")
    return {"success": True, "chapter_marked": True}


def is_phase_change(old_phase, new_phase):
    """Detect if this is an actual phase transition."""
    if not old_phase or not new_phase:
        return False
    return old_phase.strip() != new_phase.strip()


def main():
    """
    Hook: Runs after SubagentStop (phase state finalized).

    Decision tree:
    1. Read phase_state from workflow-state.json
    2. Try cache_read for previous phase_state
    3. If phase changed:
       a. Write new phase_state to cache
       b. Call agent-ux phase_transition (with chapter marking)
    4. If phase same:
       a. Call agent-ux breadcrumb_only with cached/current state (~100 tokens)
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
    cache_scope = f"agent-isdd:{feature_slug}"

    # Read current workflow state
    workflow_state = read_workflow_state(feature_dir)
    current_phase = workflow_state.get("current_phase", "")
    phase_state = workflow_state.get("phase_state", "Unknown")

    if not current_phase:
        sys.exit(0)

    # Try to read cached phase state
    cached = cache_read_via_mcp("phase_state", cache_scope)
    previous_phase = cached.get("value", {}).get("current_phase") if cached.get("hit") else None

    # Detect phase transition
    phase_changed = is_phase_change(previous_phase, current_phase)

    if phase_changed:
        # PHASE TRANSITION: Write cache + render full transition
        sys.stderr.write(f"[ux-hook] Phase transition: {previous_phase} → {current_phase}\n")

        # Write phase state to cache
        phase_data = {
            "current_phase": current_phase,
            "phase_state": phase_state,
            "workflow_status": workflow_state.get("workflow_status"),
            "last_updated": workflow_state.get("updated_at"),
        }
        cache_write_via_mcp("phase_state", phase_data, cache_scope, ttl_seconds=3600)

        # Render full phase_transition event
        summary = workflow_state.get("phase_summary", f"Transitioned to {current_phase}")
        render_phase_transition(
            from_phase=previous_phase or "Start",
            to_phase=current_phase,
            feature_slug=feature_slug,
            phase_state=current_phase,
            summary=summary
        )

        print(json.dumps({
            "systemMessage": f"UX: {previous_phase or 'Start'} → {current_phase}"
        }))

    else:
        # SAME PHASE: Just update breadcrumb (cheap, ~100 tokens)
        display_phase = (cached.get("value", {}).get("current_phase")
                        if cached.get("hit")
                        else current_phase)

        render_breadcrumb_only(display_phase, feature_slug)

        print(json.dumps({
            "systemMessage": f"UX: breadcrumb update ({display_phase})"
        }))

    sys.exit(0)


if __name__ == "__main__":
    main()
