"""Tests for scripts/render_inline.py: table/progress/timeline/flow validate + render (Slices
1-4), plus CLI dispatch (Slice 5).

Ground truth for the branch layout is skills/visual-brief/references/patterns.md's "## Flow"
example (main chain on one line, then a `│`/label/`▼` drop to the branch on the next
lines). That example is hand-authored prose, not output of any known formula (its vertical-drop
column and its `[branch-node]` bracket don't align under one single consistent rule -- see the
"branch layout centering formula" note below), so the exact column positions asserted here encode
this test's own centering choice, not a verified byte-for-byte match to the doc. Flagged as an
open question in the test-author handoff for the caller/agent-TDD to confirm or renegotiate.

Import pattern (subprocess-import-safe module path) follows test_build_brief.py's convention for
the sibling build_brief.py module.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))
from render_inline import (  # noqa: E402
    RenderError,
    render_flow,
    render_progress,
    render_table,
    render_timeline,
    validate_flow,
    validate_progress,
    validate_table,
    validate_timeline,
)


# ---------------------------------------------------------------------------
# table (Slice 1)
# ---------------------------------------------------------------------------

TABLE_MARKDOWN = {
    "kind": "markdown",
    "columns": ["Speed", "Cost"],
    "rows": [
        {"name": "Inline", "cells": [{"text": "instant", "tone": "ok"}, {"text": "low"}]},
        {"name": "Widget", "cells": [{"text": "slow", "tone": "high"}, {"text": "high"}]},
    ],
}

TABLE_RANKED = {
    "items": [
        {"severity": "high", "title": "Summaries keyed by absolute path", "where": "index.py:88"},
        {"severity": "med", "title": "No hit counter", "where": "nelly_memory.py"},
        {"severity": "low", "title": "Stale entries only pruned weekly", "where": "cleanup.py"},
    ]
}


def test_validate_table_markdown_returns_payload_unchanged():
    assert validate_table(TABLE_MARKDOWN) == TABLE_MARKDOWN


def test_render_table_markdown_golden_output():
    out = render_table(TABLE_MARKDOWN)
    lines = out.rstrip("\n").split("\n")
    assert lines[0] == "| Speed | Cost |"
    assert lines[1] == "|---|---|"
    assert lines[2] == "| instant | low |"
    assert lines[3] == "| slow | high |"
    for line in lines:
        assert len(line) <= 80


def test_render_table_markdown_truncates_rows_past_width_cap():
    # Regression: render_table's markdown branch used to have no width check at all, unlike
    # every other shape -- a row of long cells could exceed the module's own <=80-char contract.
    wide = {
        "kind": "markdown",
        "columns": ["A", "B", "C"],
        "rows": [{"name": "r", "cells": [
            {"text": "x" * 40}, {"text": "y" * 40}, {"text": "z" * 40},
        ]}],
    }
    out = render_table(wide)
    for line in out.rstrip("\n").split("\n"):
        assert len(line) <= 80


def test_validate_table_ranked_returns_payload_unchanged():
    assert validate_table({"kind": "ranked", **TABLE_RANKED}) == {"kind": "ranked", **TABLE_RANKED}


def test_render_table_ranked_golden_output():
    out = render_table({"kind": "ranked", **TABLE_RANKED})
    lines = out.rstrip("\n").split("\n")
    assert lines[0].startswith("① ⚠ HIGH")
    assert lines[1].startswith("② ◐ MED")
    assert lines[2].startswith("③ ○ LOW")
    assert lines[0].rstrip().endswith("index.py:88")
    for line in lines:
        assert len(line) <= 80


@pytest.mark.parametrize("bad, msg", [
    ({"columns": ["a"], "rows": []}, "kind"),
    ({"kind": "markdown", "rows": []}, "columns"),
    ({"kind": "markdown", "columns": ["a"], "rows": [{"name": "r", "cells": []}]}, "cells"),
    ({"kind": "markdown", "columns": ["a"],
      "rows": [{"name": "r", "cells": [{"text": "x", "tone": "red"}]}]}, "tone"),
    ({"kind": "ranked", "items": [{"title": "x"}]}, "severity"),
    ({"kind": "ranked", "items": [{"severity": "high"}]}, "title"),
    ({"kind": "markdown", "columns": ["a"],
      "rows": [{"name": f"r{i}", "cells": [{"text": "x"}]} for i in range(11)]}, "exceeds"),
])
def test_validate_table_raises_render_error_for_bad_payloads(bad, msg):
    with pytest.raises(RenderError, match=msg):
        validate_table(bad)


# ---------------------------------------------------------------------------
# progress (Slice 2)
# ---------------------------------------------------------------------------

PROGRESS = {
    "phases": [
        {"name": "Phase 1 Requirements", "total": 3, "done": 3},
        {"name": "Phase 2 Design", "total": 4, "done": 2, "current": True},
        {"name": "Phase 3 Tasks", "total": 5, "done": 0},
    ],
    "you_are_here": "step 3/4",
}


def test_validate_progress_returns_payload_unchanged():
    assert validate_progress(PROGRESS) == PROGRESS


def test_render_progress_golden_output():
    out = render_progress(PROGRESS)
    lines = out.rstrip("\n").split("\n")
    assert "✅✅✅" in lines[0]
    assert "▸" in lines[1] and "you are here (step 3/4)" in lines[1]
    assert "○○○○○" in lines[2]
    for line in lines:
        assert len(line) <= 80


@pytest.mark.parametrize("bad, msg", [
    ({"phases": []}, "phases"),
    ({"phases": [{"total": 3}]}, "name"),
    ({"phases": [{"name": "a", "total": 3, "done": 5}]}, "done"),
    ({"phases": [{"name": "a", "total": 3, "current": True},
                 {"name": "b", "total": 2, "current": True}]}, "one phase"),
    ({"phases": [{"name": f"p{i}", "total": 1} for i in range(11)]}, "exceeds"),
])
def test_validate_progress_raises_render_error_for_bad_payloads(bad, msg):
    with pytest.raises(RenderError, match=msg):
        validate_progress(bad)


# ---------------------------------------------------------------------------
# timeline (Slice 3)
# ---------------------------------------------------------------------------

TIMELINE = {
    "items": [
        {"when": "Sep 16", "label": "Phase 1 done", "status": "done"},
        {"when": "Sep 22", "label": "cache retired", "status": "done"},
        {"when": "Sep 25", "label": "summary cache", "status": "current"},
    ],
    "next": "focus-ux",
}


def test_validate_timeline_returns_payload_unchanged():
    assert validate_timeline(TIMELINE) == TIMELINE


def test_render_timeline_golden_output():
    out = render_timeline(TIMELINE)
    lines = out.rstrip("\n").split("\n")
    assert len(lines) == 2
    assert "Sep 16 ──●── Sep 22 ──●── Sep 25 ──▶ focus-ux" == lines[0]
    for line in lines:
        assert len(line) <= 80


@pytest.mark.parametrize("bad, msg", [
    ({"items": []}, "items"),
    ({"items": [{"when": "x", "status": "done"}]}, "label"),
    ({"items": [{"when": "x", "label": "y", "status": "cancelled"}]}, "status"),
    ({"items": [{"when": f"w{i}", "label": "y", "status": "done"} for i in range(11)]}, "exceeds"),
])
def test_validate_timeline_raises_render_error_for_bad_payloads(bad, msg):
    with pytest.raises(RenderError, match=msg):
        validate_timeline(bad)


def test_render_timeline_raises_when_row_exceeds_width_cap():
    huge = {"items": [{"when": "x" * 50, "label": "y", "status": "done"},
                       {"when": "z" * 50, "label": "w", "status": "pending"}]}
    with pytest.raises(RenderError, match="80 cols"):
        render_timeline(huge)


def _node(id_, label):
    return {"id": id_, "label": label}


def _edge(from_, to, label=None):
    e = {"from": from_, "to": to}
    if label is not None:
        e["label"] = label
    return e


# ---------------------------------------------------------------------------
# Valid: strict linear chain
# ---------------------------------------------------------------------------

LINEAR = {
    "nodes": [_node("a", "Start"), _node("b", "Middle"), _node("c", "End")],
    "edges": [_edge("a", "b"), _edge("b", "c")],
}


def test_validate_flow_returns_linear_payload_unchanged():
    assert validate_flow(LINEAR) == LINEAR


def test_render_flow_linear_chain_golden_output():
    out = render_flow(LINEAR)
    # `[A] ─▶ [B] ─▶ [C]` per Test Intent -- node brackets hold the label,
    # not the id, matching patterns.md's human-readable bracket contents.
    assert out.rstrip("\n") == "[Start] ─▶ [Middle] ─▶ [End]"
    for line in out.splitlines():
        assert len(line) <= 80


# ---------------------------------------------------------------------------
# Valid: single branch point (main chain line + drop to the branch)
# ---------------------------------------------------------------------------

BRANCH = {
    "nodes": [
        _node("a", "Fetch"),
        _node("b", "Validate"),
        _node("c", "Save"),
        _node("d", "Reject"),
    ],
    "edges": [
        _edge("a", "b"),
        _edge("b", "c", "ok"),
        _edge("b", "d", "bad"),
    ],
}

# Golden layout, derived from patterns.md's Flow example shape:
# line 1: main chain, with the first-listed outgoing edge of the branch node continuing inline
#         and its label shown inline (`─ ok ─▶`)
# line 2: `│` under the centre column of the branch node's `[...]` box
#         (centre = box_start + box_width // 2)
# line 3: the branch edge's label, centred under that same column
#         (label_start = max(0, centre - len(label) // 2))
# line 4: `▼` under that same centre column
# line 5: the branch target node's box, left-aligned under the branch node's own box start


def test_render_flow_single_branch_golden_output():
    out = render_flow(BRANCH)
    lines = out.rstrip("\n").split("\n")
    expected = [
        "[Fetch] ─▶ [Validate] ─ ok ─▶ [Save]",
        "                │",
        "               bad",
        "                ▼",
        "            [Reject]",
    ]
    assert lines == expected
    for line in lines:
        assert len(line) <= 80


# ---------------------------------------------------------------------------
# Valid: single branch point where BOTH arms continue past their first hop --
# regression for a defect where render_flow silently dropped every node downstream
# of the branch target (e.g. the exact patterns.md example: cache lookup branches
# to a miss path that continues through search repo -> write summary -> return).
# ---------------------------------------------------------------------------

BRANCH_WITH_DOWNSTREAM_NODES = {
    "nodes": [
        _node("req", "request"),
        _node("cache", "cache lookup"),
        _node("ret", "return summary"),
        _node("search", "search repo"),
        _node("write", "write summary"),
        _node("done", "return"),
    ],
    "edges": [
        _edge("req", "cache"),
        _edge("cache", "ret", "hit"),
        _edge("cache", "search", "miss"),
        _edge("search", "write"),
        _edge("write", "done"),
    ],
}


def test_render_flow_branch_arm_continues_past_first_hop():
    out = render_flow(BRANCH_WITH_DOWNSTREAM_NODES)
    lines = out.rstrip("\n").split("\n")
    # The main (hit) arm is one box; the branch (miss) arm must include every node
    # downstream of the branch target, not just [search repo].
    assert lines[0] == "[request] ─▶ [cache lookup] ─ hit ─▶ [return summary]"
    assert lines[-1].endswith("[search repo] ─▶ [write summary] ─▶ [return]")
    for line in lines:
        assert len(line) <= 80


# ---------------------------------------------------------------------------
# Ceiling failures -- all must raise RenderError pointing at the visual-brief skill
# ---------------------------------------------------------------------------

def _linear_chain(n):
    nodes = [_node(f"n{i}", f"N{i}") for i in range(n)]
    edges = [_edge(f"n{i}", f"n{i + 1}") for i in range(n - 1)]
    return {"nodes": nodes, "edges": edges}


MULTIPLE_BRANCH_POINTS = {
    "nodes": [_node(x, x.upper()) for x in "abcdef"],
    "edges": [
        _edge("a", "b"),
        _edge("b", "c"),
        _edge("b", "d"),  # branch point #1: b has 2 outgoing edges
        _edge("c", "e"),
        _edge("c", "f"),  # branch point #2: c has 2 outgoing edges
    ],
}

CYCLE = {
    "nodes": [_node(x, x.upper()) for x in "abc"],
    "edges": [_edge("a", "b"), _edge("b", "c"), _edge("c", "a")],
}

THREE_WAY_BRANCH = {
    "nodes": [_node(x, x.upper()) for x in "abcde"],
    "edges": [
        _edge("a", "b"),
        _edge("b", "c"),
        _edge("b", "d"),
        _edge("b", "e"),  # b has 3 outgoing edges
    ],
}

TOO_MANY_NODES = _linear_chain(11)  # cap is 10; 11 must fail

# Disconnected/unreachable node: chosen failure mode is "any node not reachable by following
# edges from nodes[0] (treated as the flow's start) raises RenderError" -- `d` here has no edge
# to or from the reachable component {a, b, c}.
DISCONNECTED_NODE = {
    "nodes": [_node(x, x.upper()) for x in "abcd"],
    "edges": [_edge("a", "b"), _edge("b", "c")],
}


CEILING_CASES = [
    pytest.param(MULTIPLE_BRANCH_POINTS, id="multiple_branch_points"),
    pytest.param(CYCLE, id="cycle"),
    pytest.param(THREE_WAY_BRANCH, id="three_way_branch"),
    pytest.param(TOO_MANY_NODES, id="more_than_10_nodes"),
    pytest.param(DISCONNECTED_NODE, id="disconnected_unreachable_node"),
]


@pytest.mark.parametrize("payload", CEILING_CASES)
def test_validate_flow_raises_render_error_for_ceiling_cases(payload):
    with pytest.raises(RenderError) as excinfo:
        validate_flow(payload)
    assert "visual-brief skill" in str(excinfo.value)


# ---------------------------------------------------------------------------
# CLI dispatch (Slice 5)
# ---------------------------------------------------------------------------

def _cli(*args, stdin=None):
    return subprocess.run(
        [sys.executable, str(SCRIPTS / "render_inline.py"), *map(str, args)],
        input=stdin, capture_output=True, text=True,
    )


@pytest.mark.parametrize("shape, payload, expect", [
    ("table", TABLE_MARKDOWN, "| Speed | Cost |"),
    ("progress", PROGRESS, "✅✅✅"),
    ("timeline", TIMELINE, "Sep 16"),
    ("flow", LINEAR, "[Start] ─▶ [Middle] ─▶ [End]"),
])
def test_cli_exit_0_and_correct_stdout_for_each_shape_via_stdin(tmp_path, shape, payload, expect):
    r = _cli(shape, "-", stdin=json.dumps(payload))
    assert r.returncode == 0
    assert expect in r.stdout


def test_cli_exit_2_reports_bad_data_without_traceback(tmp_path):
    data = tmp_path / "payload.json"
    data.write_text("{not valid json")
    r = _cli("table", data)
    assert r.returncode == 2
    assert r.stdout == ""
    assert r.stderr.startswith("render_inline: ")
    assert "Traceback" not in r.stderr
