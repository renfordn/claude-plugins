"""wait_loop_guard: PreToolUse Bash hook denying pgrep/pkill -f patterns that match their own shell."""
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


@pytest.fixture(params=[True, False], ids=["bsd", "linux"])
def platform(request, monkeypatch):
    monkeypatch.setattr(g, "BSD", request.param)
    return request.param


# Wait loops self-match on every platform (on macOS, concurrent loops match each other's shell).
LOOPS = [
    'while pgrep -f "git commit" >/dev/null; do sleep 15; done',
    "until ! pgrep -f 'local_ci.py test'; do sleep 5; done; echo ok",
    "while pgrep -af pytest; do sleep 1; done",
    "while /usr/bin/pgrep -f -- git; do sleep 1; done",
    "while [ $(pgrep -fc 'git commit') -gt 0 ]; do sleep 5; done",
    'while [ -n "$(pgrep -f \'git commit\')" ]; do sleep 5; done',
    "while [ -n \"`pgrep -f git`\" ]; do sleep 5; done",
]


@pytest.mark.parametrize("cmd", LOOPS)
def test_wait_loops_denied_on_every_platform(cmd, platform):
    assert g.self_matching(cmd) is not None


@pytest.mark.parametrize("cmd", LOOPS[:2])
def test_hook_denies_wait_loop(cmd):
    r = run(cmd)
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)["hookSpecificOutput"]
    assert out["permissionDecision"] == "deny"
    assert "foreground" in out["permissionDecisionReason"]


@pytest.mark.parametrize("cmd", [
    "pgrep -u me -f 'git commit' && echo running",
    "pkill -9 -f 'git.*commit'",
    "pkill --full 'git commit'",
])
def test_one_shot_self_match_denied_on_linux_only(cmd, platform):
    assert (g.self_matching(cmd) is None) == platform


@pytest.mark.parametrize("cmd", ["pgrep -af 'git commit'", "pkill -a -f 'vite dev'"])
def test_bsd_ancestors_flag_self_matches(cmd, monkeypatch):
    monkeypatch.setattr(g, "BSD", True)
    assert g.self_matching(cmd) is not None


def test_procps_ignore_ancestors_is_allowed(monkeypatch):
    monkeypatch.setattr(g, "BSD", False)
    assert g.self_matching("pgrep -A -f 'git commit'") is None
    assert g.self_matching("pgrep --ignore-ancestors -f 'git commit'") is None


@pytest.mark.parametrize("cmd", [
    "pgrep git",                                   # no -f: matches process names only
    "pgrep -f '[g]it commit'",                     # bracket trick: pattern text doesn't match itself
    "git commit -m 'pgrep -f is banned'",          # pgrep only inside a quoted argument
    "echo pgrep -f x",                             # pgrep not in command position
    "pgrep -f\necho done",                         # newline ends the pgrep command
    "ps aux | grep -f patterns.txt",
    "python3 -m pytest -q",
    "pgrep -f",                                    # no pattern
    "pgrep -f 'unbalanced",                        # shlex error: fail open
])
def test_other_commands_allowed(cmd, platform):
    assert g.self_matching(cmd) is None


@pytest.mark.parametrize("raw", ["not json", "[]", json.dumps({"tool_input": {}}),
                                 json.dumps({"tool_input": {"command": 5}}),
                                 json.dumps({"tool_input": {"command": "pgrep git"}})])
def test_bad_or_harmless_payload_allowed(raw):
    r = run(None, raw=raw)
    assert r.returncode == 0
    assert r.stdout.strip() == ""


def test_self_matching_returns_tool_and_pattern(platform):
    assert g.self_matching('while pgrep -f "git commit"; do :; done') == ("pgrep", "git commit")
    assert g.self_matching("while pgrep -P 123 -f x; do :; done") == ("pgrep", "x")


@pytest.mark.parametrize("cmd", ["while pgrep -f --older 60 foo; do :; done",
                                 "while pgrep -r R -f foo; do :; done"])
def test_option_values_are_not_the_pattern(cmd, platform):
    assert g.self_matching(cmd) == ("pgrep", "foo")


def test_registered_for_bash_pretooluse():
    with open(os.path.join(os.path.dirname(HOOK), "hooks.json")) as fh:
        pre = json.load(fh)["hooks"]["PreToolUse"]
    assert any(e.get("matcher") == "Bash" and any("wait_loop_guard.py" in h["command"]
                                                   for h in e["hooks"]) for e in pre)


@pytest.mark.parametrize("cmd", [
    "pkill -f vite; until curl -s localhost:5173; do sleep 1; done",   # pkill outside the loop
    'pgrep -fl node; git commit -m "fix while loop"',                  # "while" only in a string
    "while true; do sleep 1; done; pgrep -f node",                     # after the loop's done
])
def test_bsd_one_shot_outside_a_loop_allowed(cmd, monkeypatch):
    monkeypatch.setattr(g, "BSD", True)
    assert g.self_matching(cmd) is None


@pytest.mark.parametrize("cmd", [
    "while timeout 5 pgrep -f 'git commit'; do sleep 5; done",
    "while FOO=1 pgrep -f x; do sleep 1; done",
    "while sudo -n pkill -f x; do sleep 1; done",
    "while sudo -u root pgrep -f x; do sleep 1; done",
    "while env A=1 nice -n 5 pgrep -f x; do sleep 1; done",
    'while [ $(pgrep -f "git( commit)?" | wc -l) -gt 0 ]; do sleep 1; done',
    "until [ -z \"$(echo $(pgrep -f 'git commit'))\" ]; do sleep 1; done",
])
def test_prefixed_and_nested_loops_denied(cmd, platform):
    assert g.self_matching(cmd) is not None


HEREDOC_MSG = ("git commit -F - <<'MSG'\nfix: `pkill -f vite; until curl x; done`\n"
               "while pgrep -f y; do :; done\nMSG\ngit log -1")


def test_heredoc_body_is_data_not_commands(platform):
    assert g.self_matching(HEREDOC_MSG) is None
    assert g.self_matching("cat <<EOF > f.txt\npkill -f z\nEOF") is None


def test_command_after_heredoc_still_scanned(platform):
    assert g.self_matching(HEREDOC_MSG + "\nwhile pgrep -f vite; do sleep 1; done") is not None
