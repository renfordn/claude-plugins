"""wait_loop_guard: PreToolUse Bash hook denying pgrep/pkill -f patterns that match the command."""
import json
import os
import subprocess
import sys

import pytest

HOOK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "hooks", "wait_loop_guard.py")
sys.path.insert(0, os.path.dirname(HOOK))
import wait_loop_guard as g  # noqa: E402


def run(command, raw=None):
    stdin = raw if raw is not None else json.dumps({"tool_name": "Bash",
                                                     "tool_input": {"command": command}})
    return subprocess.run([sys.executable, HOOK], input=stdin, capture_output=True, text=True,
                          timeout=10)


@pytest.mark.parametrize("cmd", [
    'while pgrep -f "git commit" >/dev/null; do sleep 15; done',
    "until ! pgrep -f 'local_ci.py test'; do sleep 5; done; echo ok",
    "while pgrep -af pytest; do sleep 1; done",
    "pgrep -u me -f 'git commit' && echo running",
    "pkill -9 -f 'git.*commit'",
    "pkill --full 'git commit'",
    "while /usr/bin/pgrep -f -- git; do sleep 1; done",
])
def test_self_matching_is_denied(cmd):
    r = run(cmd)
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)["hookSpecificOutput"]
    assert out["permissionDecision"] == "deny"
    assert "foreground" in out["permissionDecisionReason"]


@pytest.mark.parametrize("cmd", [
    "pgrep git",                                   # no -f: matches process names only
    "pgrep -f '[g]it commit'",                     # bracket trick: pattern text doesn't match itself
    "git commit -m 'pgrep -f is banned'",          # pgrep only inside a quoted argument
    "ps aux | grep -f patterns.txt",
    "python3 -m pytest -q",
    "pgrep -f",                                    # no pattern
    "pgrep -f 'unbalanced",                        # shlex error: fail open
])
def test_other_commands_allowed(cmd):
    r = run(cmd)
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == ""


@pytest.mark.parametrize("raw", ["not json", "[]", json.dumps({"tool_input": {}}),
                                 json.dumps({"tool_input": {"command": 5}})])
def test_bad_payload_fails_open(raw):
    r = run(None, raw=raw)
    assert r.returncode == 0
    assert r.stdout.strip() == ""


def test_self_matching_returns_tool_and_pattern():
    assert g.self_matching('while pgrep -f "git commit"; do :; done') == ("pgrep", "git commit")
    assert g.self_matching("pgrep -P 123 -f x") == ("pgrep", "x")  # -P's value is not the pattern


def test_registered_for_bash_pretooluse():
    with open(os.path.join(os.path.dirname(HOOK), "hooks.json")) as fh:
        pre = json.load(fh)["hooks"]["PreToolUse"]
    assert any(e.get("matcher") == "Bash" and any("wait_loop_guard.py" in h["command"]
                                                   for h in e["hooks"]) for e in pre)
