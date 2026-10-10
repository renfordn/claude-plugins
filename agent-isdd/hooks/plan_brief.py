"""Plan Board brief builder: derive a feature's brief from its state files, no model involved.

`parse_brief(feature_dir, state_fields)` reads requirements.md, design.md, tasks.md and recap.md
beside workflow-state.md by heading and returns a plain dict. Stdlib only; never raises; a
missing or unparsable file just omits its section.
"""
import json
import os
import re

_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
_ITEM = re.compile(r"^\s*[-*]\s+(?:\[([ xX])\]\s*)?(\S.*?)\s*$")


def _read(path):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read()
    except (OSError, ValueError):
        return None


def _sections(text, *names):
    """[(heading, body lines)] for every `##`/`###` section whose heading matches `names`."""
    wanted = {n.lower() for n in names}
    found, cur, level = [], None, 0
    for line in text.splitlines():
        m = _HEADING.match(line)
        if m and len(m.group(1)) <= 3:
            if cur is not None and len(m.group(1)) <= level:
                cur = None
            if cur is None and len(m.group(1)) >= 2 and m.group(2).strip().lower() in wanted:
                cur, level = (m.group(2).strip(), []), len(m.group(1))
                found.append(cur)
            continue
        if cur is not None:
            cur[1].append(line)
    return found


def _section(text, *names):
    """Body lines of the first section matching one of `names` (case-insensitive)."""
    found = _sections(text, *names)
    return found[0][1] if found else []


def _items(lines, open_only=False):
    out = []
    for line in lines:
        m = _ITEM.match(line)
        if m and not (open_only and (m.group(1) or "").lower() == "x"):
            out.append(m.group(2))
    return out


def _state(lines):
    for line in lines:
        m = re.match(r"^\s*[-*]\s*State:\s*(\S.*?)\s*$", line)
        if m:
            return m.group(1)
    return ""


def _requirements(text):
    status = _state(_section(text, "Status"))
    if not status:
        return None
    return {"state": status, "openGaps": _items(_section(text, "Open Gaps"), open_only=True)}


def _design(text):
    state = _state(_section(text, "Status"))
    if not state:
        return None
    summary = " ".join(l.strip() for l in _section(text, "Design Summary") if l.strip())
    risks = _items(_section(text, "Risks And Tradeoffs", "Risks / Tradeoffs", "Risks", "Risks & Tradeoffs"))
    return {"state": state, "summary": summary, "risks": [{"text": r} for r in risks],
            "openQuestions": _items(_section(text, "Open Questions"), open_only=True)}


def _slices(text, state_path, closed=False):
    items, cur = [], None
    for line in text.splitlines():
        m = re.match(r"^##\s+Slice\s+(\d+)\s*:\s*(.*?)\s*$", line)
        if m:
            cur = {"n": int(m.group(1)), "title": m.group(2), "tier": ""}
            items.append(cur)
            continue
        t = re.match(r"^\*\*Risk Tier:\*\*\s*(\S+)", line)
        if t and cur is not None and not cur["tier"]:
            cur["tier"] = t.group(1)
    if not items:
        return None
    # A closed feature has implemented every slice, so its count never depends on a progress file
    # that nothing may have written (only the direct-implementation fallback writes it; agent-TDD keeps its own progress in tdd-progress.json).
    done = len(items) if closed else None
    raw = None if closed else _read(state_path)
    if raw:
        try:
            done = sum(1 for s in json.loads(raw).get("slices", []) if isinstance(s, dict) and s.get("status") == "done")
        except (ValueError, AttributeError, TypeError):
            done = None
    elif done is None:
        # agent-TDD's path: reports recorded per feature by subagent_report.py (impl_progress).
        import impl_progress
        prog = impl_progress.summary(os.path.dirname(state_path))
        if prog:
            done = len(items) if prog["allComplete"] else min(prog["done"], len(items))
    return {"total": len(items), "done": done, "items": items}


def _recap(text):
    out = {}
    decisions = _items(_section(text, "Decisions Made", "Decisions"))
    if decisions:
        out["decisions"] = decisions
    open_items = [{"kind": name, "text": t}
                  for name, body in _sections(text, "Open Items", "Open Questions", "Technical Debt", "Risks")
                  for t in _items(body, open_only=True)]
    if open_items:
        out["openItems"] = open_items
    return out


BRIEF_CAP = 6000  # bytes of brief JSON; leaves room for the status fields inside the 8 KB record
_LEVELS = ((160, 8), (120, 8), (80, 6), (60, 4), (40, 3), (30, 2), (20, 1))


def _clip(value, limit):
    value = re.sub(r"\s+", " ", value).strip()
    return value if len(value) <= limit else value[: limit - 1].rstrip() + "…"


def _cap(node, item_len, count, key=""):
    """Clip every string to `item_len` (summary and goal get more room) and every list to `count`."""
    if isinstance(node, str):
        return _clip(node, item_len * 2 if key in ("summary", "goal") else item_len)
    if isinstance(node, list):
        return [_cap(v, item_len, count) for v in node[:count]]
    if isinstance(node, dict):
        return {k: _cap(v, item_len, count, k) for k, v in node.items()}
    return node


def _fit(brief):
    for item_len, count in _LEVELS:
        capped = _cap(brief, item_len, count)
        if len(json.dumps(capped)) <= BRIEF_CAP:
            return capped
    return capped  # smallest level; sections are never dropped


def parse_brief(feature_dir, state_fields):
    brief = {"goal": (state_fields or {}).get("goal", "")}
    path = lambda *p: "/".join((feature_dir, *p))  # noqa: E731
    text = _read(path("requirements", "requirements.md"))
    if text:
        req = _requirements(text)
        if req:
            brief["requirements"] = req
    text = _read(path("design", "design.md"))
    if text:
        design = _design(text)
        if design:
            brief["design"] = design
    text = _read(path("tasks", "tasks.md"))
    if text:
        fields = state_fields or {}
        closed = "complete" in ((fields.get("workflow status") or "").strip().lower(),
                                (fields.get("current phase") or "").strip().lower())
        slices = _slices(text, path("direct-mode-state.json"), closed)
        if slices:
            brief["slices"] = slices
    text = _read(path("recap", "recap.md"))
    if text:
        brief.update(_recap(text))
    return _fit(brief)
