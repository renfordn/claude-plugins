#!/usr/bin/env python3
"""Stop hook: ask once per turn to record a clear source-linked finding; queue findings on uncommitted files (R18).

A finding is a line of the final answer with a behaviour verb plus an existing repo path (relative,
or absolute inside the repo) or an indexed symbol (>= 4 chars whose record has an existing source
path), backed by a code span in backticks (or a path plus a symbol, or a code-like indexed symbol),
and no hedge, question, plan, edit summary (change verbs) or code fence. Findings whose paths are all
covered by non-stale index records that carry `sources` are skipped. Findings on modified/untracked
files are queued via nelly_pending.add instead of prompting. Marker (<local state dir>/stop-capture
.json): {session_id: {hashes, paths, blocks}}: never the same answer or path twice, at most 2 blocks per
session. Silent (exit 0, no output) on: stop_hook_active, NELLY_CAPTURE=off, plan mode, no answer text,
oversized answer (> 30,000 chars), no real user prompt found (fail closed), a prompt saying not to
save to memory, bad input, a non-git cwd, or any error (fail-open). Contract: INTEROP.md "Source evidence,
staleness, capture and safe writes".
"""
import hashlib
import json
import os
import re
import subprocess
import sys
import time

_here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _here)
sys.path.insert(0, os.path.join(_here, "..", "scripts"))
try:
    import nelly_memory  # noqa: E402
    import nelly_pending  # noqa: E402
    import nelly_store  # noqa: E402
    import shared_slug  # noqa: E402
    from build_index import _read_index  # noqa: E402
except Exception:  # e.g. CLAUDE_PLUGIN_DATA unset: fail open (main() exits 0 silently)
    nelly_memory = None

MAX_CHARS = 30000
SCAN_SECONDS = 1.5
MARKER_SESSIONS = 20
_GIT_TIMEOUT = 2
_TAIL_SIZES = (262144, 2097152)
MAX_BLOCKS = 2

_VERB = re.compile(r"\b(?:writes|calls|returns|routes|validates|persists|reads|stores|emits|raises|"
                   r"loads|parses|registers|handles)\b", re.I)
_HEDGE = re.compile(r"\b(?:may|might|could|should|probably|possibly|perhaps|unverified|likely|seems?)\b"
                    r"|hypothes", re.I)
_PLAN = re.compile(r"^\s*(?:[-*]\s+)?(?:I will\b|I'll\b|Next:|Let me\b|We should\b)", re.I)
_CHANGE = re.compile(r"\b(?:updated|fixed|changed|added|removed|renamed|refactored|moved|now)\b", re.I)
_EDIT_VERBS = ("updated|fixed|changed|added|removed|renamed|refactored|moved|implemented|wrote|created|"
               "deleted|replaced")
_EDIT_SUMMARY = re.compile(r"^\s*(?:[-*]\s+)?(?:(?:I|we)\s+(?:have\s+)?(?:" + _EDIT_VERBS + r")\b"
                           r"|(?:Created|Edited|Implemented|Replaced|Deleted|Wrote)\b)", re.I)
_CMD_TAG = re.compile(r"<command-(name|args)>(.*?)</command-\1>", re.S)
_SPAN = re.compile(r"`[^`\n]+`")
_CODEISH = re.compile(r"^(?:[A-Z][a-z0-9]+[A-Z]\w*|\w*_\w*)$")
_META_PREFIXES = ("Stop hook feedback", "Another Claude session", "Base directory for this skill",
                  "[SYSTEM NOTIFICATION")
_TOKEN = re.compile(r"[A-Za-z0-9_./\\-]+")
_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]{3,}")
_NO_SAVE = re.compile(r"\b(?:do\s*n[o'’]?t|don[’']?t|do not|never|no need to|without)\b[^.;!\n]{0,40}?"
                      r"\b(?:sav|record|remember|stor|persist)|\bno memory\b", re.I)


def _git(cwd, *args):
    env = {k: v for k, v in os.environ.items() if k not in ("GIT_DIR", "GIT_WORK_TREE")}
    try:
        r = subprocess.run(["git", "-C", cwd, *args], capture_output=True, text=True, errors="replace",
                           timeout=_GIT_TIMEOUT, env=env)
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout if r.returncode == 0 else None


def _events(transcript_path, tail_bytes):
    """Events from the last tail_bytes of a JSONL transcript; (events, whole_file_read)."""
    try:
        with open(transcript_path, "rb") as fh:
            fh.seek(0, 2)
            size = fh.tell()
            start = max(0, size - tail_bytes)
            fh.seek(start)
            raw = fh.read()
    except OSError:
        return [], True
    lines = raw.split(b"\n")
    if start > 0:
        lines = lines[1:]  # partial first line
    out = []
    for line in lines:
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        if isinstance(ev, dict):
            out.append(ev)
    return out, start == 0


def _text_of(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(c.get("text", "") for c in content
                         if isinstance(c, dict) and c.get("type") == "text" and c.get("text"))
    return ""


def _prompt_text(ev, content, text):
    """The user's prompt text for this event, or "" when it is not typed by the human (meta, tool
    result, injected hook/skill text). A slash command is stored as <command-name>/<command-args>
    tags: its name and args are the prompt."""
    if ev.get("isMeta") or not text:
        return ""
    if isinstance(content, str) and text.startswith("<"):
        tags = dict(_CMD_TAG.findall(text))
        return " ".join(v.strip() for k, v in (("name", tags.get("name", "")), ("args", tags.get("args", "")))
                        if v.strip())
    return "" if text.startswith(_META_PREFIXES) else text


def extract_turn(transcript_path):
    """(last assistant text, last real user prompt text); the prompt is "" when none is found. Reads
    the tail in growing chunks until a prompt shows up. Assistant extraction pattern copied from
    code-reviewer's pre_push_offer.py to stay self-contained."""
    answer, prompt = "", ""
    for size in _TAIL_SIZES:
        events, whole = _events(transcript_path, size)
        answer, prompt = "", ""
        for ev in events:
            msg = ev.get("message") if isinstance(ev.get("message"), dict) else None
            role = ev.get("type") or (msg.get("role") if msg else "")
            content = msg.get("content") if msg else ev.get("content")
            text = _text_of(content).strip()
            if role == "assistant" and text:
                answer = text
            elif role == "user":
                prompt = _prompt_text(ev, content, text) or prompt
        if prompt or whole:
            break
    return answer, prompt


def _clean_token(tok):
    tok = tok.strip("`'\"()[]{}<>,;:*").rstrip(".")
    tok = re.sub(r":\d+(?::\d+)?$", "", tok)
    return tok


def _existing_rel(repo_root, tok):
    """Repo-relative path if tok names an existing file inside repo_root (absolute tokens count only
    when inside the repo), else None."""
    tok = _clean_token(tok)
    if not tok or tok.startswith(("\\", "~")) or ".." in tok.split("/"):
        return None
    if "/" not in tok and not re.search(r"\.\w{1,6}$", tok):
        return None
    try:
        root = os.path.realpath(repo_root)
        real = os.path.realpath(tok if os.path.isabs(tok) else os.path.join(repo_root, tok))
        if os.path.commonpath([real, root]) != root or not os.path.isfile(real):
            return None
        return os.path.relpath(real, root) if os.path.isabs(tok) else tok
    except (OSError, ValueError):
        return None


def _symbol_map(repo_root, index_records):
    """{symbol (>= 4 chars): [existing source paths]} from index records."""
    out = {}
    for rec in index_records or []:
        if not isinstance(rec, dict):
            continue
        syms = [s for s in (rec.get("symbols") or []) if isinstance(s, str) and len(s) >= 4]
        if not syms:
            continue
        srcs = [s.get("path") for s in (rec.get("sources") or []) if isinstance(s, dict)]
        srcs += [f for f in (rec.get("files") or []) if isinstance(f, str)]
        paths = [p for p in dict.fromkeys(srcs) if isinstance(p, str) and _existing_rel(repo_root, p)]
        if paths:
            for s in syms:
                out.setdefault(s, [])
                out[s] += [p for p in paths if p not in out[s]]
    return out


def _qualifies(line, paths, syms):
    """Backticked span plus a path or indexed symbol; or a path plus a symbol; or a code-like
    (CamelCase / snake_case) indexed symbol on its own."""
    if not paths and not syms:
        return False
    if _SPAN.search(line) or (paths and syms):
        return True
    return any(_CODEISH.match(s) for s in syms)


def find_findings(text, repo_root, index_records):
    """[{line, paths, symbols}] for source-linked finding lines (see module docstring)."""
    deadline = time.monotonic() + SCAN_SECONDS
    symbols = _symbol_map(repo_root, index_records)
    found, fenced = [], False
    for raw in text.splitlines():
        if time.monotonic() > deadline:
            break
        line = raw.strip()
        if line.startswith("```"):
            fenced = not fenced
            continue
        if fenced or not line or "?" in line or _HEDGE.search(line) or _PLAN.match(line):
            continue
        if _CHANGE.search(line) or _EDIT_SUMMARY.match(line):
            continue
        if not _VERB.search(line):
            continue
        paths = []
        for tok in _TOKEN.findall(line):
            rel = _existing_rel(repo_root, tok)
            if rel and rel not in paths:
                paths.append(rel)
        syms = [s for s in dict.fromkeys(_IDENT.findall(line)) if s in symbols]
        if not _qualifies(line, paths, syms):
            continue
        for s in syms:
            paths += [p for p in symbols[s] if p not in paths]
        found.append({"line": line, "paths": paths, "symbols": syms})
    return found


def _recorded_paths(records):
    """Paths covered by a non-stale record that carries `sources`."""
    out = set()
    for rec in records or []:
        if not isinstance(rec, dict) or rec.get("stale"):
            continue
        for src in rec.get("sources") or []:
            if isinstance(src, dict) and isinstance(src.get("path"), str):
                out.add(src["path"])
    return out


def _dirty_status(repo_root, paths):
    """{path: True (modified/untracked) | False (clean) | None (could not be determined)}. One batched
    `git status`; when that fails, one call per path."""
    def run(group):
        out = _git(repo_root, "status", "--porcelain", "-z", "--untracked-files=all", "--", *group)
        if out is None:
            return None
        dirty, entries, i = set(), out.split("\0"), 0
        while i < len(entries):
            e = entries[i]
            i += 1
            if len(e) > 3:
                dirty.add(e[3:])
                if e[0] in "RC":
                    i += 1  # the original path of a rename/copy follows
        return dirty

    paths = list(dict.fromkeys(paths))
    dirty = run(paths)
    if dirty is not None:
        return {p: p in dirty for p in paths}
    result = {}
    for p in paths:
        one = run([p])
        result[p] = None if one is None else p in one
    return result


def _marker_path(root):
    return os.path.join(nelly_memory.local_state_dir(root), "stop-capture.json")


def _load_marker(root):
    try:
        with open(_marker_path(root), encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _session_state(state, session):
    cur = state.get(session)
    if not isinstance(cur, dict):
        cur = {}
    return {"hashes": list(cur.get("hashes", [])), "paths": list(cur.get("paths", [])),
            "blocks": int(cur.get("blocks", 0))}


def _save_marker(root, state, session, entry):
    state.pop(session, None)
    state[session] = entry
    while len(state) > MARKER_SESSIONS:
        state.pop(next(iter(state)))
    nelly_store.atomic_write(_marker_path(root), json.dumps(state))


def _reason(root, findings):
    lines = ["agent-nelly: your answer states a source-linked finding that is not recorded in memory:"]
    for f in findings[:3]:
        quote = f["line"] if len(f["line"]) <= 200 else f["line"][:197] + "..."
        lines.append(f"- {', '.join(f['paths'])}: \"{quote}\"")
    paths = list(dict.fromkeys(p for f in findings[:3] for p in f["paths"]))
    cmd = nelly_pending.record_cmd(root, paths, "<one-line finding>", "<one-paragraph finding>")
    lines.append(f"Make ONE brief recording pass: run {cmd} (or use agent-nelly). Keep your original "
                 "answer unchanged, do not broaden the task, and do not repeat this pass.")
    return "\n".join(lines)


def _run(payload):
    if payload.get("stop_hook_active"):
        return
    if os.environ.get("NELLY_CAPTURE", "").strip().lower() == "off":
        return
    if payload.get("permission_mode") == "plan":
        return
    cwd = payload.get("cwd") or os.getcwd()
    transcript = payload.get("transcript_path")
    answer, prompt = "", ""
    if isinstance(transcript, str) and transcript:
        answer, prompt = extract_turn(transcript)
    if not prompt:
        return  # no real user prompt found: fail closed
    msg = payload.get("last_assistant_message")
    if isinstance(msg, str) and msg.strip():
        answer = msg.strip()
    if not answer or len(answer) > MAX_CHARS:
        return
    if _NO_SAVE.search(prompt):
        return
    if not _VERB.search(answer) or not (_SPAN.search(answer) or "/" in answer or "_" in answer
                                        or re.search(r"[A-Z][a-z0-9]+[A-Z]", answer)):
        return  # cheap exit before any git call or marker read
    root = shared_slug.repo_root(cwd, require_git=True)
    if not root:
        return
    session = str(payload.get("session_id") or "")
    digest = hashlib.sha256(answer.encode("utf-8")).hexdigest()
    marker = _load_marker(root)
    entry = _session_state(marker, session)
    if digest in entry["hashes"] or entry["blocks"] >= MAX_BLOCKS:
        return
    records = _read_index(os.path.join(nelly_memory.memory_dir(root), "nelly-index.json"))
    if not isinstance(records, list):
        records = []
    recorded = _recorded_paths(records)
    asked = set(entry["paths"])
    findings = [f for f in find_findings(answer, root, records)
                if not all(p in recorded for p in f["paths"]) and not all(p in asked for p in f["paths"])]
    if not findings:
        return
    status = _dirty_status(root, [p for f in findings for p in f["paths"]])
    clean = []
    for f in findings:
        states = [status.get(p) for p in f["paths"]]
        if any(st is None for st in states):
            continue  # status undetermined: drop only this finding
        if any(states):
            try:
                nelly_pending.add(root, f["line"], f["paths"][:12], f["symbols"][:20], "uncommitted")
            except (ValueError, OSError):
                pass
        else:
            clean.append(f)
    if not clean:
        return
    entry["hashes"].append(digest)
    entry["paths"] = list(dict.fromkeys(entry["paths"] + [p for f in clean for p in f["paths"]]))
    entry["blocks"] += 1
    _save_marker(root, marker, session, entry)
    print(json.dumps({"decision": "block", "reason": _reason(root, clean)}))


def main():
    if nelly_memory is None:
        return 0
    try:
        _run(json.load(sys.stdin))
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
