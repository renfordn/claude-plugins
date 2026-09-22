#!/usr/bin/env python3
"""SubagentStop hook: single entry-point combining the previously separate hooks
(subagent_report.py, high_risk_reviewer.py, ux_render.py) that all fired on every
SubagentStop event. Running one Python process instead of several cuts subprocess startup
overhead the same way post_write_check.py already does for PostToolUse.

Each module's logic still lives in its own file (and is still independently invocable --
each module's main() optionally accepts an already-parsed payload instead of always reading
stdin, so this dispatcher can read stdin once and hand the same payload to each in turn).
Execution order: subagent_report (may write workflow-state.json), high_risk_reviewer,
ux_render (reads workflow-state.json to render the breadcrumb) -- keep report before render.

A fourth module, cache_hook.py, used to sit between subagent_report and high_risk_reviewer;
it was removed in 0.1.50 after its agent-cache-plugin HTTP integration turned out to have
never had a server to talk to (see INTEROP.md -> "agent-cache-plugin").

Each module's systemMessage (if any) is combined into a single systemMessage, separated by
blank lines, since only one JSON object can be emitted per hook invocation.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import subagent_report  # noqa: E402
import high_risk_reviewer  # noqa: E402
import ux_render  # noqa: E402

# Order matters -- see module docstring.
MODULES = (subagent_report, high_risk_reviewer, ux_render)


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
