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
# Words after which the next word is still in command position.
KEYWORDS = {"if", "then", "do", "else", "elif", "while", "until"}
# Command prefixes: their options (and these options' values) come before the real command.
WRAPPERS = {"sudo": set("ugCDhpRrTU"), "timeout": set("sk"), "env": set("uSC"), "nice": set("n"),
            "nohup": set(), "time": set(), "command": set(), "exec": set("a"), "stdbuf": set("ioe"),
            "xargs": set("IinPsLEd"), "caffeinate": set("tw")}
ASSIGN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
DURATION = re.compile(r"^\d+(\.\d+)?[smhd]?$")


def _substitutions(tok):
    """Bodies of every $(...) (balanced, nested parens allowed) and `...` in one token."""
    out, i = [], 0
    while i < len(tok):
        if tok.startswith("$(", i):
            depth, j = 1, i + 2
            while j < len(tok) and depth:
                depth += {"(": 1, ")": -1}.get(tok[j], 0)
                j += 1
            out.append(tok[i + 2:j - 1] if depth == 0 else tok[i + 2:])
            i = j
        elif tok[i] == "`":
            j = tok.find("`", i + 1)
            j = len(tok) if j < 0 else j
            out.append(tok[i + 1:j])
            i = j + 1
        else:
            i += 1
    return out


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


def _walk(toks):
    """Yield (index, kind, word) for each token in command position: kind "keyword" for shell
    keywords and "command" for the command word (its basename). Command position starts after a
    separator or keyword and skips NAME=value words and wrappers with their options (and those
    options' values, plus `timeout`'s duration). Shared by `_scan` and `_strip_heredocs`."""
    expect, wrapper, skip = True, None, False
    for i, tok in enumerate(toks):
        if tok in SEPARATORS:
            expect, wrapper, skip = True, None, False
            continue
        if not expect:
            continue
        if skip:
            skip = False
            continue
        if wrapper is not None:
            if tok.startswith("-"):
                skip = len(tok) == 2 and tok[1] in WRAPPERS[wrapper]
                continue
            if wrapper == "timeout" and DURATION.match(tok):
                continue
        if ASSIGN.match(tok):
            continue
        if tok in KEYWORDS or tok in ("for", "select", "done"):
            yield i, "keyword", tok
            expect = tok in KEYWORDS  # `for x in ...` words are not commands
            continue
        name = os.path.basename(tok)
        if name in WRAPPERS:
            wrapper = name
            continue
        expect, wrapper = False, None
        yield i, "command", name


def _scan(segment, command, in_loop):
    """First self-matching (tool, pattern) in `segment`. A pgrep/pkill counts only in command
    position (see `_walk`); `in_loop` is true between a `while`/`until` and its `done`."""
    try:
        toks = _tokens(segment)
    except ValueError:
        return None
    events = {i: (kind, word) for i, kind, word in _walk(toks)}
    loops = []  # stack of open loop keywords
    for i, tok in enumerate(toks):
        loop = in_loop or "while" in loops or "until" in loops
        for body in _substitutions(tok):
            hit = _scan(body, command, loop)
            if hit:
                return hit
        kind, word = events.get(i, (None, None))
        if kind == "keyword":
            if word in ("while", "until", "for", "select"):
                loops.append(word)
            elif word == "done" and loops:
                loops.pop()
            continue
        if kind != "command" or word not in TOOLS:
            continue
        args = []
        for t in toks[i + 1:]:
            if t in SEPARATORS or t[:1] in "<>" or t[:2] in ("2>", "1>", "&>"):
                break
            args.append(t)
        full, ancestors, pattern = _parse(args)
        if full and pattern and (ancestors or loop) and _matches(pattern, command):
            return word, pattern
    return None


# Groups: 1 `-` of <<-, 2 quote, 3 delimiter, 4 rest of the opening line. The body may be empty;
# the closing delimiter may be tab-indented only for <<-. `<<<` here-strings are not heredocs.
HEREDOC = re.compile(r"(?<!<)<<(?!<)(-)?[ \t]*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\2([^\n]*)\n"
                     r"(?:.*?\n)??(?(1)\t*)\3(?=\n|$)", re.S)
SHELLS = {"bash", "sh", "zsh", "dash", "ksh"}


LINE_TOKEN = re.compile(r"&&|\|\||\$\(|[;&|()`]|[^\s;&|()`]+")
LIST_SEPARATORS = {";", "&&", "||", "&", "`"}
HERE = "\0"  # stands for the heredoc operator on its opening line


def _feeds_shell(before, after):
    """Whether the heredoc at the end of `before` (text from the start of its line) feeds a
    shell: a shell in command position in the same list element, i.e. the pipeline holding the
    `<<` (and any `{ }`/`( )` group it redirects), not one after `;`, `&&`, `||` or `&`.
    Quoted text is dropped, so a title like "fix bash hook" does not count."""
    line = re.sub(r"\"[^\"]*\"|'[^']*'", " ", "%s %s %s" % (before, HERE, after))
    line = re.sub(r"[<>]&|&>", ">", line.replace('"', " ").replace("'", " "))
    toks = ["(" if t == "$(" else t for t in LINE_TOKEN.findall(line)]
    at = toks.index(HERE)
    start, depth = at, 0
    while start > 0:
        t = toks[start - 1]
        if t in (")", "}"):
            depth += 1
        elif t in ("(", "{"):
            if not depth:
                break
            depth -= 1
        elif not depth and t in LIST_SEPARATORS:
            break
        start -= 1
    end, depth = at + 1, 0
    while end < len(toks):
        t = toks[end]
        if t in ("(", "{"):
            depth += 1
        elif t in (")", "}"):
            if not depth:
                break
            depth -= 1
        elif not depth and t in LIST_SEPARATORS:
            break
        end += 1
    element = [t for t in toks[start:end] if t != HERE]
    return any(kind == "command" and word in SHELLS for _, kind, word in _walk(element))


def _strip_heredocs(command):
    """Drop heredoc bodies (data such as commit messages, not commands), keeping the line that
    opened each one. A heredoc fed to a shell (`bash <<EOF`) is its commands, so it stays."""
    def repl(m):
        before = command[command.rfind("\n", 0, m.start()) + 1:m.start()]
        if _feeds_shell(before, m.group(4)):
            return m.group(0)
        return "<<%s%s" % (m.group(3), m.group(4))
    return HEREDOC.sub(repl, command)


def self_matching(command):
    """(tool, pattern) of the first pgrep/pkill -f whose pattern matches its own shell on this
    platform (or any self-matching wait loop), else None. Heredoc bodies are not scanned."""
    if not isinstance(command, str) or not any(t in command for t in TOOLS):
        return None
    return _scan(_strip_heredocs(command), command, False)


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
