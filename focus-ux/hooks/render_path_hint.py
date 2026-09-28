#!/usr/bin/env python3
"""SessionStart hook: tell the model where focus-ux's inline-render script lives.

The Focus output style can't name the script with ${CLAUDE_PLUGIN_ROOT}: observed in a live
session, that text reached the model unexpanded, and the Bash tool's shell has no
CLAUDE_PLUGIN_ROOT either, so the model can't resolve the path itself. This hook computes the
absolute path from its own location and injects it as one line of context on each SessionStart
(startup, resume, clear and compact alike). Fails open: if the script isn't there it prints
nothing, and every path exits 0.
"""
import json
import os
import sys


def main():
    plugin_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    script = os.path.join(plugin_root, "scripts", "render_inline.py")
    if not os.path.isfile(script):
        return
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": (
                f'focus-ux render script: python3 "{script}" '
                "<table|progress|timeline|flow> - (JSON on stdin)"
            ),
        }
    }))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
