#!/usr/bin/env python3
"""PreToolUse Bash: offer a whole-diff review before a `git push` of an unreviewed HEAD (R15).

State: `<git dir>/code-review/pre-push.json` = {"<head sha>": {"status": "offered|reviewed|declined",
"at": <iso time>}}.

- HEAD `reviewed`            -> allow silently.
- HEAD unseen                -> deny once with the offer; record `offered`.
- HEAD `offered` (re-pushed) -> allow; record `declined` (never accepted risk). Never denies twice.
- `pre_push_offer.py mark-reviewed [--cwd DIR]` records `reviewed` for the current HEAD.
- `CODE_REVIEWER_PREPUSH=off` -> always allow.
- SubagentStop: an unscoped code-reviewer finish (agent_type ends in `code-reviewer`, report text has
  `<!--CODE-REVIEWER-REPORT-->`, no `<!--REVIEW-SCOPE:` line) records `reviewed` for HEAD of the
  payload `cwd`. Text comes from `last_assistant_message`, else `agent_transcript_path`; never the
  parent `transcript_path`. Silent, fail-open.
Any error (bad JSON, not a repo, git failure, unwritable state) fails open: no output, exit 0.

Push detection is best effort: the command is tokenised with shlex, split at `; & | && ||`, and a
segment counts when it is `[VAR=x ...] git [-C dir | -c k=v | --opt ...] push`. A quoted
`echo "git push"` is one token and is not a push. Not handled: push hidden in `bash -c '...'`,
`$(...)`, aliases, or variables. Newlines separate commands like `;`.
`--dry-run`, `-n`, `--help`, branch deletes (`--delete`, `-d`, `:ref`), `--tags`-only pushes and a push
with nothing new (HEAD already on its upstream or any remote-tracking ref) are allowed silently
without consuming the offer. The offer lists open gating findings (block_commit, pause_for_review or
decision block, resolution open or absent) from `<git dir>/code-review/findings.json`.

A push chained after a HEAD-moving git command (`git commit -m x && git push`) is offered once,
keyed `chained:<pre-command HEAD>`, asking for separate commands; the unchanged re-run is `declined`.
The SubagentStop auto-mark skips reports with open gating findings (block_commit, pause_for_review,
decision block) and marks the repo on a report line `Review cwd: <path>`, else the stop's `cwd`.
"""
import datetime
try:
    import fcntl  # POSIX; without it state writes are unlocked (Windows)
except ImportError:  # pragma: no cover
    fcntl = None
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile

_GIT_TIMEOUT = 3
_OPS_CHARS = set(";&|()\n")


_HEAD_CHANGING = {"commit", "merge", "rebase", "cherry-pick", "am", "pull", "revert", "reset"}


def find_push(command):
    """Return None if `command` has no `git push`, else (dir, args): the directory `-C`/`cd` points
    at ('' = none) and the tokens after `push`."""
    found = find_push_info(command)
    return None if found is None else found[:2]


def find_push_info(command):
    """Like find_push, plus a third item: True when an earlier segment runs a git command that moves
    HEAD (commit, merge, rebase, ...), so HEAD now is not the HEAD that will be pushed."""
    if "push" not in command or "git" not in command:  # cheap fast path
        return None
    try:
        lex = shlex.shlex(command, posix=True, punctuation_chars=";&|()\n")
        lex.whitespace_split = True
        lex.whitespace = " \t\r"  # newline is an operator token, like `;`
        tokens = list(lex)
    except ValueError:
        return None
    segments, cur = [], []
    for t in tokens:
        if t and set(t) <= _OPS_CHARS:
            segments.append(cur)
            cur = []
        else:
            cur.append(t)
    segments.append(cur)
    cd_dir, head_moves = "", False
    for seg in segments:
        i = 0
        while i < len(seg) and "=" in seg[i] and not seg[i].startswith(("-", "=")):
            i += 1
        seg = seg[i:]
        if len(seg) >= 2 and seg[0] == "cd":
            cd_dir = os.path.join(cd_dir, seg[1]) if cd_dir else seg[1]
            continue
        if not seg or seg[0] != "git":
            continue
        c_dir, j = "", 1
        while j < len(seg):
            a = seg[j]
            if a == "-C" and j + 1 < len(seg):
                c_dir = os.path.join(c_dir, seg[j + 1]) if c_dir else seg[j + 1]
                j += 2
            elif a == "-c" and j + 1 < len(seg):
                j += 2
            elif a.startswith("-"):
                j += 1
            else:
                break
        if j < len(seg) and seg[j] == "push":
            d = os.path.join(cd_dir, c_dir) if cd_dir and c_dir else (c_dir or cd_dir)
            return d, seg[j + 1:], head_moves
        if j < len(seg) and seg[j] in _HEAD_CHANGING:
            head_moves = True
    return None


def is_push(command):
    return find_push(command) is not None


def _skips_offer(args):
    """Pushes that publish nothing reviewable: dry runs, help, branch deletes, tags-only."""
    if any(a in ("--dry-run", "-n", "--help") for a in args):
        return True
    if any(a in ("--delete", "-d") or a.startswith(":") for a in args):
        return True
    positional = [a for a in args if not a.startswith("-")]
    return "--tags" in args and len(positional) <= 1


def _git(repo, *args):
    env = {k: v for k, v in os.environ.items() if k not in ("GIT_DIR", "GIT_WORK_TREE")}
    r = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, errors="replace",
                       timeout=_GIT_TIMEOUT, env=env)
    return r.stdout.strip() if r.returncode == 0 else None


def _state_path(repo):
    git_dir = _git(repo, "rev-parse", "--absolute-git-dir")
    if not git_dir:
        raise RuntimeError("not a git repo")
    return os.path.join(git_dir, "code-review", "pre-push.json")


def _load(path):
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _record(path, head, status):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path + ".lock", "a") as lock:
        if fcntl is not None:
            fcntl.flock(lock, fcntl.LOCK_EX)  # released on close
        _record_locked(path, head, status)


def _record_locked(path, head, status):
    state = _load(path)
    state[head] = {"status": status, "at": datetime.datetime.now().astimezone().isoformat()}
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), prefix=".pre-push-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(state, fh, indent=2)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _upstream(repo):
    return _git(repo, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}")


def _base(repo):
    """upstream, else origin/HEAD, else origin/main or main; None if none exist."""
    up = _upstream(repo)
    if up:
        return up
    for ref in ("origin/HEAD", "origin/main", "main"):
        if _git(repo, "rev-parse", "--verify", "--quiet", ref + "^{commit}"):
            return ref
    return None


_BLOCKING_ACTIONS = ("block_commit", "pause_for_review")


def _open_blockers(repo, limit=5):
    """Open gating findings from <git dir>/code-review/findings.json, as `F1 file:line summary`."""
    try:
        git_dir = _git(repo, "rev-parse", "--absolute-git-dir")
        with open(os.path.join(git_dir, "code-review", "findings.json")) as fh:
            findings = json.load(fh).get("findings") or []
    except Exception:
        return []
    out = []
    for f in findings:
        if not isinstance(f, dict) or f.get("resolution", "open") != "open":
            continue
        if f.get("workflow_action") in _BLOCKING_ACTIONS or f.get("decision") == "block":
            loc = f"{f.get('file', '?')}" + (f":{f['line']}" if f.get("line") else "")
            out.append(f"{f.get('id', '?')} {loc} {str(f.get('summary', ''))[:120]}")
    return out[:limit] + ([f"... and {len(out) - limit} more"] if len(out) > limit else [])


def _offer_reason(repo):
    plan = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "scripts", "review_plan.py")
    me = os.path.abspath(__file__)
    base = _base(repo)
    plan_cmd = f"python3 {shlex.quote(plan)} plan" + (f" --base {shlex.quote(base)}" if base else "")
    mark_cmd = f"python3 {shlex.quote(me)} mark-reviewed --cwd {shlex.quote(os.path.realpath(repo))}"
    return (
        "Pre-push review offer: HEAD has not been reviewed. Review the whole outgoing diff first: "
        f"run `{plan_cmd}` and review that diff with the "
        "code-reviewer skill (references/pre-push.md), starting the summary with "
        f"<!--PRE-PUSH-REVIEW-->. When the review is done, run `{mark_cmd}` to mark HEAD reviewed, "
        "then push (the review grants no push permission by itself). Ask the user whether to review "
        "or skip; do not decide for them, even when the push itself was pre-authorized. To skip, "
        "re-run the same push: it will go through and HEAD is recorded as `declined` (not accepted risk). This "
        "offer is made once per HEAD. Set CODE_REVIEWER_PREPUSH=off to disable it."
    ) + _blocker_note(repo)


def _blocker_note(repo):
    blockers = _open_blockers(repo)
    if not blockers:
        return ""
    return (" Unresolved blocking findings from the last review (findings.json): "
            + "; ".join(blockers) + ".")


def _mark_reviewed(argv):
    cwd = os.getcwd()
    if "--cwd" in argv and argv.index("--cwd") + 1 < len(argv):
        cwd = argv[argv.index("--cwd") + 1]
    try:
        head = _git(cwd, "rev-parse", "HEAD")
        if not head:
            raise RuntimeError("no HEAD")
        _record(_state_path(cwd), head, "reviewed")
    except Exception as exc:
        print(f"mark-reviewed failed: {exc}", file=sys.stderr)
        return 1
    print(f"pre-push: {head[:12]} marked reviewed")
    return 0


def extract_last_assistant_text(transcript_path, tail_bytes=16384):
    """Text of the last assistant message in a JSONL transcript (tail read; copied from
    agent-isdd subagent_report.py to stay self-contained)."""
    try:
        with open(transcript_path, "rb") as fh:
            fh.seek(0, 2)
            size = fh.tell()
            start = max(0, size - tail_bytes)
            fh.seek(start)
            raw = fh.read()
    except OSError:
        return ""
    lines = raw.split(b"\n")
    if start > 0:
        lines = lines[1:]  # drop a partial first line
    blocks = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        if not isinstance(ev, dict):
            continue
        msg = ev.get("message") if isinstance(ev.get("message"), dict) else None
        role = ev.get("type") or (msg.get("role") if msg else "")
        if not (role == "assistant" or (msg and msg.get("role") == "assistant")):
            continue
        content = msg.get("content") if msg else ev.get("content")
        if isinstance(content, str):
            blocks.append(content)
        elif isinstance(content, list):
            joined = "\n".join(c.get("text", "") for c in content
                               if isinstance(c, dict) and c.get("type") == "text" and c.get("text"))
            if joined:
                blocks.append(joined)
    return blocks[-1].strip() if blocks else ""


_GATING_RE = re.compile(
    r'"(?:workflow_action"\s*:\s*"(?:block_commit|pause_for_review)|decision"\s*:\s*"block)"')
_REVIEW_CWD_RE = re.compile(r"^Review cwd:\s*(.+?)\s*$", re.M)


_PROMPT_SCOPE_RE = re.compile(r"^Review scope:[ \t]*slice=\d", re.M | re.I)


def _first_user_prompt(path, max_bytes=1048576):
    """The subagent's first user message (its brief), from the first line of its own transcript
    (copied on purpose: agent-isdd's review_tracking reads it the same way); "" on any failure."""
    try:
        with open(path, "rb") as fh:
            line = fh.readline(max_bytes)
        msg = json.loads(line).get("message") or {}
    except (OSError, ValueError, TypeError, AttributeError):
        return ""
    if not isinstance(msg, dict) or msg.get("role") != "user":
        return ""
    content = msg.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(b.get("text", "") for b in content if isinstance(b, dict))
    return ""


def _unscoped_review_text(payload):
    """Report text of a finished unscoped code-reviewer run, else None. A run whose brief had a
    `Review scope: slice=…` line is a scoped (slice) review even if it forgot to echo the marker."""
    if str(payload.get("agent_type") or "").split(":")[-1] != "code-reviewer":
        return None
    text = payload.get("last_assistant_message")
    if not isinstance(text, str) or not text:
        path = payload.get("agent_transcript_path")  # never the parent transcript_path
        if not isinstance(path, str) or not path:
            return None
        text = extract_last_assistant_text(path)
    if "<!--CODE-REVIEWER-REPORT-->" not in text or "<!--REVIEW-SCOPE:" in text:
        return None
    path = payload.get("agent_transcript_path")
    if isinstance(path, str) and path and _PROMPT_SCOPE_RE.search(_first_user_prompt(path)):
        return None
    return text


def _is_unscoped_review(payload):
    return _unscoped_review_text(payload) is not None


def _on_subagent_stop(payload):
    text = _unscoped_review_text(payload)
    if text is None or _GATING_RE.search(text):
        return  # a review with open gating findings does not clear the push offer
    m = _REVIEW_CWD_RE.search(text)
    repo = os.path.expanduser(m.group(1)) if m else (payload.get("cwd") or os.getcwd())
    head = _git(repo, "rev-parse", "HEAD")
    if head:
        _record(_state_path(repo), head, "reviewed")


def _deny(reason):
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse", "permissionDecision": "deny",
        "permissionDecisionReason": reason}}))


def _chained_offer(path, key):
    """A push chained after a commit/merge/...: the HEAD to be pushed doesn't exist yet."""
    status = _load(path).get(key, {}).get("status")
    if status == "offered":
        _record(path, key, "declined")
        return 0
    if status:
        return 0
    _record(path, key, "offered")
    _deny("Pre-push review offer: this command moves HEAD (commit/merge/rebase/...) and pushes in "
          "one step, so the commit being pushed can't be checked for a review yet. Run the commit "
          "and the push as separate commands; the push then gets the normal pre-push check. Ask the "
          "user before re-running the combined command unchanged: that skips the check and is "
          "recorded as `declined` (not accepted risk). Set CODE_REVIEWER_PREPUSH=off to disable.")
    return 0


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] == "mark-reviewed":
        return _mark_reviewed(argv[1:])
    try:
        if os.environ.get("CODE_REVIEWER_PREPUSH", "").lower() == "off":
            return 0
        payload = json.load(sys.stdin)
        if payload.get("hook_event_name") == "SubagentStop":
            _on_subagent_stop(payload)
            return 0
        command = payload["tool_input"]["command"]
        found = find_push_info(command)
        if found is None:
            return 0
        target, push_args, head_moves = found
        if _skips_offer(push_args):
            return 0
        base_cwd = payload.get("cwd") or os.getcwd()
        repo = os.path.join(base_cwd, os.path.expanduser(target)) if target else base_cwd
        head = _git(repo, "rev-parse", "HEAD")
        if not head:
            return 0
        if head_moves:
            return _chained_offer(_state_path(repo), "chained:" + head)
        if _upstream(repo) and _git(repo, "rev-list", "@{upstream}..HEAD") == "":
            return 0  # nothing new to push
        if _git(repo, "rev-list", "-1", "HEAD", "--not", "--remotes") == "":
            return 0  # HEAD already on a remote-tracking ref: nothing new to review
        path = _state_path(repo)
        status = _load(path).get(head, {}).get("status")
        if status in ("reviewed", "declined"):
            return 0
        if status == "offered":
            _record(path, head, "declined")
            return 0
        reason = _offer_reason(repo)
        _record(path, head, "offered")  # if this raises we fail open rather than deny unrecorded
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse", "permissionDecision": "deny",
            "permissionDecisionReason": reason}}))
    except Exception:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
