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
with an upstream and nothing ahead of it are allowed silently without consuming the offer.

Known limit: the SubagentStop auto-mark uses the stop's `cwd`, so a review of another worktree is
marked only via `mark-reviewed --cwd <dir>`.
"""
import datetime
try:
    import fcntl  # POSIX; without it state writes are unlocked (Windows)
except ImportError:  # pragma: no cover
    fcntl = None
import json
import os
import shlex
import subprocess
import sys
import tempfile

_GIT_TIMEOUT = 3
_OPS_CHARS = set(";&|()\n")


def find_push(command):
    """Return None if `command` has no `git push`, else (dir, args): the directory `-C`/`cd` points
    at ('' = none) and the tokens after `push`."""
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
    cd_dir = ""
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
            return d, seg[j + 1:]
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
        "then push (the review grants no push permission by itself). To skip the review, re-run the "
        "same push: it will go through and HEAD is recorded as `declined` (not accepted risk). This "
        "offer is made once per HEAD. Set CODE_REVIEWER_PREPUSH=off to disable it."
    )


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


def _is_unscoped_review(payload):
    """True for a finished unscoped code-reviewer run (not a scoped slice review or a verifier)."""
    if str(payload.get("agent_type") or "").split(":")[-1] != "code-reviewer":
        return False
    text = payload.get("last_assistant_message")
    if not isinstance(text, str) or not text:
        path = payload.get("agent_transcript_path")  # never the parent transcript_path
        if not isinstance(path, str) or not path:
            return False
        text = extract_last_assistant_text(path)
    return "<!--CODE-REVIEWER-REPORT-->" in text and "<!--REVIEW-SCOPE:" not in text


def _on_subagent_stop(payload):
    if not _is_unscoped_review(payload):
        return
    repo = payload.get("cwd") or os.getcwd()
    head = _git(repo, "rev-parse", "HEAD")
    if head:
        _record(_state_path(repo), head, "reviewed")


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
        found = find_push(command)
        if found is None:
            return 0
        target, push_args = found
        if _skips_offer(push_args):
            return 0
        base_cwd = payload.get("cwd") or os.getcwd()
        repo = os.path.join(base_cwd, os.path.expanduser(target)) if target else base_cwd
        head = _git(repo, "rev-parse", "HEAD")
        if not head:
            return 0
        if _upstream(repo) and _git(repo, "rev-list", "@{upstream}..HEAD") == "":
            return 0  # nothing new to push
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
