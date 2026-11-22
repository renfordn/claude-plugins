#!/usr/bin/env python3
"""PreToolUse Bash: deny `pgrep -f` / `pkill -f` patterns that match the command running them.

`-f` matches full command lines, and the Bash tool's shell carries the command, pattern included.
- Linux (procps) excludes only pgrep itself, so the shell always self-matches (unless `-A`):
  `while pgrep -f "git commit"; do sleep 15; done` never exits and `pkill -f` kills its own shell.
- macOS/BSD exclude pgrep's ancestors unless `-a`, so a one-shot call is fine there, but two
  wait loops on the same pattern still match each other's shell and neither exits. An agent-TDD
  run sat idle ~12 hours that way with four piled-up loops.
So: deny any self-matching call on Linux or with BSD `-a`, and any self-matching wait loop
(`while`/`until`) everywhere. Fails open on any error."""
import json
import os
import re
import shlex
import sys

TOOLS = ("pgrep", "pkill")
BSD = sys.platform == "darwin" or "bsd" in sys.platform
# Short options that take a value (procps and BSD); the value is not the pattern.
VALUE_OPTS = set("uUgGPstFdrM")
LONG_VALUE_OPTS = ("signal", "uid", "euid", "group", "parent", "session", "terminal", "pidfile",
                   "delimiter", "ns", "nslist", "pgroup", "older", "runstates", "cgroup", "env")
SEPARATORS = {";", "&&", "||", "|", "&", "(", ")", "!", "{", "}"}
# Words after which the next word is a command (shell keywords and simple prefixes).
LEADERS = {"while", "until", "if", "then", "do", "else", "elif", "time", "sudo", "command",
           "exec", "nohup", "timeout", "env", "xargs"}
LOOP = re.compile(r"(^|[\s;&|(])(while|until)\s")
SUBST = re.compile(r"\$\(([^()]*)\)|`([^`]*)`")


def _tokens(command):
    lex = shlex.shlex(command.replace("\n", " ; "), posix=True, punctuation_chars=";&|()")
    lex.whitespace_split = True
    lex.commenters = ""
    return list(lex)


def _parse(args):
    """(uses -f/--full, includes ancestors per platform, first pattern) from pgrep/pkill args."""
    full, ancestors, i = False, not BSD, 0
    while i < len(args):
        a = args[i]
        if a == "--":
            return full, ancestors, args[i + 1] if i + 1 < len(args) else None
        if a.startswith("--"):
            name = a[2:].split("=", 1)[0]
            full = full or name == "full"
            if name == "ignore-ancestors":
                ancestors = False
            if "=" not in a and name in LONG_VALUE_OPTS:
                i += 1
        elif a.startswith("-") and len(a) > 1:
            flags = a[1:]
            if not flags.isdigit() and not (len(flags) > 1 and flags.isupper()):  # -9/-TERM
                for j, ch in enumerate(flags):
                    if ch == "f":
                        full = True
                    elif ch == "a" and BSD:
                        ancestors = True
                    elif ch == "A" and not BSD:
                        ancestors = False
                    if ch in VALUE_OPTS:
                        if j == len(flags) - 1:
                            i += 1
                        break
        else:
            return full, ancestors, a
        i += 1
    return full, ancestors, None


def _matches(pattern, command):
    try:
        return re.search(pattern, command) is not None
    except re.error:
        return pattern in command


def _scan(segment, command, loop):
    try:
        toks = _tokens(segment)
    except ValueError:
        return None
    for i, tok in enumerate(toks):
        for m in SUBST.finditer(tok):  # "$(pgrep -f x)" / `pgrep -f x` inside one token
            hit = _scan(m.group(1) or m.group(2) or "", command, loop)
            if hit:
                return hit
        prev = toks[i - 1] if i else None
        if os.path.basename(tok) not in TOOLS or not (prev is None or prev in SEPARATORS
                                                      or prev in LEADERS):
            continue
        args = []
        for t in toks[i + 1:]:
            if t in SEPARATORS or t[:1] in "<>" or t[:2] in ("2>", "1>", "&>"):
                break
            args.append(t)
        full, ancestors, pattern = _parse(args)
        if full and pattern and (ancestors or loop) and _matches(pattern, command):
            return os.path.basename(tok), pattern
    return None


def self_matching(command):
    """(tool, pattern) of the first pgrep/pkill -f whose pattern matches its own shell on this
    platform (or any self-matching wait loop), else None."""
    if not isinstance(command, str) or not any(t in command for t in TOOLS):
        return None
    return _scan(command, command, bool(LOOP.search(command)))


def reason_for(tool, pattern):
    return (
        "Wait-loop guard: `%s -f %s` matches the shell running this command (its command line "
        "contains the pattern; on macOS another loop's shell with the same pattern), so a wait "
        "loop never exits and `pkill -f` can kill itself. Instead run the command in the "
        "foreground with a long timeout (up to 600000 ms; a slow pre-commit hook fits), or start "
        "it in the background writing its exit code to a file (`cmd > run.log 2>&1; echo $? > "
        "run.rc`) and poll that file (`until [ -f run.rc ]; do sleep 15; done`). Never wait on "
        "`pgrep -f`." % (tool, shlex.quote(pattern)))


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
