#!/usr/bin/env python3
"""Validate a visual-brief JSON file and build its page, or build the Brief Board page.

One page (`assets/brief-board.html`) renders briefs. With a brief embedded it shows that brief on
its own; with none it becomes the Brief Board, which reads every brief from its Artifact database
(collection `briefs`). Claude only ever writes the small JSON below, never HTML.

Usage:
    python3 build_brief.py brief.json out.html     # validate, then a standalone page
    python3 build_brief.py --check brief.json      # validate only (before a board write)
    python3 build_brief.py --board out.html        # the Brief Board page (publish once)

JSON shape (only title and headline are required):
    {
      "title": "Plugin Test Audit",                  # 2-4 word name (rail + page title)
      "project": "Claude-Plugins",                   # board: groups/filters briefs
      "createdAt": "2026-09-25T14:05:00Z",           # board: sort order (set on write)
      "eyebrow": "Test-suite audit · 7 suites · 696 tests",
      "headline": "Fix the 3 isdd flakies and CI goes green.",
      "lede": "One or two sentences of context.",
      "stats": [{"text": "3 flaky tests", "tone": "high|med|low|info|ok|now"}],
      "progress": {"label": "Plan · Phase 2/4",
                   "phases": [{"name": "...", "status": "done|current|pending|blocked", "note": "..."}]},
      "points": ["top key point", "..."],            # 3-5
      "sections": [
        {"type": "findings", "title": "...", "items": [{"severity": "high|med|low|info", "title": "...", "detail": "...", "where": "file:line", "sowhat": "..."}]},
        {"type": "grid",     "title": "...", "rowHeader": "Suite", "columns": ["..."], "rows": [{"name": "...", "flag": "start here", "cells": [{"text": "3 flaky", "tone": "high"}]}]},
        {"type": "matrix",   "title": "...", "columns": ["..."], "rows": [{"name": "...", "pick": true, "cells": [{"verdict": "yes|no|warn|na", "text": "..."}]}]},
        {"type": "timeline", "title": "...", "items": [{"when": "Sep 24", "title": "...", "status": "done|current|pending|blocked", "note": "..."}]},
        {"type": "bars",     "title": "...", "unit": "s", "items": [{"label": "...", "value": 41, "highlight": true}]},
        {"type": "diagram",  "title": "...", "mermaid": "flowchart LR\\n  A-->B", "caption": "..."},
        {"type": "text",     "title": "...", "body": "paragraphs separated by a blank line"},
        {"type": "list",     "title": "...", "items": ["..."]},
        {"type": "details",  "title": "...", "body": "..."}          # always collapsed
      ],                                             # any section may add "collapsed": true
      "next": {"recommendation": "...", "options": ["..."]}
    }

Text fields accept `code` and **bold**. Exit status: 0 ok, 2 invalid data (message on stderr).
"""
import html
import json
import sys
from pathlib import Path

PAGE = Path(__file__).resolve().parent.parent / "assets" / "brief-board.html"
STATUSES = {"done", "current", "pending", "blocked"}
SEVERITIES = {"high", "med", "low", "info"}
TONES = SEVERITIES | {"ok", "now"}
VERDICTS = {"yes", "no", "warn", "na"}


class BriefError(ValueError):
    pass


def _need(obj, key, where):
    if not isinstance(obj, dict) or obj.get(key) in (None, "", []):
        raise BriefError(f"{where}: missing '{key}'")
    return obj[key]


def _choice(value, allowed, field, where):
    if value not in allowed:
        raise BriefError(f"{where}: {field} '{value}' must be one of {sorted(allowed)}")


def _items(s, where):
    items = _need(s, "items", where)
    if not isinstance(items, list):
        raise BriefError(f"{where}: 'items' must be a list")
    return items


def _rows(s, where):
    cols = _need(s, "columns", where)
    for i, row in enumerate(_need(s, "rows", where)):
        w = f"{where}.rows[{i}]"
        _need(row, "name", w)
        cells = row.get("cells") or []
        if len(cells) != len(cols):
            raise BriefError(f"{w}: has {len(cells)} cells, needs {len(cols)} (one per column)")
        yield w, cells


def _findings(s, where):
    for i, it in enumerate(_items(s, where)):
        w = f"{where}.items[{i}]"
        _need(it, "title", w)
        _choice(it.get("severity", "info"), SEVERITIES, "severity", w)


def _grid(s, where):
    for w, cells in _rows(s, where):
        for j, c in enumerate(cells):
            if isinstance(c, dict):
                _choice(c.get("tone", "low"), TONES, "tone", f"{w}.cells[{j}]")


def _matrix(s, where):
    for w, cells in _rows(s, where):
        for j, c in enumerate(cells):
            _choice((c or {}).get("verdict", "na"), VERDICTS, "verdict", f"{w}.cells[{j}]")


def _timeline(s, where):
    for i, it in enumerate(_items(s, where)):
        w = f"{where}.items[{i}]"
        _need(it, "title", w)
        _choice(it.get("status", "pending"), STATUSES, "status", w)


def _bars(s, where):
    for it in _items(s, where):
        if not isinstance(it.get("value"), (int, float)) or isinstance(it.get("value"), bool):
            raise BriefError(f"{where}: every item needs a numeric 'value'")


SECTIONS = {
    "findings": _findings, "grid": _grid, "matrix": _matrix, "timeline": _timeline, "bars": _bars,
    "diagram": lambda s, w: _need(s, "mermaid", w), "text": lambda s, w: _need(s, "body", w),
    "details": lambda s, w: _need(s, "body", w), "list": _items,
}


def validate(data):
    """Raise BriefError naming the first problem; return data unchanged when valid."""
    if not isinstance(data, dict):
        raise BriefError("brief data must be a JSON object")
    _need(data, "title", "brief")
    _need(data, "headline", "brief")
    for i, st in enumerate(data.get("stats") or []):
        _need(st, "text", f"stats[{i}]")
        _choice(st.get("tone", "low"), TONES, "tone", f"stats[{i}]")
    if data.get("progress"):
        for i, ph in enumerate(_need(data["progress"], "phases", "progress")):
            _need(ph, "name", f"progress.phases[{i}]")
            _choice(ph.get("status", "pending"), STATUSES, "status", f"progress.phases[{i}]")
    for i, s in enumerate(data.get("sections") or []):
        where = f"sections[{i}]"
        kind = _need(s, "type", where)
        if kind not in SECTIONS:
            raise BriefError(f"{where}: unknown type '{kind}' (use one of {sorted(SECTIONS)})")
        _need(s, "title", where)
        SECTIONS[kind](s, where)
    if data.get("next"):
        _need(data["next"], "recommendation", "next")
    return data


def _page(title, data_json):
    # The JSON sits in a <script type="application/json"> block; "</" would end it early.
    return (PAGE.read_text()
            .replace("{{TITLE}}", html.escape(title))
            .replace("{{DATA}}", data_json.replace("</", "<\\/")))


def render(data):
    """Standalone page for one brief."""
    validate(data)
    return _page(str(data["title"]), json.dumps(data, ensure_ascii=False))


def render_board():
    """The Brief Board page: no embedded brief, so it reads the `briefs` collection."""
    return _page("Brief Board", "null")


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    try:
        if argv[:1] == ["--board"] and len(argv) == 2:
            Path(argv[1]).write_text(render_board())
            print(argv[1])
        elif argv[:1] == ["--check"] and len(argv) == 2:
            validate(json.loads(Path(argv[1]).read_text()))
            print("ok")
        elif len(argv) == 2 and not argv[0].startswith("--"):
            Path(argv[1]).write_text(render(json.loads(Path(argv[0]).read_text())))
            print(argv[1])
        else:
            print("usage: build_brief.py brief.json out.html | --check brief.json | --board out.html", file=sys.stderr)
            return 2
    except (BriefError, json.JSONDecodeError, OSError) as e:
        print(f"build_brief: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
