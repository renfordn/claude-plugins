"""Tests for hooks/nelly_delete_guard.py -- PreToolUse Bash: deny hard deletes under the store (R0d).

Drives the hook as the harness does: JSON payload on stdin, assert on stdout + exit code.
"""
import json
import os
import subprocess
import sys

import pytest

HOOK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nelly_delete_guard.py")
DATA = os.environ["CLAUDE_PLUGIN_DATA"]
STORE = os.path.join(DATA, "agent-nelly-memory")
OUTSIDE = os.path.join(os.path.dirname(DATA), "elsewhere")
ANC = os.path.dirname(DATA)
_DN = os.path.basename(DATA)  # data dir name differs when another plugin's conftest set it first


def run_hook(command, cwd=None, env=None, raw=None):
    full_env = dict(os.environ)
    if env:
        full_env.update(env)
    payload = raw if raw is not None else json.dumps(
        {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": cwd or OUTSIDE})
    return subprocess.run([sys.executable, HOOK], input=payload, capture_output=True,
                          text=True, env=full_env)


def decision(proc):
    assert proc.returncode == 0, proc.stderr
    if not proc.stdout.strip():
        return None
    return json.loads(proc.stdout)["hookSpecificOutput"]["permissionDecision"]


DENY = [
    (f"rm {STORE}/entries/x.md", None),
    (f"rm -rf {STORE}", None),
    (f"cd {STORE} && rm x.md", None),
    ("rm x.md", STORE),
    (f"cd {STORE}/entries; rm -f ../MEMORY.md", None),
    (f"rm -rf {os.path.dirname(STORE)}", None),                       # ancestor
    (f"rm -rf {os.path.dirname(os.path.dirname(STORE))}/", None),     # ancestor, trailing slash
    (f"find {STORE} -name '*.md' -delete", None),
    (f"find {STORE} -type f -exec rm {{}} \\;", None),
    (f"rm {STORE}/entries/*.md", None),                               # glob inside
    (f"rm {STORE}/ent*/x.md", None),
    (f"rm {DATA}/agent-nelly-m*", None),                              # glob matching the store
    (f"unlink {STORE}/a.md", None),
    (f"rmdir {STORE}/entries", None),
    (f"shred -u {STORE}/a.md", None),
    (f"git rm {STORE}/a.md", None),
    (f"git -C {STORE} rm a.md", None),
    (f"FOO=1 rm {STORE}/a.md", None),
    (f"echo hi && rm {STORE}/a.md", None),
    (f"true | rm {STORE}/a.md", None),
    (f"(cd {STORE} && rm a.md)", None),
    (f"bash -c 'rm {STORE}/a.md'", None),
    (f"rm -- {STORE}/a.md", None),
    (f"echo ok\nrm {STORE}/a.md", None),
    # F1: comments must not swallow the rest of the line or the following lines
    (f"cd {STORE} # go\nrm -rf entries", None),
    (f"echo a#b\nrm -rf {STORE}/entries", None),
    (f"curl http://x/#f; rm -rf {STORE}", None),
    # F7: wrappers and substitutions
    (f"bash -lc 'rm -rf {STORE}'", None),
    (f"env rm -rf {STORE}", None),
    (f"env -i FOO=1 rm -rf {STORE}", None),
    (f"echo $(rm -rf {STORE})", None),
    (f"timeout 5 rm -rf {STORE}", None),
    (f"nice -n 5 rm -rf {STORE}", None),
    (f"nohup rm -rf {STORE}", None),
    # F9
    (f"sudo rm -rf {STORE}", None),
    (f"/bin/rm {STORE}/a.md", None),
    (f"\\rm {STORE}/a.md", None),
    (f"command rm {STORE}/a.md", None),
    # F4: find from an ancestor without a name filter, or filtering on the store's name
    (f"find {os.path.dirname(DATA)} -delete", None),
    (f"find {os.path.dirname(DATA)} -exec rm {{}} \\;", None),
    (f"find {os.path.dirname(DATA)} -path '*agent-nelly-memory*' -delete", None),
    # name filters that can match store file names, from an ancestor
    (f"find {os.path.dirname(DATA)} -name '*.md' -delete", None),
    (f"find {os.path.dirname(DATA)} -iname '*.MD' -delete", None),
    (f"find {os.path.dirname(DATA)} -name '*' -delete", None),
    (f"find {os.path.dirname(DATA)} -name 'MEMORY*' -delete", None),
    (f"find {os.path.dirname(DATA)} -name '*.json' -exec rm {{}} \\;", None),
    (f"find {os.path.dirname(DATA)} -path '*/agent-nelly-*/*' -delete", None),
    # $(...) sees the cd context at the point it appears; a `)` closing it does not pop the stack
    (f"cd {STORE} && echo $(rm x.md)", None),
    (f"cd {STORE} && echo $(cd entries && rm x.md)", None),
    ("( cd /tmp && echo $(ls) ); rm -rf build", STORE),
    # F11: negated / alternative filters widen the delete
    (f"find {STORE} ! -name '*.tmp' -delete", None),
    (f"find {ANC} ! -name '*.pyc' -delete", None),
    (f"find {ANC} -not -name .DS_Store -delete", None),
    (f"find {ANC} -name node_modules -prune -o -name '*.pyc' -delete", None),
    # F13: -path / -regex samples cover the slug level; regexes are translated from emacs style
    (f"find {ANC} -regex '.*\\.json' -delete", None),
    (f"find {ANC} -path '*.json' -delete", None),
    (f"find {ANC} -path '*/archive/*' -delete", None),
    (f"find {ANC} -regex '.*\\(md\\|json\\)' -delete", None),
    (f"find {ANC} -regex '[' -delete", None),                         # uncompilable: deny
    # F6: a subshell closes at its `)` token even when more tokens follow
    ("(cd /tmp && ls) > /dev/null; rm -rf build", STORE),
    ("(cd /tmp && ls) 2>&1 | tail -1; rm -rf build", STORE),
    # F14: a quoted `)` does not confuse the substitution scan
    (f'echo "a)" $(cd {STORE} && rm x.md)', None),
    # -c scan skips -o <opt> pairs
    (f"bash -o pipefail -c 'rm -rf {STORE}'", None),
    (f'echo "$(rm -rf {STORE})"', None),                              # double quotes still run
    (f"cat <<EOF\n$(rm -rf {STORE})\nEOF", None),                     # unquoted heredoc body runs
    # F15: shell keywords do not hide the command
    (f"if [ -d {STORE} ]; then rm -rf {STORE}/entries; fi", None),
    (f"{{ rm -rf {STORE}; }}", None),
    (f"while true; do rm -rf {STORE}; done", None),
    (f"! rm -rf {STORE}", None),
    (f"for f in a; do rm -rf {STORE}; done", None),
    (f"case x in x) rm -rf {STORE};; esac", None),
    # F16: `<<<` is a here-string, not a heredoc that swallows the following lines
    (f'grep -c x <<< "$var"\nrm -rf {STORE}', None),
    (f"cat <<< hi\nrm -rf {STORE}", None),
    # F17: $'...' escapes; process substitution runs its content
    (f"echo $'it\\'s'; rm -rf {STORE}", None),
    (f"cat <(rm -rf {STORE})", None),
]

ALLOW = [
    ('grep <<< "$var"; rm -rf build', None),                          # F16
    ("diff <(sort a) <(sort b); rm -rf build", None),                 # F17
    (f"rm {STORE}/entries/x.md.tmp", None),
    (f"rm {STORE}/.nelly.lock", None),
    (f"rm {STORE}/.index.lock", None),
    (f"rm {STORE}/entries/*.tmp", None),
    (f"mv {STORE}/entries/x.md {STORE}/archive/x.md", None),
    (f"git mv {STORE}/entries/x.md {STORE}/archive/x.md", None),
    (f"cd {STORE} && mv x.md archive/", None),
    (f"rm {OUTSIDE}/x.md", None),
    ("rm x.md", OUTSIDE),
    (f"rm -rf {DATA}-other/x", None),                                 # sibling prefix, not ancestor
    (f"rm {DATA}/*.log", None),                                       # glob cannot reach the store
    (f"echo \"rm {STORE}/a.md\"", None),
    (f"echo 'find {STORE} -delete'", None),
    (f"find {STORE} -name '*.md'", None),
    (f"find {OUTSIDE} -delete", None),
    (f"cat {STORE}/MEMORY.md", None),
    (f"git rm {OUTSIDE}/a.md", None),
    (f"git rm --cached {STORE}/a.md", None),                          # F3: only untracks
    (f"(cd {STORE} && ls); rm -rf build", OUTSIDE),                   # F6: subshell cd does not leak
    (f"find {STORE} -name '*.tmp' -delete", None),                    # F4
    (f"find {os.path.dirname(DATA)} -name .DS_Store -delete", None),
    ("find . -name '*.pyc' -delete", os.path.dirname(DATA)),
    (f"find {os.path.dirname(DATA)} -path '*/node_modules/*' -delete", None),
    (f"( cd {STORE} && echo $(ls) ); rm -rf build", OUTSIDE),
    (f"cd /tmp && echo $(rm x.md)", STORE),
    (f"(cd {STORE} && ls) > /dev/null; rm -rf build", OUTSIDE),       # F6
    (f"(cd {STORE} && ls) 2>&1 | tail -1; rm -rf build", OUTSIDE),
    # F12: literal text is not scanned for substitutions
    (f"echo 'never run $(rm -rf {STORE})'", None),
    (f"git commit -m \"$(cat <<'EOF'\nfix: mention rm -rf {STORE}\nEOF\n)\"", None),
    (f"cat <<'EOF'\n$(rm -rf {STORE})\nEOF", None),
]


@pytest.mark.parametrize("command,cwd", DENY)
def test_denies_hard_delete_under_store(command, cwd):
    proc = run_hook(command, cwd=cwd)
    assert decision(proc) == "deny", command
    reason = json.loads(proc.stdout)["hookSpecificOutput"]["permissionDecisionReason"]
    assert "archived" in reason and "never deleted" in reason
    assert "archive/" in reason and "/nelly-memory prune" in reason


@pytest.mark.parametrize("command,cwd", ALLOW)
def test_allows_everything_else(command, cwd):
    proc = run_hook(command, cwd=cwd)
    assert decision(proc) is None, (command, proc.stdout)


def test_home_tilde_expansion(tmp_path):
    # ~ expands from HOME: an unrelated HOME is outside the store, the store's grandparent is
    # an ancestor of it.
    assert decision(run_hook("rm ~/x.md", env={"HOME": str(tmp_path)})) is None
    gp = os.path.dirname(DATA)
    cmd = f"rm -rf ~/{os.path.basename(DATA)}"
    assert decision(run_hook(cmd, env={"HOME": gp})) == "deny"


def test_nelly_gate_off_disables():
    assert decision(run_hook(f"rm {STORE}/a.md", env={"NELLY_GATE": "off"})) is None


@pytest.mark.parametrize("raw", ["not json", "", "[]", '{"tool_input": null}',
                                 '{"tool_input": {"command": 5}}'])
def test_bad_payload_fails_open(raw):
    assert decision(run_hook(None, raw=raw)) is None


ENV_DENY = [
    # F10: $HOME / ${HOME} with HOME an ancestor of the store
    (f"rm -rf $HOME/{_DN}/agent-nelly-memory/x.md", None, {"HOME": os.path.dirname(DATA)}),
    (f"rm ${{HOME}}/{_DN}/agent-nelly-memory/x.md", None, {"HOME": os.path.dirname(DATA)}),
    # F9: bare cd goes home
    (f"cd && rm -rf {_DN}/agent-nelly-memory", None, {"HOME": os.path.dirname(DATA)}),
]


@pytest.mark.parametrize("command,cwd,env", ENV_DENY)
def test_denies_with_home_env(command, cwd, env):
    assert decision(run_hook(command, cwd=cwd, env=env)) == "deny", command


def test_shared_root_mode(tmp_path):
    shared = str(tmp_path / "shared")
    env = {"CLAUDE_PLUGIN_OPTION_SHARED_MEMORY_ROOT": shared}
    assert decision(run_hook(f"rm {shared}/agent-nelly-memory/x.md", env=env)) == "deny"
    assert decision(run_hook(f"rm -rf {shared}", env=env)) == "deny"
    assert decision(run_hook(f"rm -rf {shared}/agent-isdd-memory/x", env=env)) is None


def test_symlink_to_store(tmp_path):
    link = tmp_path / "mylink"
    os.symlink(STORE, link)
    cwd = str(tmp_path)
    assert decision(run_hook("rm mylink", cwd=cwd)) is None          # removes the link only
    assert decision(run_hook("rm -rf mylink/", cwd=cwd)) == "deny"
    assert decision(run_hook("rm mylink/x.md", cwd=cwd)) == "deny"


def test_fast_path_does_not_import_store_module():
    code = (
        "import io, json, sys\n"
        f"sys.path.insert(0, {os.path.dirname(HOOK)!r})\n"
        "import nelly_delete_guard as g\n"
        "sys.stdin = io.StringIO(json.dumps({'tool_input': {'command': 'git status'}}))\n"
        "assert g.main() == 0\n"
        "print('nelly_memory' in sys.modules)\n"
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert out.stdout.strip() == "False", out.stderr


def test_hook_compiles_without_warnings():
    # invalid escape sequences (e.g. in a non-raw docstring) are SyntaxWarnings
    code = "import sys; p = sys.argv[1]; compile(open(p).read(), p, 'exec')"
    out = subprocess.run([sys.executable, "-W", "error", "-c", code, HOOK],
                         capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
