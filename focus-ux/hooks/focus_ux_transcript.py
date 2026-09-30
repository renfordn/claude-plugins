"""Transcript helpers and checkpoint marker parsing for focus-ux hooks (stdlib only).

Nothing here raises on bad input: unreadable transcripts give "" and malformed markers give None.
"""
import json
import os
import re

TAIL_BYTES = 16384
# A final line longer than TAIL_BYTES leaves no complete line in the first window, so the read
# doubles the window until it holds one, up to this cap (a line beyond it reads as empty).
MAX_TAIL_BYTES = 1024 * 1024
# _raw_session_title scans forward from the start of the transcript (a title can be set once
# near session start and never changed again, unlike last_assistant_text's "only the tail
# matters"), so it can't reuse TAIL_BYTES's tail-window bound. It still needs *some* cap so an
# unbounded transcript can't force an unbounded read (review New-F4); 8 MB is generous enough
# to cover ordinary sessions while capping the pathological case.
TITLE_SCAN_BYTES = 8 * 1024 * 1024


def _tail_last_assistant_text(transcript_path, tail_bytes=TAIL_BYTES):
    """Last assistant text block in the transcript's tail.

    Copied (not imported) from agent-isdd/hooks/subagent_report.py extract_last_assistant_text.
    """
    try:
        with open(transcript_path, "rb") as fh:
            fh.seek(0, 2)
            size = fh.tell()
            while True:
                start = max(0, size - tail_bytes)
                fh.seek(start)
                raw = fh.read()
                lines = raw.split(b"\n")
                if start > 0:
                    lines = lines[1:]  # drop the partial first line left by a mid-line seek
                if start == 0 or any(ln.strip() for ln in lines) or tail_bytes >= MAX_TAIL_BYTES:
                    break
                tail_bytes = min(tail_bytes * 2, MAX_TAIL_BYTES)
    except (OSError, TypeError, ValueError):
        return ""

    blocks = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            ev = json.loads(line)
        except (json.JSONDecodeError, ValueError):
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
            parts = [c.get("text", "") for c in content
                     if isinstance(c, dict) and c.get("type") == "text"]
            joined = "\n".join(p for p in parts if p)
            if joined:
                blocks.append(joined)
    return blocks[-1].strip() if blocks else ""


def last_assistant_text(payload):
    """Prefer the Stop payload's last_assistant_message (the transcript may lag)."""
    msg = payload.get("last_assistant_message") if isinstance(payload, dict) else None
    if isinstance(msg, str) and msg:
        return msg
    path = payload.get("transcript_path") if isinstance(payload, dict) else None
    return _tail_last_assistant_text(path) if path else ""


def _raw_session_title(transcript_path, cwd):
    """Latest string `customTitle` in the transcript, else the cwd basename, else "".

    Unsanitized -- callers must go through session_title(), never this directly (F2).
    """
    title = None
    if transcript_path:
        try:
            with open(transcript_path, "rb") as fh:
                for line in fh:
                    if fh.tell() > TITLE_SCAN_BYTES:
                        break
                    if b"customTitle" not in line:
                        continue
                    try:
                        ev = json.loads(line)
                    except (json.JSONDecodeError, ValueError):
                        continue
                    if isinstance(ev, dict) and isinstance(ev.get("customTitle"), str):
                        title = ev["customTitle"]
        except (OSError, TypeError, ValueError):
            pass
    if title:
        return title
    return os.path.basename(os.path.normpath(cwd)) if cwd else ""


# --- checkpoint markers (SDD design doc, outside this repo: Data Contracts And Interfaces) ---------------------------
# Producer: <!--CHECKPOINT:type=(input|gate|done|step) name="<[a-z0-9:_-]{1,48}>" need="<...>"-->
# Ack:      <!--CHECKPOINT-PUSHED:type=(...|none) id="<...>" nonce="<hex8>" [reason="..."]-->
# The marker body ends at the first "-->", so a "-->" inside a field makes the marker malformed.
#
# Extraction is a bounded linear str.find() walk, not a lazy-DOTALL regex findall: the regex
# version is O(n^2) on adversarial input -- many unterminated "<!--CHECKPOINT" prefixes each
# force a fresh forward scan for the (possibly absent, possibly very distant) "-->" (measured
# 42.7s on ~1MB of unterminated prefixes). This hook runs on untrusted transcript/assistant
# text inside the Stop hook, so that's a real DoS path (review finding F1). The walk below
# bounds both the total text considered (MARKER_SCAN_CHARS, matching the tail-read bound used
# elsewhere) and each candidate marker's search window for its closing "-->"
# (MARKER_MAX_BODY), so worst-case cost is linear in MARKER_SCAN_CHARS regardless of input
# shape.
_PRODUCER_PREFIX = "<!--CHECKPOINT:"
_ACK_PREFIX = "<!--CHECKPOINT-PUSHED:"
_MARKER_SUFFIX = "-->"
MARKER_SCAN_CHARS = 16384
MARKER_MAX_BODY = 512

_PRODUCER_BODY_RE = re.compile(
    r'type=(input|gate|done|step) name="([a-z0-9:_-]{1,48})" need="([^"]*)"'
    r'(?: [A-Za-z_]+="[^"]*")*'  # extra fields are tolerated and dropped
)
_ACK_BODY_RE = re.compile(
    r'type=(input|gate|done|step|none) id="([a-z0-9:_-]{1,48})" nonce="([0-9a-f]{8})"'
    r'(?: reason="(duplicate|unavailable|routine)")?'
)
_DISALLOWED = re.compile(r"[^\w .,:'-]")
NEED_MAX = 80
TITLE_MAX = 48


def _clean(s, cap):
    return _DISALLOWED.sub("", s)[:cap]


def sanitize_title(s):
    """Allow-list [\\w .,:'-], disallowed characters removed, capped at 48 chars."""
    return _clean(s if isinstance(s, str) else "", TITLE_MAX)


def session_title(transcript_path, cwd):
    """Sanitized session title: the public entry point. Always safe to embed in a reason/prompt
    (F2) -- there is no unsanitized path to this value outside the module."""
    return sanitize_title(_raw_session_title(transcript_path, cwd))


def _iter_marker_bodies(text, prefix):
    """Yield each `prefix ... "-->"` body substring in `text`, left to right, in one linear
    pass. A marker whose closing "-->" doesn't appear within MARKER_MAX_BODY chars (unterminated,
    or just too long) is skipped by moving past its prefix and resuming the search from there,
    not by re-scanning the rest of the text (that's what keeps this linear -- see the
    module-level note on F1). One side effect: a genuine, well-formed marker that follows a
    too-long/unterminated one is still found -- it isn't swallowed by the earlier one, unlike a
    naive lazy-DOTALL scan. A marker that *does* close within the window but whose body is
    otherwise malformed is still yielded raw; the caller's regex validates it and returns None
    for it (see test_checkpoint_markers.py's malformed-body cases)."""
    if not isinstance(text, str):
        return
    if len(text) > MARKER_SCAN_CHARS:
        text = text[-MARKER_SCAN_CHARS:]
    pos = 0
    while True:
        start = text.find(prefix, pos)
        if start == -1:
            return
        body_start = start + len(prefix)
        window_end = min(len(text), body_start + MARKER_MAX_BODY)
        end = text.find(_MARKER_SUFFIX, body_start, window_end)
        if end == -1:
            pos = start + 1  # unterminated or oversized body -- keep scanning, don't rescan it
            continue
        yield text[body_start:end]
        pos = end + len(_MARKER_SUFFIX)


def _last_body(prefix, text):
    body = None
    for candidate in _iter_marker_bodies(text, prefix):
        body = candidate
    return body.strip() if body is not None else None


def parse_producer(text):
    """Last producer marker as {type, name, need}; None when absent or malformed."""
    body = _last_body(_PRODUCER_PREFIX, text)
    m = _PRODUCER_BODY_RE.fullmatch(body) if body is not None else None
    if not m:
        return None
    return {"type": m.group(1), "name": m.group(2), "need": _clean(m.group(3), NEED_MAX)}


def parse_ack(text):
    """Last ack marker as {type, id, nonce, reason}; None when absent or malformed."""
    body = _last_body(_ACK_PREFIX, text)
    m = _ACK_BODY_RE.fullmatch(body) if body is not None else None
    if not m:
        return None
    return {"type": m.group(1), "id": m.group(2), "nonce": m.group(3), "reason": m.group(4)}
