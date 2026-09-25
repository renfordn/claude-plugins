#!/usr/bin/env python3
"""Build a visual-brief Artifact page from a small JSON file.

Writing a brief as JSON (~1-2KB) and letting this script render it into the pre-designed
template costs far fewer tokens than hand-writing 10-16KB of HTML, and every brief looks the
same, so the reader learns the layout once.

Usage:
    python3 build_brief.py brief.json out.html

JSON shape (only title and headline are required):
    {
      "title": "Plugin Test Audit",                 # 2-4 word page name
      "headline": "Fix the 3 isdd flakies and CI goes green.",
      "progress": {"label": "Phase 2/4 · Counters",
                   "phases": [{"name": "...", "status": "done|current|pending|blocked", "note": "..."}]},
      "points": ["top key point", "..."],           # 3-5; rendered as ①②③
      "sections": [
        {"type": "findings", "title": "...", "items": [{"severity": "high|med|low|info", "title": "...", "detail": "...", "where": "file:line"}]},
        {"type": "timeline", "title": "...", "items": [{"when": "Sep 24", "title": "...", "status": "done|current|pending|blocked", "note": "..."}]},
        {"type": "matrix",   "title": "...", "columns": ["..."], "rows": [{"name": "...", "pick": true, "cells": [{"verdict": "yes|no|warn|na", "text": "..."}]}]},
        {"type": "bars",     "title": "...", "unit": "s", "items": [{"label": "...", "value": 41, "highlight": true}]},
        {"type": "diagram",  "title": "...", "mermaid": "flowchart LR\\n  A-->B", "caption": "..."},
        {"type": "text",     "title": "...", "body": "paragraphs separated by a blank line"},
        {"type": "list",     "title": "...", "items": ["..."]},
        {"type": "details",  "title": "...", "body": "..." }          # always collapsed
      ],                                            # any section may add "collapsed": true
      "next": {"recommendation": "...", "options": ["..."]}
    }

Text fields accept `code` and **bold**; everything else is escaped.
Exit status: 0 written, 2 invalid data (message on stderr).
"""
import html
import json
import re
import sys
from pathlib import Path

TEMPLATE = Path(__file__).resolve().parent.parent / "assets" / "brief-template.html"
STATUSES = {"done", "current", "pending", "blocked"}
SEVERITIES = {"high", "med", "low", "info"}
VERDICTS = {"yes": "✓", "no": "✗", "warn": "!", "na": "–"}
# Loaded only when the brief has a diagram section. Pinned; cdnjs is on the Artifact CSP allowlist.
MERMAID = """<script src="https://cdnjs.cloudflare.com/ajax/libs/mermaid/11.6.0/mermaid.min.js"></script>
<script>
(function () {
  if (!window.mermaid) return;
  var t = document.documentElement.getAttribute("data-theme");
  var dark = t ? t === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
  mermaid.initialize({ startOnLoad: false, theme: dark ? "dark" : "neutral", securityLevel: "strict" });
  mermaid.run({ querySelector: "pre.mermaid:not([data-processed])" });
})();
</script>"""


class BriefError(ValueError):
    pass


def _t(text):
    """Escape, then allow `code` and **bold**."""
    s = html.escape(str(text), quote=False)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    return re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)


def _need(obj, key, where):
    if not isinstance(obj, dict) or obj.get(key) in (None, "", []):
        raise BriefError(f"{where}: missing '{key}'")
    return obj[key]


def _choice(value, allowed, field, where):
    if value not in allowed:
        raise BriefError(f"{where}: {field} '{value}' must be one of {sorted(allowed)}")
    return value


def _progress(p):
    phases = _need(p, "phases", "progress")
    out = [f'<section class="progress" aria-label="Progress">']
    if p.get("label"):
        out.append(f'<div class="label">{_t(p["label"])}</div>')
    for i, ph in enumerate(phases):
        where = f"progress.phases[{i}]"
        status = _choice(ph.get("status", "pending"), STATUSES, "status", where)
        here = '<div class="here">◀ you are here</div>' if status == "current" else ""
        note = f'<div class="note">{_t(ph["note"])}</div>' if ph.get("note") else ""
        out.append(f'<div class="phase {status}"><div class="name">{_t(_need(ph, "name", where))}</div>{note}{here}</div>')
    out.append("</section>")
    return "".join(out)


def _findings(s, where):
    rows = []
    for i, it in enumerate(_need(s, "items", where)):
        w = f"{where}.items[{i}]"
        sev = _choice(it.get("severity", "info"), SEVERITIES, "severity", w)
        extra = "".join(f'<div class="{k}">{_t(it[k])}</div>' for k in ("detail", "where") if it.get(k))
        rows.append(f'<div class="finding"><span class="sev {sev}">{sev}</span>'
                    f'<div class="title">{_t(_need(it, "title", w))}</div>{extra}</div>')
    return "".join(rows)


def _timeline(s, where):
    items = []
    for i, it in enumerate(_need(s, "items", where)):
        w = f"{where}.items[{i}]"
        status = _choice(it.get("status", "pending"), STATUSES, "status", w)
        when = f'<div class="when">{_t(it["when"])}</div>' if it.get("when") else ""
        note = f'<div class="note">{_t(it["note"])}</div>' if it.get("note") else ""
        items.append(f'<li class="{status}">{when}<div><strong>{_t(_need(it, "title", w))}</strong></div>{note}</li>')
    return f'<ol class="timeline">{"".join(items)}</ol>'


def _matrix(s, where):
    cols = _need(s, "columns", where)
    head = "".join(f'<th scope="col">{_t(c)}</th>' for c in cols)
    body = []
    for i, row in enumerate(_need(s, "rows", where)):
        w = f"{where}.rows[{i}]"
        cells = row.get("cells") or []
        if len(cells) != len(cols):
            raise BriefError(f"{w}: has {len(cells)} cells, needs {len(cols)} (one per column)")
        tds = []
        for j, c in enumerate(cells):
            v = _choice(c.get("verdict", "na"), VERDICTS, "verdict", f"{w}.cells[{j}]")
            tds.append(f'<td><span class="v {v}">{VERDICTS[v]}</span>{_t(c.get("text", ""))}</td>')
        pick = row.get("pick")
        name = _t(_need(row, "name", w)) + (" ◀ pick" if pick else "")
        tr = '<tr class="pick">' if pick else "<tr>"
        body.append(f'{tr}<th scope="row">{name}</th>{"".join(tds)}</tr>')
    return f'<div class="scroll"><table><thead><tr><th></th>{head}</tr></thead><tbody>{"".join(body)}</tbody></table></div>'


def _bars(s, where):
    items = _need(s, "items", where)
    try:
        top = max(float(it["value"]) for it in items) or 1.0
    except (KeyError, TypeError, ValueError):
        raise BriefError(f"{where}: every item needs a numeric 'value'")
    unit = str(s.get("unit", ""))
    rows = []
    for it in items:
        v = float(it["value"])
        label = f"{v:g}{unit}"
        rows.append(f'<div class="bar{" hl" if it.get("highlight") else ""}"><span>{_t(it.get("label", ""))}</span>'
                    f'<div class="track"><div class="fill" style="width:{v / top * 100:.1f}%"></div></div>'
                    f'<span class="val">{html.escape(label)}</span></div>')
    return f'<div class="bars">{"".join(rows)}</div>'


def _diagram(s, where):
    cap = f'<div class="caption">{_t(s["caption"])}</div>' if s.get("caption") else ""
    return f'<div class="scroll"><pre class="mermaid">{html.escape(_need(s, "mermaid", where), quote=False)}</pre></div>{cap}'


def _text(s, where):
    return "".join(f"<p>{_t(p.strip())}</p>" for p in str(_need(s, "body", where)).split("\n\n") if p.strip())


def _list(s, where):
    return '<ul class="plain">' + "".join(f"<li>{_t(i)}</li>" for i in _need(s, "items", where)) + "</ul>"


RENDERERS = {"findings": _findings, "timeline": _timeline, "matrix": _matrix, "bars": _bars,
             "diagram": _diagram, "text": _text, "list": _list, "details": _text}


def _section(s, i):
    where = f"sections[{i}]"
    kind = _need(s, "type", where)
    if kind not in RENDERERS:
        raise BriefError(f"{where}: unknown type '{kind}' (use one of {sorted(RENDERERS)})")
    title = _t(_need(s, "title", where))
    inner = RENDERERS[kind](s, where)
    if s.get("collapsed") or kind == "details":
        return f'<details><summary>{title}</summary><div class="inner">{inner}</div></details>'
    return f"<section><h2>{title}</h2>{inner}</section>"


def render(data):
    if not isinstance(data, dict):
        raise BriefError("brief data must be a JSON object")
    title, headline = _need(data, "title", "brief"), _need(data, "headline", "brief")
    parts = [f"<h1>{_t(headline)}</h1>"]
    if data.get("progress"):
        parts.append(_progress(data["progress"]))
    if data.get("points"):
        lis = "".join(f'<li><span class="callout">{chr(0x2460 + i)}</span><span>{_t(p)}</span></li>'
                      for i, p in enumerate(data["points"][:20]))
        parts.append(f'<section><h2>Key points</h2><ol class="points">{lis}</ol></section>')
    parts += [_section(s, i) for i, s in enumerate(data.get("sections") or [])]
    if data.get("next"):
        nx = data["next"]
        opts = "".join(f"<li>{_t(o)}</li>" for o in nx.get("options") or [])
        opts = f'<div class="caption">Other options</div><ul class="plain">{opts}</ul>' if opts else ""
        parts.append(f'<section class="next"><h2>Next</h2><p>{_t(_need(nx, "recommendation", "next"))}</p>{opts}</section>')
    has_diagram = any(s.get("type") == "diagram" for s in data.get("sections") or [])
    page = TEMPLATE.read_text()
    return (page.replace("{{TITLE}}", html.escape(str(title)))
                .replace("{{BODY}}", "\n".join(parts))
                .replace("{{SCRIPTS}}", MERMAID if has_diagram else ""))


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 2:
        print("usage: build_brief.py brief.json out.html", file=sys.stderr)
        return 2
    try:
        data = json.loads(Path(argv[0]).read_text())
        Path(argv[1]).write_text(render(data))
    except (BriefError, json.JSONDecodeError, OSError) as e:
        print(f"build_brief: {e}", file=sys.stderr)
        return 2
    print(argv[1])
    return 0


if __name__ == "__main__":
    sys.exit(main())
