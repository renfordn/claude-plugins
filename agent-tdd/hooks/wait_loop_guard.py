#!/usr/bin/env python3
"""PreToolUse Bash: deny `pgrep -f` / `pkill -f` whose pattern matches the command itself.

`pgrep -f` matches full command lines and skips only its own process, not the shell running it.
The shell's command line is the Bash tool's command, which contains the pattern, so
`while pgrep -f "git commit"; do sleep 15; done` never exits (and `pkill -f` kills its own
shell). An agent-TDD run sat idle ~12 hours on such a loop. Fails open on any error."""
import json
import os
import re
import shlex
import sys

TOOLS = ("pgrep", "pkill")
# Options that take a value (procps and BSD); the value is not the pattern.
VALUE_OPTS = set("uUgGPstFdc")
SEPARATORS = {";", "&&", "||", "|", "&", "(", ")", "\n"}


def _tokens(command):
    lex = shlex.shlex(command, posix=True, punctuation_chars=";&|()")
    lex.whitespace_split = True
    lex.commenters = ""
    return list(lex)


def _full_and_pattern(args):
    """(uses -f/--full, first pattern) from the args after pgrep/pkill."""
    full, i = False, 0
    while i < len(args):
        a = args[i]
        if a == "--":
            return full, args[i + 1] if i + 1 < len(args) else None
        if a.startswith("--"):
            full = full or a == "--full"
            if "=" not in a and a[2:] in ("signal", "uid", "euid", "group", "parent", "session",
                                          "terminal", "pidfile", "delimiter", "ns", "nslist"):
                i += 1
        elif a.startswith("-") and len(a) > 1:
            flags = a[1:]
            if not flags.isdigit() and not (len(flags) > 1 and flags.isupper()):  # -9/-TERM
                for j, ch in enumerate(flags):
                    if ch == "f":
                        full = True
                    if ch in VALUE_OPTS:
                        if j == len(flags) - 1:
                            i += 1
                        break
        else:
            return full, a
        i += 1
    return full, None


def _matches(pattern, command):
    try:
        return re.search(pattern, command) is not None
    except re.error:
        return pattern in command


def self_matching(command):
    """(tool, pattern) of the first pgrep/pkill -f whose pattern matches `command`, else None."""
    if not isinstance(command, str) or not any(t in command for t in TOOLS):
        return None
    try:
        toks = _tokens(command)
    except ValueError:
        return None
    for i, tok in enumerate(toks):
        if os.path.basename(tok) not in TOOLS:
            continue
        args = []
        for t in toks[i + 1:]:
            if t in SEPARATORS or t.startswith(">") or t.startswith("<"):
                break
            args.append(t)
        full, pattern = _full_and_pattern(args)
        if full and pattern and _matches(pattern, command):
            return os.path.basename(tok), pattern
    return None


def reason_for(tool, pattern):
    return (
        "Wait-loop guard: `%s -f %s` matches this command's own shell (its command line contains "
        "the pattern), so it is always true: a wait loop never exits and `pkill -f` kills itself. "
        "Instead run the command in the foreground with a long timeout (up to 600000 ms; a slow "
        "pre-commit hook fits), or start it in the background writing its exit code to a file "
        "(`cmd > run.log 2>&1; echo $? > run.rc`) and poll that file (`until [ -f run.rc ]; do "
        "sleep 15; done`). Never wait on `pgrep -f`." % (tool, shlex.quote(pattern)))


def main():
    try:
        payload = json.load(sys.stdin)
        if not isinstance(payload, dict):
            return 0
        hit = self_matching((payload.get("tool_input") or {}).get("command"))
        if hit:
            print(json.dumps({"hookSpecificOutput": {
                "hookEventName": "PreToolUse", "permissionDecision": "deny",
                "permissionDecisionReason": reason_for(*hit)}}))
    except Exception as exc:  # fail open
        print("wait_loop_guard: %s" % exc, file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
