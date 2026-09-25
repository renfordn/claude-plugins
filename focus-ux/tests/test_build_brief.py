"""Tests for skills/visual-brief/scripts/build_brief.py: JSON brief data -> static Artifact HTML."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "skills" / "visual-brief" / "scripts"
sys.path.insert(0, str(SCRIPTS))
from build_brief import BriefError, render  # noqa: E402

MINIMAL = {"title": "Test Audit", "headline": "Fix the flakies first."}


def test_minimal_brief_fills_template():
    html = render(MINIMAL)
    assert "<title>Test Audit</title>" in html
    assert "Fix the flakies first." in html
    assert "{{" not in html
    assert "<!doctype" not in html.lower() and "<body" not in html  # publish skeleton adds these


def test_text_is_escaped_but_inline_code_and_bold_render():
    html = render({**MINIMAL, "headline": "Use `os.replace` for **atomic** <writes>"})
    assert "<code>os.replace</code>" in html
    assert "<strong>atomic</strong>" in html
    assert "&lt;writes&gt;" in html and "<writes>" not in html


def test_progress_marks_current_phase_and_notes():
    html = render({**MINIMAL, "progress": {"label": "Phase 2/4 · Counters", "phases": [
        {"name": "Digest entries", "status": "done", "note": "entry type + write path merged"},
        {"name": "Counters", "status": "current"},
        {"name": "Warming", "status": "pending"},
    ]}})
    assert "Phase 2/4 · Counters" in html
    assert 'class="phase done"' in html and 'class="phase current"' in html
    assert "you are here" in html.lower()
    assert "entry type + write path merged" in html


def test_points_get_circled_callouts():
    html = render({**MINIMAL, "points": ["one", "two", "three"]})
    assert "①" in html and "②" in html and "③" in html


def test_all_section_types_render():
    html = render({**MINIMAL, "sections": [
        {"type": "findings", "title": "Findings", "items": [
            {"severity": "high", "title": "3 flakies", "detail": "all CI reds", "where": "agent-isdd/tests"}]},
        {"type": "timeline", "title": "History", "items": [{"when": "Sep 24", "title": "merged", "status": "done"}]},
        {"type": "matrix", "title": "Options", "columns": ["Sync", "Grep"], "rows": [
            {"name": "(a) md", "pick": True, "cells": [{"verdict": "yes", "text": "per file"}, {"verdict": "yes", "text": "plain"}]},
            {"name": "(b) sqlite", "cells": [{"verdict": "no", "text": "corrupts"}, {"verdict": "no", "text": "binary"}]}]},
        {"type": "bars", "title": "Runtime", "unit": "s", "items": [{"label": "isdd", "value": 41, "highlight": True}, {"label": "nelly", "value": 9}]},
        {"type": "diagram", "title": "Flow", "mermaid": "flowchart LR\n  A-->B", "caption": "lookup"},
        {"type": "text", "title": "Why", "body": "para one\n\npara two"},
        {"type": "list", "title": "Also", "items": ["x", "y"]},
        {"type": "details", "title": "Raw data", "body": "raw"},
    ]})
    for needle in ('class="sev high"', 'class="timeline"', "<table", 'class="v no"', 'class="bar hl"',
                   'width:100.0%', 'class="mermaid"', "A--&gt;B", "<p>para two</p>", "<details"):
        assert needle in html, needle


def test_bars_scale_to_max_and_label_values():
    html = render({**MINIMAL, "sections": [{"type": "bars", "title": "t", "unit": "s",
                                            "items": [{"label": "a", "value": 40}, {"label": "b", "value": 10}]}]})
    assert "width:100.0%" in html and "width:25.0%" in html and "40s" in html


def test_collapsed_section_wraps_in_details():
    html = render({**MINIMAL, "sections": [{"type": "list", "title": "More", "collapsed": True, "items": ["x"]}]})
    assert "<details><summary>More</summary>" in html


def test_next_block():
    html = render({**MINIMAL, "next": {"recommendation": "Quarantine now, fix next.", "options": ["Fix first"]}})
    assert 'class="next"' in html and "Quarantine now, fix next." in html and "Fix first" in html


@pytest.mark.parametrize("bad, msg", [
    ({"headline": "x"}, "title"),
    ({"title": "x"}, "headline"),
    ({**MINIMAL, "sections": [{"type": "pie", "title": "t"}]}, "pie"),
    ({**MINIMAL, "sections": [{"type": "findings", "title": "t", "items": [{"severity": "urgent", "title": "x"}]}]}, "severity"),
    ({**MINIMAL, "sections": [{"type": "matrix", "title": "t", "columns": ["a"], "rows": [{"name": "r", "cells": []}]}]}, "cells"),
])
def test_invalid_data_names_the_problem(bad, msg):
    with pytest.raises(BriefError, match=msg):
        render(bad)


def test_cli_writes_file(tmp_path):
    data, out = tmp_path / "brief.json", tmp_path / "brief.html"
    data.write_text(json.dumps(MINIMAL))
    r = subprocess.run([sys.executable, str(SCRIPTS / "build_brief.py"), str(data), str(out)],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert "<title>Test Audit</title>" in out.read_text()


def test_cli_reports_bad_data_without_traceback(tmp_path):
    data = tmp_path / "brief.json"
    data.write_text(json.dumps({"title": "x"}))
    r = subprocess.run([sys.executable, str(SCRIPTS / "build_brief.py"), str(data), str(tmp_path / "o.html")],
                       capture_output=True, text=True)
    assert r.returncode == 2 and "headline" in r.stderr and "Traceback" not in r.stderr


def test_mermaid_loads_only_with_a_diagram():
    with_diagram = render({**MINIMAL, "sections": [{"type": "diagram", "title": "Flow", "mermaid": "flowchart LR\n  A-->B"}]})
    assert "cdnjs.cloudflare.com/ajax/libs/mermaid/" in with_diagram and "mermaid.run" in with_diagram
    without = render(MINIMAL)
    assert "libs/mermaid/" not in without and "mermaid.run" not in without and "{{SCRIPTS}}" not in without
