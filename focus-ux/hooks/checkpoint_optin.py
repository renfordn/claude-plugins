#!/usr/bin/env python3
"""UserPromptSubmit hook: opt in a session to checkpoint pushes (R7), reset the dedup `last`
marker on every new prompt (R8's resolution rule), and inject the standing rule that makes a
Dispatch child push before AskUserQuestion (R1). Fails open on every path -- always exits 0."""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from focus_ux_state import load_state, save_state  # noqa: E402

MARKER = "[checkpoint-push]"

# Quoted marker text (an agent report or a pasted doc mentioning `[checkpoint-push]`) must not opt
# a session in, so the marker only counts outside fenced blocks (an unterminated fence runs to the
# end) and inline code spans.
_CODE_RE = re.compile(r"```.*?(?:```|\Z)|`[^`\n]*`", re.DOTALL)

R1_RULE = (
    "focus-ux checkpoint-push is on for this session. Before calling AskUserQuestion, or "
    "before asking the user an explicit decision question in plain text, send exactly one "
    'PushNotification (load it via ToolSearch if needed) formatted as '
    '"<title> · input · <question gist>" (≤120 chars), then continue normally.'
)


def _env_flag():
    return os.environ.get("FOCUS_UX_CHECKPOINT_PUSH")


def main():
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return
    if not isinstance(payload, dict):
        return

    session_id = payload.get("session_id")
    prompt = payload.get("prompt")
    if not isinstance(prompt, str):
        prompt = ""

    env = dict(os.environ)
    flag = _env_flag()

    if flag == "0":
        return  # explicit off wins over everything (R7)

    has_marker = MARKER in _CODE_RE.sub("", prompt)
    if not has_marker and flag != "1":
        # Not opted in by this prompt. Still clear `last` if an earlier prompt opted in.
        state = load_state(session_id, env)
        if state["opted_in"] and (state["last"] is not None or state["pending"] is not None):
            state["last"] = None
            state["pending"] = None  # F2: a new prompt starts a fresh cycle; drop a stale nonce
            save_state(session_id, state, env)
        return

    state = load_state(session_id, env)
    state["opted_in"] = True
    state["last"] = None
    state["pending"] = None  # F2: same reset on the opted-in path
    # `rule_injected` is tracked separately from `opted_in` (review F1/New-F3): opted_in can be
    # true on every single call along the persistent-env-var path (FOCUS_UX_CHECKPOINT_PUSH=1
    # never goes away), so it can't be what gates the injection -- otherwise the rule would be
    # reprinted on every prompt instead of exactly once per session.
    should_inject = not state["rule_injected"]
    if should_inject:
        state["rule_injected"] = True
    save_state(session_id, state, env)

    if should_inject:
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "additionalContext": R1_RULE,
            }
        }))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
