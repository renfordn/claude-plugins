"""Tests for skills/visual-brief/scripts/build_brief.py: validate brief JSON, embed it in the one
brief page, or emit the Brief Board. Rendering itself happens in the page's JS."""
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "skills" / "visual-brief" / "scripts"
sys.path.insert(0, str(SCRIPTS))
from build_brief import BriefError, render, render_board, validate  # noqa: E402

MINIMAL = {"title": "Test Audit", "headline": "Fix the flakies first."}
FULL = {
    **MINIMAL,
    "project": "Claude-Plugins", "createdAt": "2026-09-25T14:05:00Z",
    "eyebrow": "Audit · 7 suites", "lede": "context",
    "stats": [{"text": "3 flaky", "tone": "high"}, {"text": "2 clean", "tone": "ok"}],
    "progress": {"label": "Plan", "phases": [{"name": "A", "status": "done"}, {"name": "B", "status": "current"}]},
    "points": ["one", "two"],
    "sections": [
        {"type": "findings", "title": "F", "items": [{"severity": "high", "title": "t", "sowhat": "s"}]},
        {"type": "grid", "title": "G", "columns": ["Flaky"], "rows": [{"name": "isdd", "flag": "start here", "cells": [{"text": "3", "tone": "high"}]}]},
        {"type": "matrix", "title": "M", "columns": ["Sync"], "rows": [{"name": "a", "pick": True, "cells": [{"verdict": "yes", "text": "ok"}]}]},
        {"type": "timeline", "title": "T", "items": [{"title": "x", "status": "done"}]},
        {"type": "bars", "title": "B", "unit": "s", "items": [{"label": "a", "value": 4}]},
        {"type": "diagram", "title": "D", "mermaid": "flowchart LR\n  A-->B"},
        {"type": "text", "title": "X", "body": "p"},
        {"type": "list", "title": "L", "items": ["x"]},
        {"type": "details", "title": "Raw", "body": "raw"},
    ],
    "next": {"recommendation": "go", "options": ["wait"]},
}


def _embedded(page):
    m = re.search(r'<script type="application/json" id="brief-data">(.*?)</script>', page, re.S)
    assert m, "no data block"
    return json.loads(m.group(1).replace("<\\/", "</"))


def test_full_brief_validates_and_round_trips():
    page = render(FULL)
    assert "<title>Test Audit</title>" in page and "{{" not in page
    assert _embedded(page) == FULL
    assert "<!doctype" not in page.lower() and "<body" not in page  # publish skeleton adds these


def test_script_breakout_is_neutralised():
    page = render({**MINIMAL, "headline": "</script><script>alert(1)</script>"})
    block = page.split('id="brief-data">', 1)[1].split("</script>", 1)[0]
    assert "</script" not in block
    assert _embedded(page)["headline"] == "</script><script>alert(1)</script>"


def test_title_is_escaped():
    assert "<title>A &amp; B &lt;x&gt;</title>" in render({**MINIMAL, "title": "A & B <x>"})


def test_board_page_embeds_no_brief():
    page = render_board()
    assert "<title>Brief Board</title>" in page
    assert _embedded(page) is None
    assert 'collection("briefs")' in page


def test_page_never_injects_brief_text_as_html():
    page = render_board()
    assert "innerHTML" not in page and "insertAdjacentHTML" not in page


def test_mermaid_is_loaded_lazily_and_pinned():
    page = render_board()
    assert "cdnjs.cloudflare.com/ajax/libs/mermaid/11.6.0/mermaid.min.js" in page
    assert '<script src="https://cdnjs' not in page  # only injected when a brief has a diagram


@pytest.mark.parametrize("bad, msg", [
    ({"headline": "x"}, "title"),
    ({"title": "x"}, "headline"),
    ({**MINIMAL, "stats": [{"text": "x", "tone": "red"}]}, "tone"),
    ({**MINIMAL, "progress": {"phases": [{"name": "a", "status": "soon"}]}}, "status"),
    ({**MINIMAL, "sections": [{"type": "pie", "title": "t"}]}, "pie"),
    ({**MINIMAL, "sections": [{"type": "findings", "title": "t", "items": [{"severity": "urgent", "title": "x"}]}]}, "severity"),
    ({**MINIMAL, "sections": [{"type": "grid", "title": "t", "columns": ["a", "b"], "rows": [{"name": "r", "cells": [{}]}]}]}, "cells"),
    ({**MINIMAL, "sections": [{"type": "matrix", "title": "t", "columns": ["a"], "rows": [{"name": "r", "cells": [{"verdict": "maybe"}]}]}]}, "verdict"),
    ({**MINIMAL, "sections": [{"type": "bars", "title": "t", "items": [{"label": "a", "value": "4"}]}]}, "numeric"),
    ({**MINIMAL, "next": {"options": ["x"]}}, "recommendation"),
])
def test_invalid_data_names_the_problem(bad, msg):
    with pytest.raises(BriefError, match=msg):
        validate(bad)


def _cli(*args):
    return subprocess.run([sys.executable, str(SCRIPTS / "build_brief.py"), *map(str, args)], capture_output=True, text=True)


def test_cli_standalone_check_and_board(tmp_path):
    data = tmp_path / "brief.json"
    data.write_text(json.dumps(FULL))
    out = tmp_path / "brief.html"
    assert _cli(data, out).returncode == 0 and _embedded(out.read_text()) == FULL
    r = _cli("--check", data)
    assert r.returncode == 0 and r.stdout.strip() == "ok"
    board = tmp_path / "board.html"
    assert _cli("--board", board).returncode == 0 and _embedded(board.read_text()) is None


def test_cli_reports_bad_data_without_traceback(tmp_path):
    data = tmp_path / "brief.json"
    data.write_text(json.dumps({"title": "x"}))
    r = _cli("--check", data)
    assert r.returncode == 2 and "headline" in r.stderr and "Traceback" not in r.stderr
