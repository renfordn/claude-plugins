#!/usr/bin/env python3
"""SubagentStop hook: single entry-point combining the four previously separate hooks
(subagent_report.py, cache_hook.py, high_risk_reviewer.py, ux_render.py) that all fired on
every SubagentStop event. Running one Python process instead of four cuts subprocess
startup overhead the same way post_write_check.py already does for PostToolUse.

Behaviour is unchanged from the four originals: each module's logic still lives in its own
file (and is still independently invocable -- hooks.json's SubagentStop entry is the only
thing that changed, plus each module's main() now optionally accepts an already-parsed
payload instead of always reading stdin, so this dispatcher can read stdin once and hand
the same payload to each in turn). Execution order is preserved exactly as it was in
hooks.json: subagent_report, cache_hook, high_risk_reviewer, ux_render. This order is not
arbitrary -- cache_hook.py (currently a documented no-op, see its docstring) is the slot for
a future invalidate-on-rollback that must read workflow-state.json's rollback_pending field
after subagent_report.py writes it and before ux_render.py renders; keep the order.

Each module's systemMessage (if any) is combined into a single systemMessage, separated by
blank lines, since only one JSON object can be emitted per hook invocation.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import subagent_report  # noqa: E402
import cache_hook  # noqa: E402
import high_risk_reviewer  # noqa: E402
import ux_render  # noqa: E402

# Order matters -- see module docstring.
MODULES = (subagent_report, cache_hook, high_risk_reviewer, ux_render)


def main():
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        payload = {}

    messages = []
    for module in MODULES:
        try:
            msg = module.main(payload)
        except Exception as exc:  # noqa: BLE001 -- one module's failure must not block the rest
            sys.stderr.write(f"[subagent_dispatch] {module.__name__} failed: {exc}\n")
            msg = None
        if msg:
            messages.append(msg)

    if messages:
        print(json.dumps({"systemMessage": "\n\n".join(messages)}))
    sys.exit(0)


if __name__ == "__main__":
    main()
