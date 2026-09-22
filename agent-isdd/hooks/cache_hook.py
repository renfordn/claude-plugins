#!/usr/bin/env python3
"""
Agent-ISDD cache hook (SubagentStop) -- currently a documented no-op.

History / the gap
-----------------
This hook was written to push workflow phase state into agent-cache-plugin on every phase
transition (and invalidate it on rollback) by POSTing to ``http://localhost:7771/cache/write``
and ``/cache/invalidate``. agent-cache-plugin has never run an HTTP server on that port or any
other: it has no ``bin`` entry, no listener in ``hooks/``, ``skills/``, or ``commands/``. Every
request failed with a connection error that was swallowed as "graceful degradation", so the
hook has never cached anything.

agent-cache-plugin's real integration surface (see its ``STRUCTURE.md`` -> "Capabilities") is:

- automatic ``PreToolUse``/``PostToolUse`` hooks on the ``Agent`` tool, which cache *Agent tool
  outputs* keyed by agent-type + task-slug + input digest -- not a scoped key/value store, and
  not something a caller can write phase state into;
- two subagents (``agent-cache-orchestrator``, ``cache-validator``) reachable only via the
  ``Agent`` tool from the main thread, not from a hook process;
- CLI commands (``cache-status|cache-clear|cache-config``) with no store/retrieve verb;
- an in-process JS API usable only by Node callers.

None of those is callable from a Python hook, so explicit phase-state write/invalidate is not
possible today. Nothing is lost in practice: ``workflow-state.json`` is the source of truth for
phase state and every consumer already reads it directly. If agent-cache-plugin ever grows a
transport a hook process can reach (local socket, CLI ``store``/``retrieve``, ...), this module
is the place to wire it; keep it in ``subagent_dispatch.MODULES`` before ``ux_render`` so any
future invalidate-on-rollback still runs before rendering.

``main()`` keeps the dispatcher-compatible signature (optional pre-parsed payload, returns the
systemMessage text or ``None``) and returns ``None`` unconditionally.
"""
import json
import sys


def main(payload=None):
    """No-op: see module docstring. Consumes stdin when run standalone so the hook contract
    (read one JSON payload, exit 0) is honoured."""
    if payload is None:
        try:
            json.load(sys.stdin)
        except (json.JSONDecodeError, ValueError):
            pass
    return None


if __name__ == "__main__":
    _msg = main()
    if _msg:
        print(json.dumps({"systemMessage": _msg}))
    sys.exit(0)
