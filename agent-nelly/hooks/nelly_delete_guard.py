#!/usr/bin/env python3
"""PreToolUse Bash: deny hard deletes (rm/unlink/rmdir/shred/git rm/find -delete) under the memory
store (R0d, "never hard-delete" made deterministic).

Entries are archived, never deleted: `mv` into `archive/` or `/nelly-memory prune`. Contract:
INTEROP.md "Source evidence, staleness, capture and safe writes".

Denied: a command segment that runs `rm`, `unlink`, `rmdir`, `shred`, `git rm`, or
`find ... -delete` / `find ... -exec rm|unlink|shred`, whose target is inside the agent-nelly
memory store (nelly_memory.BASE, LOCAL_BASE) or an ancestor of it (`rm -rf ~/.claude/plugins/data`).
Targets are resolved against the payload `cwd` plus preceding `cd`s and `git -C`, with `~`, `$HOME`
and `${HOME}` expanded; a bare `cd` goes home. Globs are resolved conservatively: a pattern that
can match the store, a path inside it, or an ancestor of it counts. A symlink target is resolved
through its directory only: `rm mylink` removes the link (allowed), `rm -rf mylink/` and
`rm mylink/x.md` reach the store (denied).

Allowed: targets named `*.tmp` / `*.lock` (incl. `.nelly.lock`), `mv` / `git mv`,
`git rm --cached` (only untracks), everything outside the store, quoted text (`echo "rm x"` is
one token).

`find` trade-off: a start path inside the store is denied unless every -name/-iname pattern ends
in .tmp or .lock. A start path that is an ancestor of the store is denied when it has no
-name/-iname/-path/-ipath/-regex filter, or a -name/-iname pattern fnmatch-matches a store file
name (x.md, MEMORY.md, nelly-index.json, GLOBAL-MEMORY.md; case-insensitive for -iname), or a
-path/-ipath/-regex filter mentions "agent-nelly-memory" or can match a path under it. So
`find ~ -delete`, `find ~ -name '*.md' -delete` and `find ~ -name '*' -delete` are denied, while
`find ~ -name .DS_Store -delete`, `find . -name '*.pyc' -delete` and `-path '*/node_modules/*'`
pass. A find with `!`, `-not` or `-o`/`-or` anywhere is read as having no filter (negation and
alternatives widen the delete), so it is denied inside the store and from an ancestor. -path and
-regex filters are tried against sample store paths (project-slug level included); -regex is also
tried translated from find's emacs syntax, and an uncompilable one is denied. Not caught: a name
filter that matches store files only through an unlisted file name.

Command parsing is best effort: one quote-aware scanner (single/double quotes, escapes,
comments, heredocs, `( )` subshells, `$( )` and backtick substitutions) splits at `; & | && ||` and
newlines. A `cd` inside a subshell or substitution never leaks out. Single-quoted text and quoted-
delimiter heredoc bodies are never scanned; double-quoted text and unquoted heredoc bodies are
(bash runs substitutions there). `$'...'` honours backslash escapes, `<<<` is a here-string,
`<( )` / `>( )` run their content like `$( )`. Leading shell keywords (`if then else elif do while
until { } !`), VAR=x and `sudo|env|timeout|nice|nohup|command|time`
wrappers are skipped; `sh|bash|zsh -c '...'` (also `-lc`, `-o opt -c`) is recursed.
Not handled: aliases, `xargs rm`, `eval`, variables other than ~ and $HOME.

Fail open on bad JSON or any error (no output, exit 0). NELLY_GATE=off (or 0/false/disabled)
disables. Commands with none of rm/unlink/rmdir/shred/-delete take a fast path that imports nothing.
"""
import fnmatch
import json
import os
import re
import sys

_FAST_WORDS = ("rm", "unlink", "rmdir", "shred", "-delete")
_DELETERS = ("rm", "unlink", "rmdir", "shred")
_GLOB_CHARS = "*?["
_SHELLS = ("sh", "bash", "zsh", "dash", "ksh")
_SIMPLE_PREFIXES = ("command", "builtin", "time", "nohup", "exec",
                    # shell keywords that precede a command (`if x; then rm ...`, `{ rm ...; }`)
                    "{", "}", "!", "if", "then", "else", "elif", "do", "while", "until")
_NAME_FLAGS = ("-name", "-iname")
_PATH_FLAGS = ("-path", "-ipath", "-wholename", "-iwholename", "-regex", "-iregex")
_STORE_DIRNAME = "agent-nelly-memory"
_STORE_FILE_NAMES = ("x.md", "MEMORY.md", "nelly-index.json", "GLOBAL-MEMORY.md", "entries",
                     "archive", "global", "conflicts", _STORE_DIRNAME)
_STORE_RELS = ("slug/entries/x.md", "slug/MEMORY.md", "slug/nelly-index.json", "slug/archive/x.md",
               "slug/conflicts/x.md", "global/GLOBAL-MEMORY.md", "conflicts/x.md", "MEMORY.md")

REASON = (
    "Agent Nelly memory entries are archived, never deleted: this command would hard-delete "
    "under the memory store ({target}). Move the entry into the store's archive/ directory "
    "(mv <entry> archive/) or run /nelly-memory prune to archive stale entries."
)


def _deny(target):
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": REASON.format(target=target),
    }}))


# --- quote-aware scanner -------------------------------------------------------------------
# One pass over the raw command builds a tree; subshell isolation, substitutions and heredocs all
# come from it. A statement is (words, subs): the command's words (quotes removed; a substitution
# leaves "$" in the word) and the statement lists of the `$(...)` / backtick substitutions that
# run before it. ("group", stmts) is a `( ... )` subshell. Single-quoted text and the bodies of
# quoted-delimiter heredocs are never scanned; double-quoted text and unquoted heredoc bodies are
# (bash runs substitutions there). `#` starts a comment only at the start of a word.

def _find_backtick(text, i):
    n = len(text)
    while i < n and text[i] != "`":
        i += 2 if text[i] == "\\" else 1
    return min(i, n)


def _scan_dq(text, i, until_quote):
    """Scan double-quoted text (or an unquoted heredoc body). -> (value, subs, next index)."""
    n, out, subs = len(text), [], []
    while i < n:
        c = text[i]
        if until_quote and c == '"':
            return "".join(out), subs, i + 1
        if c == "\\" and i + 1 < n and text[i + 1] in '$`"\\\n':
            if text[i + 1] != "\n":
                out.append(text[i + 1])
            i += 2
        elif c == "$" and text.startswith("$(", i):
            inner, i = _parse(text, i + 2, ")")
            subs.append(inner)
            out.append("$")
        elif c == "`":
            j = _find_backtick(text, i + 1)
            subs.append(_parse(text[i + 1:j])[0])
            out.append("$")
            i = j + 1
        else:
            out.append(c)
            i += 1
    return "".join(out), subs, i


def _heredoc_delim(text, i):
    """After `<<`: -> (next index, (delimiter, quoted, strip_tabs))."""
    n = len(text)
    strip = text.startswith("-", i)
    i += strip
    while i < n and text[i] in " \t":
        i += 1
    delim, quoted = [], False
    while i < n and text[i] not in " \t\r\n;&|()<>":
        ch = text[i]
        if ch in "'\"":
            quoted = True
            k = text.find(ch, i + 1)
            k = n if k == -1 else k
            delim.append(text[i + 1:k])
            i = k + 1
        elif ch == "\\":
            quoted = True
            delim.append(text[i + 1:i + 2])
            i += 2
        else:
            delim.append(ch)
            i += 1
    return i, ("".join(delim), quoted, strip)


def _read_heredocs(text, i, pending, stmts):
    """Consume pending heredoc bodies starting at line start `i`; -> next index."""
    n = len(text)
    for delim, quoted, strip in pending:
        body = []
        while i < n:
            j = text.find("\n", i)
            j = n if j == -1 else j
            line = text[i:j]
            i = min(j + 1, n)
            if (line.lstrip("\t") if strip else line) == delim:
                break
            body.append(line)
        if not quoted:
            subs = _scan_dq("\n".join(body), 0, False)[1]
            if subs:
                stmts.append(([], subs))
    pending.clear()
    return i


def _parse(text, i=0, closer=None):
    """Parse commands from text[i:] until `closer` (")") or the end. -> (stmts, next index)."""
    n = len(text)
    stmts, words, subs, cur, pending = [], [], [], [], []
    in_word = False

    def end_word():
        nonlocal in_word
        if in_word:
            words.append("".join(cur))
            cur.clear()
            in_word = False

    def end_cmd():
        end_word()
        if words or subs:
            stmts.append((list(words), list(subs)))
        words.clear()
        subs.clear()

    while i < n:
        c = text[i]
        if c == "\\":
            if i + 1 < n and text[i + 1] != "\n":
                cur.append(text[i + 1])
                in_word = True
            i += 2
        elif c == "'":
            j = text.find("'", i + 1)
            j = n if j == -1 else j
            cur.append(text[i + 1:j])
            in_word = True
            i = j + 1
        elif c == '"':
            val, sub_list, i = _scan_dq(text, i + 1, True)
            cur.append(val)
            subs.extend(sub_list)
            in_word = True
        elif c == "`":
            j = _find_backtick(text, i + 1)
            subs.append(_parse(text[i + 1:j])[0])
            cur.append("$")
            in_word = True
            i = j + 1
        elif c == "$" and text.startswith("$'", i):  # ANSI-C quoting: backslash escapes
            j = i + 2
            while j < n and text[j] != "'":
                j += 2 if text[j] == "\\" else 1
            cur.append(re.sub(r"\\(.)", r"\1", text[i + 2:j]))
            in_word = True
            i = j + 1
        elif c in "$<>" and text.startswith("(", i + 1):
            # `$(...)` command substitution and `<(...)` / `>(...)` process substitution
            inner, i = _parse(text, i + 2, ")")
            subs.append(inner)
            cur.append("$")
            in_word = True
        elif c == "#" and not in_word:
            j = text.find("\n", i)
            i = n if j == -1 else j
        elif c in " \t\r":
            end_word()
            i += 1
        elif c == "\n":
            end_cmd()
            i += 1
            if pending:
                i = _read_heredocs(text, i, pending, stmts)
        elif c in ";&|" and not (c == "&" and i > 0 and text[i - 1] in "<>"):
            end_cmd()
            i += 1
        elif c == "(" and not in_word:
            end_cmd()
            inner, i = _parse(text, i + 1, ")")
            stmts.append(("group", inner))
        elif c == ")":
            end_cmd()
            i += 1
            if closer == ")":
                return stmts, i
        elif c == "<" and text.startswith("<<<", i):  # here-string: one token, no body
            cur.append("<<<")
            in_word = True
            i += 3
        elif c == "<" and text.startswith("<<", i):
            i, spec = _heredoc_delim(text, i + 2)
            pending.append(spec)
        else:
            cur.append(c)
            in_word = True
            i += 1
    end_cmd()
    return stmts, i


def _is_assign(tok):
    name, eq, _ = tok.partition("=")
    return bool(eq) and name.isidentifier()


def _unwrap(seg):
    """Drop leading VAR=x, sudo/env/timeout/nice/command/... wrappers; normalise the command name."""
    seg = list(seg)
    while True:
        i = 0
        while i < len(seg) and _is_assign(seg[i]):
            i += 1
        seg = seg[i:]
        if not seg:
            return seg
        name = seg[0]
        if name.startswith("/"):
            name = os.path.basename(name)
        j = 1
        if name in _SIMPLE_PREFIXES:
            pass
        elif name == "sudo":
            while j < len(seg) and seg[j].startswith("-"):
                j += 2 if seg[j] in ("-u", "-g", "-h", "-p", "-C", "-D", "-R", "-T", "-U") else 1
        elif name == "env":
            while j < len(seg):
                a = seg[j]
                if a in ("-u", "-C", "-S"):
                    j += 2
                elif a.startswith("-") or _is_assign(a):
                    j += 1
                else:
                    break
        elif name == "timeout":
            while j < len(seg) and seg[j].startswith("-"):
                j += 2 if seg[j] in ("-s", "-k", "--signal", "--kill-after") else 1
            j += 1  # the duration
        elif name == "nice":
            if j < len(seg) and seg[j] == "-n":
                j += 2
            elif j < len(seg) and seg[j].startswith("-"):
                j += 1
        else:
            seg[0] = name
            return seg
        seg = seg[j:]


def _store_roots():
    from nelly_memory import BASE, LOCAL_BASE  # lazy: keep the fast path import-free
    roots = set()
    for b in (BASE, LOCAL_BASE):
        if b:
            n = os.path.normpath(b)
            roots.add(n)
            roots.add(os.path.realpath(n))
    return roots


def _expand(tok, home):
    for var in ("${HOME}", "$HOME"):
        if tok.startswith(var):
            tok = home + tok[len(var):]
    if tok == "~" or tok.startswith("~/"):
        tok = home + tok[1:]
    return tok


def _comps(path):
    return [c for c in path.split(os.sep) if c]


def _match(pattern_comps, store_comps):
    """True when the pattern can reach the store, a path inside it, or an ancestor of it."""
    n = min(len(pattern_comps), len(store_comps))
    for p, s in zip(pattern_comps[:n], store_comps[:n]):
        if p == s:
            continue
        if any(g in p for g in _GLOB_CHARS) and fnmatch.fnmatchcase(s, p):
            continue
        return False
    return True


def _store_kind(target, base, home, roots):
    """None, 'inside' (the store or below) or 'ancestor' (strictly above it) for a raw token."""
    tok = _expand(target, home)
    if not tok or "$" in tok or "`" in tok:
        return None  # unresolvable: fail open
    if os.path.basename(tok.rstrip("/")).endswith((".tmp", ".lock")):
        return None
    trailing = tok.endswith("/")
    path = os.path.normpath(tok if os.path.isabs(tok) else os.path.join(base, tok))
    candidates = [path]
    if not any(g in path for g in _GLOB_CHARS):
        if trailing:
            candidates.append(os.path.realpath(path))
        else:  # a symlink named by the target is removed itself, not followed
            candidates.append(os.path.join(os.path.realpath(os.path.dirname(path)),
                                           os.path.basename(path)))
    kind = None
    for cand in candidates:
        pc = _comps(cand)
        for root in roots:
            sc = _comps(root)
            if _match(pc, sc):
                if len(pc) >= len(sc):
                    return "inside"
                kind = "ancestor"
    return kind


def _emacs_to_py(pat):
    r"""find's default -regex syntax: `\(`, `\)`, `\|` group/alternate, bare `( ) |` are literal."""
    out, i = [], 0
    while i < len(pat):
        c = pat[i]
        if c == "\\" and i + 1 < len(pat):
            d = pat[i + 1]
            out.append(d if d in "()|{}" else "\\" + d)
            i += 2
        else:
            out.append("\\" + c if c in "()|{}" else c)
            i += 1
    return "".join(out)


def _regex_reaches(pat, samples, flags):
    try:
        cands = [re.compile(_emacs_to_py(pat), flags)]
    except re.error:
        return True  # cannot tell: deny conservatively
    try:
        cands.append(re.compile(pat, flags))
    except re.error:
        pass
    return any(c.fullmatch(sp) for c in cands for sp in samples)


def _filters_reach_store(filters, roots):
    """True when a find -name/-path/-regex filter can match store file names or paths."""
    samples = [os.path.join(r, rel) for r in roots for rel in _STORE_RELS]
    for flag, pat in filters:
        fold = flag.startswith("-i")
        if flag in _NAME_FLAGS:
            targets = [n.lower() if fold else n for n in _STORE_FILE_NAMES]
            if any(fnmatch.fnmatchcase(t, pat.lower() if fold else pat) for t in targets):
                return True
        elif _STORE_DIRNAME in pat:
            return True
        elif "regex" in flag:
            if _regex_reaches(pat, samples, re.I if fold else 0):
                return True
        else:
            if any(fnmatch.fnmatchcase(sp.lower() if fold else sp, pat.lower() if fold else pat)
                   for sp in samples):
                return True
    return False


def _find_hit(args, base, home, roots):
    """Offending start path of a deleting `find`, or None."""
    paths, i = [], 0
    while i < len(args) and not (args[i].startswith("-") and args[i] != "-") \
            and args[i] not in ("(", ")", "!", "\\(", "\\)", ","):
        paths.append(args[i])
        i += 1
    filters, deletes = [], False
    for k, a in enumerate(args):
        nxt = args[k + 1] if k + 1 < len(args) else ""
        if a == "-delete":
            deletes = True
        elif a in ("-exec", "-execdir", "-ok", "-okdir") and \
                os.path.basename(nxt) in _DELETERS:
            deletes = True
        elif a in _NAME_FLAGS or a in _PATH_FLAGS:
            filters.append((a, nxt))
    if not deletes:
        return None
    if any(a in ("!", "-not", "-o", "-or") for a in args):
        filters = []  # negation / alternatives widen the delete: read as no filter at all
    names = [pat for flag, pat in filters if flag in _NAME_FLAGS]
    for t in paths or ["."]:
        kind = _store_kind(t, base, home, roots)
        if kind == "inside":
            if not (names and len(names) == len(filters)
                    and all(n.endswith((".tmp", ".lock")) for n in names)):
                return t
        elif kind == "ancestor":
            if not filters or _filters_reach_store(filters, roots):
                return t
    return None


def _operands(args):
    out, rest = [], False
    for a in args:
        if rest or not a.startswith("-") or a == "-":
            out.append(a)
        elif a == "--":
            rest = True
    return out


def _check_segment(seg, cd_dir, home, roots, depth):
    """-> (offending target or None, cd_dir after this segment)."""
    seg = _unwrap(seg)
    if not seg:
        return None, cd_dir
    head = seg[0]
    if head == "cd":
        if len(seg) == 1 or seg[1] == "~":
            return None, home
        if seg[1] != "-":
            return None, os.path.normpath(os.path.join(cd_dir, _expand(seg[1], home)))
        return None, cd_dir
    if head in _SHELLS and depth < 4:
        j = 1
        while j < len(seg):
            a = seg[j]
            if a in ("-o", "+o"):
                j += 2
                continue
            if not a.startswith(("-", "+")):
                break
            if a.startswith("-") and not a.startswith("--") and "c" in a[1:] and j + 1 < len(seg):
                return _check(seg[j + 1], cd_dir, home, roots, depth + 1), cd_dir
            j += 1
        return None, cd_dir
    base = cd_dir
    if head in _DELETERS:
        targets = _operands(seg[1:])
    elif head == "git":
        j = 1
        while j < len(seg):
            a = seg[j]
            if a == "-C" and j + 1 < len(seg):
                base = os.path.normpath(os.path.join(base, _expand(seg[j + 1], home)))
                j += 2
            elif a == "-c" and j + 1 < len(seg):
                j += 2
            elif a.startswith("-"):
                j += 1
            else:
                break
        targets = []
        if j < len(seg) and seg[j] == "rm" and "--cached" not in seg[j + 1:]:
            targets = _operands(seg[j + 1:])
    elif head == "find":
        return _find_hit(seg[1:], base, home, roots), cd_dir
    else:
        return None, cd_dir
    for t in targets:
        if _store_kind(t, base, home, roots):
            return t, cd_dir
    return None, cd_dir


def _check_list(stmts, cd_dir, home, roots, depth):
    """-> (offending target or None, cd_dir after the list). Subshells and substitutions run with
    the cd context at their point and never change it for the statements after them."""
    for st in stmts:
        if st[0] == "group":
            hit = _check_list(st[1], cd_dir, home, roots, depth)[0]
            if hit:
                return hit, cd_dir
            continue
        words, subs = st
        for sub in subs:
            hit = _check_list(sub, cd_dir, home, roots, depth)[0]
            if hit:
                return hit, cd_dir
        hit, cd_dir = _check_segment(words, cd_dir, home, roots, depth)
        if hit:
            return hit, cd_dir
    return None, cd_dir


def _check(command, cwd, home, roots, depth=0):
    """Return the offending target token, or None."""
    return _check_list(_parse(command)[0], cwd, home, roots, depth)[0]


def main():
    try:
        if os.environ.get("NELLY_GATE", "").lower() in ("off", "0", "false", "disabled"):
            return 0
        payload = json.load(sys.stdin)
        command = payload["tool_input"]["command"]
        if not isinstance(command, str) or not any(w in command for w in _FAST_WORDS):
            return 0
        cwd = payload.get("cwd") or os.getcwd()
        home = os.path.expanduser("~")
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        hit = _check(command, cwd, home, _store_roots())
        if hit:
            _deny(hit)
    except Exception:
        pass  # fail open
    return 0


if __name__ == "__main__":
    sys.exit(main())
