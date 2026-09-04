#!/usr/bin/env python3
"""
Agent-ISDD cache integration hook.

Integrates with agent-cache plugin to cache phase state and invalidate on rollback.
Called from SubagentStop hook after phase state changes.

Uses agent-cache-plugin's MCP interface via HTTP calls. Falls back gracefully
if agent-cache-plugin is unavailable.
"""
import json
import os
import sys
import re
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from sdd_state import active_state_file
except ImportError:
    def active_state_file(cwd):
        return None


def get_feature_slug(state_path):
    """Extract feature slug from sdd-memory path."""
    match = re.search(r'/sdd-memory/([^/]+)/', state_path)
    return match.group(1) if match else os.path.basename(os.path.dirname(state_path))


def read_workflow_state(feature_dir):
    """Read workflow-state.json from feature directory."""
    workflow_json = os.path.join(feature_dir, "workflow-state.json")
    try:
        with open(workflow_json, 'r') as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def cache_write_via_mcp(key, value, scope, ttl_seconds=3600):
    """
    Write to agent-cache plugin via MCP HTTP interface.

    Stores phase state in cache with TTL. Gracefully degrades if agent-cache-plugin
    is unavailable (continues without caching).

    Args:
        key: Cache key (e.g., "phase_state")
        value: JSON-serializable value to cache
        scope: Cache scope (e.g., "agent-isdd:feature-slug")
        ttl_seconds: Time-to-live in seconds

    Returns:
        bool: True if write succeeded or was skipped gracefully
    """
    try:
        import urllib.request
        import urllib.error

        # Try to write to agent-cache-plugin MCP server on standard localhost port
        # (if running). This is a graceful attempt; if unavailable, we continue.
        try:
            cache_entry = {
                "prompt": f"Phase state: {scope}",
                "output": value,
                "metadata": {
                    "cacheKey": key,
                    "scope": scope,
                    "ttl": ttl_seconds * 1000,  # Convert to milliseconds
                    "type": "phase_state"
                }
            }

            # Attempt to send to agent-cache-plugin's MPC interface
            # (assumes it's running on localhost:9000 or similar)
            # If not available, the exception is caught below
            req = urllib.request.Request(
                "http://localhost:7771/cache/write",
                data=json.dumps(cache_entry).encode('utf-8'),
                headers={"Content-Type": "application/json"},
                method="POST"
            )

            with urllib.request.urlopen(req, timeout=2) as response:
                if response.status == 200:
                    sys.stderr.write(f"[cache-hook] cache_write succeeded: {scope}\n")
                    return True

        except (urllib.error.URLError, TimeoutError, OSError):
            # agent-cache-plugin MCP server not running or unreachable
            # This is expected in many environments; graceful degradation
            sys.stderr.write(f"[cache-hook] agent-cache-plugin unavailable; cache_write skipped\n")
            return True  # Don't fail the hook; cache is optional

    except Exception as e:
        # Catch all; never crash the hook
        sys.stderr.write(f"[cache-hook] cache_write error (graceful): {str(e)}\n")
        return True


def cache_invalidate_via_mcp(scope):
    """
    Invalidate cache entries in a scope via agent-cache plugin MPC interface.

    Removes all entries under the given scope when rollback/rewind occurs.
    Gracefully degrades if agent-cache-plugin is unavailable.

    Args:
        scope: Cache scope to invalidate (e.g., "agent-isdd:feature-slug")

    Returns:
        bool: True if invalidate succeeded or was skipped gracefully
    """
    try:
        import urllib.request
        import urllib.error

        try:
            req = urllib.request.Request(
                "http://localhost:7771/cache/invalidate",
                data=json.dumps({"scope": scope}).encode('utf-8'),
                headers={"Content-Type": "application/json"},
                method="POST"
            )

            with urllib.request.urlopen(req, timeout=2) as response:
                if response.status == 200:
                    sys.stderr.write(f"[cache-hook] cache_invalidate succeeded: {scope}\n")
                    return True

        except (urllib.error.URLError, TimeoutError, OSError):
            # agent-cache-plugin MCP server not running or unreachable
            sys.stderr.write(f"[cache-hook] agent-cache-plugin unavailable; cache_invalidate skipped\n")
            return True  # Don't fail the hook; cache is optional

    except Exception as e:
        # Catch all; never crash the hook
        sys.stderr.write(f"[cache-hook] cache_invalidate error (graceful): {str(e)}\n")
        return True


def main():
    """
    Hook: Runs after SubagentStop (phase state finalized).

    Actions:
    1. Detect phase transitions (Requirements → Design → Tasks → Implementation)
    2. On phase change: cache_write the phase_state
    3. On rollback/rewind: cache_invalidate the scope
    """
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        payload = {}

    cwd = payload.get("cwd") or os.getcwd()
    state_path = active_state_file(cwd)

    if not state_path:
        sys.exit(0)

    feature_dir = os.path.dirname(state_path)
    feature_slug = get_feature_slug(state_path)
    cache_scope = f"agent-isdd:{feature_slug}"

    # Read workflow state
    workflow_state = read_workflow_state(feature_dir)

    # Check for rollback/rewind and invalidate cache
    if workflow_state.get("rollback_pending"):
        cache_invalidate_via_mcp(cache_scope)
        sys.stderr.write(f"[cache-hook] Cleared cache for rollback: {cache_scope}\n")
        sys.exit(0)

    # On successful phase transition, cache the state
    current_phase = workflow_state.get("current_phase")
    if current_phase:
        phase_data = {
            "current_phase": current_phase,
            "phase_state": workflow_state.get("phase_state", "Unknown"),
            "workflow_status": workflow_state.get("workflow_status"),
            "last_updated": workflow_state.get("updated_at"),
        }

        cache_write_via_mcp("phase_state", phase_data, cache_scope, ttl_seconds=3600)

        print(json.dumps({
            "systemMessage": f"[Cache] Phase state: {current_phase}"
        }))

    sys.exit(0)


if __name__ == "__main__":
    main()
