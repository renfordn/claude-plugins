#!/usr/bin/env python3
"""Render a Small inline picture (table, progress map, timeline, flow) from JSON.

Structurally mirrors skills/visual-brief/scripts/build_brief.py: same validate-then-render
split, same BriefError-equivalent/exit-code/stderr contract -- but renders plain <=80-char ASCII
text to stdout instead of writing an HTML file. Fully independent of build_brief.py (no shared
import) per this feature's Non-Goals.

Usage:
    python3 render_inline.py <shape> <payload.json>   # shape in {table, progress, timeline, flow}
    python3 render_inline.py <shape> -                # payload on stdin

JSON shape per `shape`:
    table (kind: markdown): {"kind": "markdown", "columns": [...],
        "rows": [{"name", "cells": [{"text","tone"} | str, ...]}]}
    table (kind: ranked):   {"kind": "ranked",
        "items": [{"severity": "high|med|low", "title", "detail"?, "where"?}]}
    progress: {"phases": [{"name","total","done","current"?}], "you_are_here"?: "step N/M"}
    timeline: {"items": [{"when","label","status": "done|current|pending"}], "next"?: "label"}
    flow: {"nodes": [{"id","label"}], "edges": [{"from","to","label"?}]}

Every shape caps its list of nodes/rows/items at 10 -- over that (or, for `flow`, a layout this
renderer doesn't support) is a ceiling failure directing the caller to the `visual-brief` skill.

Exit status: 0 ok (rendered text on stdout), 2 invalid/oversized data (message on stderr).
"""
import json
import sys
from pathlib import Path

MAX_ITEMS = 10
WIDTH = 80

SEVERITIES = {"high": ("⚠", "HIGH"), "med": ("◐", "MED"), "low": ("○", "LOW")}
CIRCLED = ["①", "②", "③", "④", "⑤", "⑥", "⑦", "⑧", "⑨", "⑩"]
TONES = {"high", "med", "low", "info", "ok", "now"}
TIMELINE_STATUSES = {"done", "current", "pending"}


class RenderError(ValueError):
    pass


def _need(obj, key, where):
    if not isinstance(obj, dict) or obj.get(key) in (None, "", []):
        raise RenderError(f"{where}: missing '{key}'")
    return obj[key]


def _choice(value, allowed, field, where):
    if value not in allowed:
        raise RenderError(f"{where}: {field} '{value}' must be one of {sorted(allowed)}")


def _items(payload, where, cap=MAX_ITEMS, key="items"):
    items = _need(payload, key, where)
    if not isinstance(items, list):
        raise RenderError(f"{where}: '{key}' must be a list")
    if len(items) > cap:
        raise RenderError(
            f"{where}: {len(items)} {key} exceeds the Small-shape ceiling of {cap} "
            f"-- use the visual-brief skill instead"
        )
    return items


def _truncate(text, width):
    text = str(text)
    if len(text) <= width:
        return text
    if width <= 1:
        return text[:width]
    return text[: width - 1] + "…"


# ---------------------------------------------------------------------------
# table
# ---------------------------------------------------------------------------

def validate_table(payload):
    if not isinstance(payload, dict):
        raise RenderError("table: payload must be a JSON object")
    kind = _need(payload, "kind", "table")
    _choice(kind, {"markdown", "ranked"}, "kind", "table")
    if kind == "markdown":
        cols = _need(payload, "columns", "table")
        if not isinstance(cols, list) or not cols:
            raise RenderError("table: 'columns' must be a non-empty list")
        rows = _items(payload, "table", key="rows")
        for i, row in enumerate(rows):
            where = f"table.rows[{i}]"
            _need(row, "name", where)
            cells = row.get("cells") or []
            if len(cells) != len(cols):
                raise RenderError(
                    f"{where}: has {len(cells)} cells, needs {len(cols)} (one per column)"
                )
            for j, c in enumerate(cells):
                if isinstance(c, dict):
                    _choice(c.get("tone", "low"), TONES, "tone", f"{where}.cells[{j}]")
    else:
        items = _items(payload, "table")
        for i, it in enumerate(items):
            where = f"table.items[{i}]"
            _need(it, "title", where)
            _choice(it.get("severity"), set(SEVERITIES), "severity", where)
    return payload


def render_table(payload):
    validate_table(payload)
    if payload["kind"] == "markdown":
        cols = payload["columns"]
        lines = ["| " + " | ".join(cols) + " |", "|" + "|".join(["---"] * len(cols)) + "|"]
        for row in payload["rows"]:
            cells = row.get("cells") or []
            texts = []
            for c in cells:
                texts.append(c.get("text", "") if isinstance(c, dict) else str(c))
            lines.append("| " + " | ".join(texts) + " |")
        return "\n".join(_truncate(line, WIDTH) for line in lines) + "\n"
    # ranked
    lines = []
    width_word = max(len(word) for _, word in SEVERITIES.values())
    for i, it in enumerate(payload["items"]):
        glyph, word = SEVERITIES[it["severity"]]
        circ = CIRCLED[i]
        title = it["title"]
        where = it.get("where", "")
        prefix = f"{circ} {glyph} {word.ljust(width_word)}  {title}"
        if where:
            pad = max(1, WIDTH - len(prefix) - len(where))
            line = prefix + (" " * pad) + where
        else:
            line = prefix
        lines.append(_truncate(line, WIDTH))
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# progress
# ---------------------------------------------------------------------------

def validate_progress(payload):
    if not isinstance(payload, dict):
        raise RenderError("progress: payload must be a JSON object")
    phases = _items(payload, "progress", key="phases")
    current_count = 0
    for i, ph in enumerate(phases):
        where = f"progress.phases[{i}]"
        _need(ph, "name", where)
        total = _need(ph, "total", where)
        done = ph.get("done", 0)
        if not isinstance(total, int) or isinstance(total, bool) or total < 0:
            raise RenderError(f"{where}: 'total' must be a non-negative integer")
        if not isinstance(done, int) or isinstance(done, bool) or done < 0:
            raise RenderError(f"{where}: 'done' must be a non-negative integer")
        if done > total:
            raise RenderError(f"{where}: 'done' ({done}) must be <= 'total' ({total})")
        if ph.get("current"):
            current_count += 1
    if current_count > 1:
        raise RenderError("progress: at most one phase may have 'current': true")
    return payload


def render_progress(payload):
    validate_progress(payload)
    phases = payload["phases"]
    name_width = max(len(ph["name"]) for ph in phases)
    lines = []
    for ph in phases:
        total, done = ph["total"], ph.get("done", 0)
        is_current = bool(ph.get("current"))
        run = "✅" * done
        remaining = total - done
        if is_current and remaining > 0:
            run += "▸" + ("○" * (remaining - 1))
        else:
            run += "○" * remaining
        line = f"{ph['name'].ljust(name_width)}  {run}"
        if is_current and payload.get("you_are_here"):
            line += f"      ◀ you are here ({payload['you_are_here']})"
        lines.append(_truncate(line, WIDTH))
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# timeline
# ---------------------------------------------------------------------------

def validate_timeline(payload):
    if not isinstance(payload, dict):
        raise RenderError("timeline: payload must be a JSON object")
    items = _items(payload, "timeline")
    for i, it in enumerate(items):
        where = f"timeline.items[{i}]"
        _need(it, "when", where)
        _need(it, "label", where)
        _choice(it.get("status"), TIMELINE_STATUSES, "status", where)
    return payload


def render_timeline(payload):
    validate_timeline(payload)
    items = payload["items"]
    when_row = " ──●── ".join(it["when"] for it in items)
    if payload.get("next"):
        when_row += f" ──▶ {payload['next']}"
    if len(when_row) > WIDTH:
        raise RenderError(
            "timeline: rendered waypoint row exceeds 80 cols -- use the visual-brief skill instead"
        )
    # Second row: labels padded under each waypoint's "when" column.
    label_row = ""
    for i, it in enumerate(items):
        seg = " ──●── " if i > 0 else ""
        col_width = len(seg) + len(it["when"])
        start = len(label_row) if i == 0 else len(label_row)
        label_row += " " * len(seg) if i > 0 else ""
        label = it["label"]
        pad_total = len(it["when"])
        label_row += label.center(pad_total) if len(label) <= pad_total else label
    lines = [when_row, label_row]
    for line in lines:
        if len(line) > WIDTH:
            raise RenderError(
                "timeline: rendered label row exceeds 80 cols -- use the visual-brief skill instead"
            )
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# flow
# ---------------------------------------------------------------------------

def _flow_graph(payload):
    nodes = _need(payload, "nodes", "flow")
    if not isinstance(nodes, list):
        raise RenderError("flow: 'nodes' must be a list")
    if len(nodes) > MAX_ITEMS:
        raise RenderError(
            f"flow: {len(nodes)} nodes exceeds the Small-shape ceiling of {MAX_ITEMS} "
            f"-- use the visual-brief skill instead"
        )
    edges = payload.get("edges") or []
    by_id = {}
    for i, n in enumerate(nodes):
        where = f"flow.nodes[{i}]"
        nid = _need(n, "id", where)
        _need(n, "label", where)
        by_id[nid] = n
    out_edges = {}
    for i, e in enumerate(edges):
        where = f"flow.edges[{i}]"
        src = _need(e, "from", where)
        dst = _need(e, "to", where)
        if src not in by_id or dst not in by_id:
            raise RenderError(f"{where}: edge references an unknown node id")
        out_edges.setdefault(src, []).append(e)
    return nodes, by_id, out_edges


def validate_flow(payload):
    if not isinstance(payload, dict):
        raise RenderError("flow: payload must be a JSON object")
    nodes, by_id, out_edges = _flow_graph(payload)

    for nid, edges in out_edges.items():
        if len(edges) > 2:
            raise RenderError(
                f"flow: node '{nid}' has {len(edges)} outgoing edges (max 2 for a branch) "
                f"-- use the visual-brief skill instead"
            )

    branch_points = [nid for nid, edges in out_edges.items() if len(edges) == 2]
    if len(branch_points) > 1:
        raise RenderError(
            "flow: more than one branch point -- use the visual-brief skill instead"
        )

    # Reachability from nodes[0] (the flow's start), following edges.
    start = nodes[0]["id"]
    seen = {start}
    stack = [start]
    while stack:
        cur = stack.pop()
        for e in out_edges.get(cur, []):
            if e["to"] not in seen:
                seen.add(e["to"])
                stack.append(e["to"])
    if len(seen) != len(nodes):
        raise RenderError(
            "flow: not every node is reachable from the first node -- use the visual-brief "
            "skill instead"
        )

    # Cycle detection (DFS with recursion stack).
    visiting = set()
    visited = set()

    def _dfs(nid):
        visiting.add(nid)
        for e in out_edges.get(nid, []):
            nxt = e["to"]
            if nxt in visiting:
                raise RenderError("flow: cycle detected -- use the visual-brief skill instead")
            if nxt not in visited:
                _dfs(nxt)
        visiting.discard(nid)
        visited.add(nid)

    _dfs(start)

    return payload


def render_flow(payload):
    validate_flow(payload)
    nodes, by_id, out_edges = _flow_graph(payload)
    branch_node = next((nid for nid, edges in out_edges.items() if len(edges) == 2), None)

    def box(nid):
        return f"[{by_id[nid]['label']}]"

    def walk_chain(start):
        """Node ids from `start` through the end of its linear run -- stops at (but does not
        cross past) any node with 2 outgoing edges. validate_flow already guarantees at most
        one such branch point exists, so this only ever needs to stop once."""
        order = [start]
        cur = start
        while out_edges.get(cur) and len(out_edges[cur]) == 1:
            cur = out_edges[cur][0]["to"]
            order.append(cur)
        return order

    if branch_node is None:
        # Strict linear chain.
        order = walk_chain(nodes[0]["id"])
        line = " ─▶ ".join(box(nid) for nid in order)
        return line + "\n"

    # Linear chain up to and including the branch node.
    order = walk_chain(nodes[0]["id"])
    main_edge, branch_edge = out_edges[branch_node]
    # Each arm continues (possibly through further nodes) until it dead-ends -- neither arm
    # can re-branch, since validate_flow already ruled out a second branch point.
    main_chain = walk_chain(main_edge["to"])
    branch_chain = walk_chain(branch_edge["to"])

    prefix = " ─▶ ".join(box(nid) for nid in order)
    main_rest = " ─▶ ".join(box(nid) for nid in main_chain)
    main_label = main_edge.get("label")
    if main_label:
        line1 = f"{prefix} ─ {main_label} ─▶ {main_rest}"
    else:
        line1 = f"{prefix} ─▶ {main_rest}"

    # Branch node's own box start within `prefix` (index of its opening bracket).
    box_start = prefix.rfind(box(branch_node))
    box_width = len(box(branch_node))
    centre = box_start + box_width // 2

    branch_label = branch_edge.get("label", "")
    label_start = max(0, centre - len(branch_label) // 2)

    branch_rest = " ─▶ ".join(box(nid) for nid in branch_chain)

    line2 = " " * centre + "│"
    line3 = " " * label_start + branch_label
    line4 = " " * centre + "▼"
    line5 = " " * (box_start + 1) + branch_rest

    lines = [line1, line2, line3, line4, line5]
    for line in lines:
        if len(line) > WIDTH:
            raise RenderError(
                "flow: rendered layout exceeds 80 cols -- use the visual-brief skill instead"
            )
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

SHAPES = {
    "table": (validate_table, render_table),
    "progress": (validate_progress, render_progress),
    "timeline": (validate_timeline, render_timeline),
    "flow": (validate_flow, render_flow),
}


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    try:
        if len(argv) != 2 or argv[0] not in SHAPES:
            print(
                "usage: render_inline.py <table|progress|timeline|flow> <payload.json|->",
                file=sys.stderr,
            )
            return 2
        shape, source = argv
        text = sys.stdin.read() if source == "-" else Path(source).read_text()
        payload = json.loads(text)
        _, render = SHAPES[shape]
        sys.stdout.write(render(payload))
    except (RenderError, json.JSONDecodeError, OSError) as e:
        print(f"render_inline: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
