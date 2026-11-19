#!/usr/bin/env python3
"""resume_context hook (UserPromptSubmit). On a resume prompt (/isdd, /isdd-continue, or
"continue"/"resume" + the active feature slug) with an active workflow, injects additionalContext:
baseline diff, carried-forward research labels (still-applicable / needs-recheck / unknown), an
intent hash check and any rollback_pending. Total work stays well under the hook's 5s timeout.
Never blocks the prompt: any error -> exit 0, no output (fail open)."""
import hashlib
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import sdd_state  # noqa: E402

try:
    import baseline  # noqa: E402
except Exception:  # pragma: no cover
    baseline = None
try:
    import research_cache  # noqa: E402
except Exception:  # pragma: no cover
    research_cache = None

TOTAL_BUDGET_S = 4.0
MIN_CLASSIFY_S = 0.5
_CMD = re.compile(r"^\s*/(?:agent-isdd:)?(?:isdd\s*$|isdd-continue\b)", re.I)
_WORDS = re.compile(r"\b(?:continue|resume)\b", re.I)
_ANCHOR = re.compile(r"^## Intent Anchor\b.*?(?=^## |\Z)", re.M | re.S)
_FENCE = re.compile(r"```json\s*\n(.*?)```", re.S)
_BULLET = re.compile(r"^\s*[-*]\s*`?path:\s*(\S+?)`?[,;]?\s+git_hash:\s*`?([^`\n]*?)`?\s*$", re.M)


def is_resume_prompt(prompt, slug):
    if not isinstance(prompt, str) or not prompt.strip():
        return False
    if _CMD.match(prompt):
        return True
    return bool(_WORDS.search(prompt)) and bool(slug) and slug.lower() in prompt.lower()


def _paths(p):
    return ", ".join(str(x.get("path") or x.get("summary") or "?") for x in p)


def format_context(base, classified, intent_msg, rollback, slug=None):
    """Assemble the context text; None when there is nothing to say."""
    lines = []
    base = base if isinstance(base, dict) else None
    incomplete = bool(base and base.get("incomplete"))
    if base is not None:
        parts = []
        if base.get("branch_changed"):
            parts.append("branch changed: %s -> %s" % tuple(base["branch_changed"]))
        if base.get("head_moved"):
            parts.append("HEAD moved: %s -> %s" % tuple(c[:10] for c in base["head_moved"]))
        if base.get("files_changed"):
            parts.append("files changed: " + ", ".join(base["files_changed"][:20]))
        if incomplete:
            parts.append("diff incomplete (treating carried-forward items as unknown)")
        lines.append("Since the implementation baseline: " + ("; ".join(parts) if parts else "no changes"))
    if classified:
        c = {k: list(classified.get(k) or []) for k in ("still_applicable", "needs_recheck", "unknown")}
        if incomplete:
            c = {"still_applicable": [], "needs_recheck": [],
                 "unknown": c["still_applicable"] + c["needs_recheck"] + c["unknown"]}
        for key, label in (("still_applicable", "still-applicable"), ("needs_recheck", "needs-recheck"),
                           ("unknown", "unknown")):
            if c[key]:
                lines.append("Carried-forward research %s: %s" % (label, _paths(c[key])))
    if intent_msg:
        lines.append(intent_msg)
    if rollback:
        r = rollback if isinstance(rollback, dict) else {}
        lines.append("rollback_pending: target=%s reason=%s source=%s -- handle before continuing."
                     % (r.get("target"), r.get("reason"), r.get("source")))
    if not lines:
        return None
    return "SDD resume context%s:\n" % (" (%s)" % slug if slug else "") + "\n".join("- " + ln for ln in lines)


def intent_repro_hash(text):
    """sha256 of intent.md with the `## Intent Anchor` section removed (line endings normalised,
    stripped), so the hash is reproducible regardless of the embedded anchor ID."""
    t = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    return hashlib.sha256(_ANCHOR.sub("", t).strip().encode("utf-8")).hexdigest()


def _intent_message(feature_dir, state_json, state_json_path):
    try:
        with open(os.path.join(feature_dir, "intent", "intent.md"), encoding="utf-8") as fh:
            current = intent_repro_hash(fh.read())
    except OSError:
        return None
    stored = state_json.get("intent_hash_repro")
    if not stored:
        sdd_state.update_json(state_json_path, lambda d: dict(d, intent_hash_repro=current))
        return None
    if stored != current:
        return "Intent changed since the first resume recorded it (intent/intent.md differs); re-check alignment."
    return None


def _summaries(feature_dir):
    """File summaries from research/cache.md: a fenced json list of {path, git_hash}, or bullet
    lines `- path: ... git_hash: ...`. A git_hash of 'not captured'/missing counts as unknown."""
    try:
        with open(os.path.join(feature_dir, "research", "cache.md"), encoding="utf-8") as fh:
            text = fh.read()
    except OSError:
        return []
    out = []
    for m in _FENCE.finditer(text):
        try:
            data = json.loads(m.group(1))
        except ValueError:
            continue
        if isinstance(data, dict):
            data = data.get("file_summaries")
        if isinstance(data, list):
            out += [x for x in data if isinstance(x, dict) and x.get("path")]
    if not out:
        for m in _BULLET.finditer(text):
            gh = m.group(2).strip()
            ok = re.fullmatch(r"[0-9a-fA-F]{7,64}", gh)
            out.append({"path": m.group(1), "git_hash": gh if ok else None})
    return out


def build_context(payload):
    """Context string injected on UserPromptSubmit, or None."""
    t0 = time.monotonic()
    left = lambda: TOTAL_BUDGET_S - (time.monotonic() - t0)  # noqa: E731
    cwd = payload.get("cwd") or os.getcwd()
    state_md = sdd_state.active_state_file(cwd)
    if not state_md:
        return None
    feature_dir = os.path.dirname(state_md)
    slug = os.path.basename(feature_dir)
    if not is_resume_prompt(payload.get("prompt"), slug):
        return None
    state_json_path = os.path.join(feature_dir, "workflow-state.json")
    state_json = sdd_state.parse_state_json(state_json_path)
    if not isinstance(state_json, dict):
        state_json = {}

    base = None
    if state_json.get("baseline") and baseline is not None and left() >= 3.2:
        base = baseline.diff(cwd, state_json_path)
    classified = None
    summaries = _summaries(feature_dir)
    if summaries and research_cache is not None and left() >= MIN_CLASSIFY_S:
        try:
            classified = research_cache.classify_summaries(
                summaries, cwd, deadline_s=min(1.5, left()))
        except Exception:
            classified = None
    elif summaries:
        classified = {"still_applicable": [], "needs_recheck": [], "unknown": summaries}
    return format_context(base, classified, _intent_message(feature_dir, state_json, state_json_path),
                          state_json.get("rollback_pending"), slug)


def evaluate(payload):
    return build_context(payload)


def main():
    try:
        payload = json.load(sys.stdin)
    except (ValueError, OSError):
        payload = {}
    try:
        ctx = evaluate(payload if isinstance(payload, dict) else {})
        if ctx:
            sys.stdout.write(json.dumps({"hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit", "additionalContext": ctx}}))
    except Exception:
        pass
    sys.exit(0)


if __name__ == "__main__":
    main()
