"""skills/workflow-manager/assets/plan-board.html -- the living Plan Board page.

One Artifact page reads the `plans` collection from its own db and draws a card per feature. It
never builds markup from record text (records are untrusted data), so every value goes through
textContent and every class name comes from a fixed list. The behavior tests run the page's own
script in node with a tiny fake DOM.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGE = os.path.join(ROOT, "skills", "workflow-manager", "assets", "plan-board.html")
HOOKS = os.path.join(ROOT, "hooks")
NODE = shutil.which("node")


def _html():
    with open(PAGE, encoding="utf-8") as fh:
        return fh.read()


def _script():
    scripts = re.findall(r"<script>(.*?)</script>", _html(), re.S)
    assert scripts, "page has no inline script"
    return scripts[-1]


# ---------------------------------------------------------------- structure

def test_page_has_a_stable_name_and_no_document_skeleton():
    html = _html()
    assert "<title>Plan Board</title>" in html
    assert "<!doctype" not in html.lower()
    # Real skeleton tags only: `<header>` is a normal element and must not trip this.
    assert not re.search(r"<(html|head|body)[\s>]", html, re.I), "the Artifact tool adds the skeleton"


def test_page_reads_the_plans_collection_live_and_subscribes_once():
    js = _script()
    assert 'claude.use("db")' in js
    assert 'collection("plans")' in js
    assert js.count(".onSnapshot(") == 1
    assert "window.claude.db" not in js  # only claude.use() is promised


def test_page_never_builds_markup_from_record_text():
    js = _script()
    for banned in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "eval("):
        assert banned not in js, banned


def test_page_only_loads_fonts_from_the_allowed_host():
    html = _html()
    assert "<script src" not in html
    for url in re.findall(r'href="(https?://[^"]+)"', html):
        assert url.startswith(("https://fonts.googleapis.com", "https://fonts.gstatic.com")), url


def test_page_defines_both_themes_and_an_explicit_background():
    html = _html()
    assert re.search(r":root\s*{[^}]*--bg:", html)
    assert '@media (prefers-color-scheme: dark)' in html
    assert ':root:not([data-theme="light"])' in html
    assert ':root[data-theme="dark"]' in html
    assert re.search(r"body\s*{[^}]*background:\s*var\(--bg\)", html)


def test_page_has_designed_empty_offline_and_error_states():
    js = _script()
    assert "No features yet" in js
    assert "opened in Claude" in js
    assert "Live updates stopped" in js


def test_page_command_writes_an_identical_copy(tmp_path):
    out = tmp_path / "board.html"
    result = subprocess.run([sys.executable, os.path.join(HOOKS, "plan_board.py"), "page", str(out)],
                            capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr
    assert out.read_text() == _html()


# ---------------------------------------------------------------- behavior (node)

FAKE_DOM = r"""
function Node(tag){ this.tag = tag; this.children = []; this.textContent = ""; this.className = ""; this.attrs = {}; }
Node.prototype.appendChild = function(c){ this.children.push(c); return c; };
Node.prototype.setAttribute = function(k, v){ this.attrs[k] = String(v); };
Node.prototype.replaceChildren = function(){ this.children = Array.prototype.slice.call(arguments); };
global.document = { createElement: function(t){ return new Node(t); } };
global.Node = Node;
function allText(n){ return [n.textContent].concat(n.children.map(allText)).join(" "); }
function allNodes(n){ return [n].concat(...n.children.map(allNodes)); }
"""


def _node(body):
    if not NODE:
        pytest.skip("node is not installed")
    with tempfile.TemporaryDirectory() as d:
        page = os.path.join(d, "page.js")
        with open(page, "w", encoding="utf-8") as fh:
            fh.write(_script())
        driver = os.path.join(d, "run.js")
        with open(driver, "w", encoding="utf-8") as fh:
            fh.write(FAKE_DOM + f"\nconst pb = require({json.dumps(page)});\n" + body)
        result = subprocess.run([NODE, driver], capture_output=True, text=True, timeout=30)
        assert result.returncode == 0, result.stderr
        return json.loads(result.stdout) if result.stdout.strip() else None


def _doc(**kw):
    base = {"schema": 1, "id": "p--f", "project": "proj", "slug": "f", "title": "Feature", "goal": "Goal",
            "track": "Standard", "phase": "Design", "status": "In Progress", "pauseReason": "",
            "nextAction": "", "phases": [{"name": n, "state": "pending"} for n in
                                          ("Requirements", "Design", "Tasks", "Implementation")],
            "implementationRequested": None, "updatedAt": "2026-09-29"}
    base.update(kw)
    return base


def test_sorting_puts_active_work_first_then_newest():
    docs = [_doc(id="a", title="a", status="Complete", updatedAt="2026-09-30"),
            _doc(id="b", title="b", status="Paused", updatedAt="2026-09-25"),
            _doc(id="c", title="c", status="In Progress", updatedAt="2026-09-20"),
            _doc(id="d", title="d", status="In Progress", updatedAt="2026-09-28")]
    out = _node(f"console.log(JSON.stringify(pb.sortDocs({json.dumps(docs)}).map(d => d.id)));")
    assert out == ["d", "c", "b", "a"]


def test_grouping_orders_projects_alphabetically_and_keeps_doc_order():
    docs = [_doc(id="1", project="zeta"), _doc(id="2", project="alpha"), _doc(id="3", project="zeta")]
    out = _node(f"console.log(JSON.stringify(pb.groupByProject({json.dumps(docs)}).map(g => [g.project, g.docs.map(d => d.id)])));")
    assert out == [["alpha", ["2"]], ["zeta", ["1", "3"]]]


def test_counts_by_status():
    docs = [_doc(status="In Progress"), _doc(status="Paused"), _doc(status="Complete"), _doc(status="Complete"),
            _doc(status="Weird")]
    out = _node(f"console.log(JSON.stringify(pb.countByStatus({json.dumps(docs)})));")
    assert out == {"active": 1, "paused": 1, "complete": 2, "other": 1, "total": 5}


def test_relative_day_wording():
    now = "Date.UTC(2026, 8, 30, 12)"
    out = _node(f"""console.log(JSON.stringify([
      pb.relDay("2026-09-30", {now}), pb.relDay("2026-09-29", {now}),
      pb.relDay("2026-09-27", {now}), pb.relDay("garbage", {now}), pb.relDay(undefined, {now})]));""")
    assert out == ["today", "yesterday", "3 days ago", "", ""]


def test_records_that_are_not_valid_are_skipped():
    out = _node("""console.log(JSON.stringify(pb.cleanDocs([
      {id: "a", title: "ok"}, null, 42, "x", {title: "no id"}, {id: "b"}, {id: "c", title: "fine"}]).map(d => d.id)));""")
    assert out == ["a", "c"]


def test_cards_show_title_status_phases_and_next_action():
    doc = _doc(title="Sort Queue", status="Paused", pauseReason="Waiting on a call",
               nextAction="Pick the next phase", phase="Implementation",
               phases=[{"name": "Requirements", "state": "done"}, {"name": "Design", "state": "done"},
                       {"name": "Tasks", "state": "done"}, {"name": "Implementation", "state": "paused"}])
    out = _node(f"""const root = new Node("div");
      pb.renderBoard(root, [{json.dumps(doc)}], {{}}, Date.UTC(2026, 8, 30, 12));
      console.log(JSON.stringify(allText(root)));""")
    for needle in ("Sort Queue", "Paused", "Waiting on a call", "Pick the next phase",
                   "Requirements", "Implementation", "yesterday"):
        assert needle in out, needle


def test_hostile_record_text_stays_text():
    # A different marker per field, so stripping or escaping any one field is noticed.
    payload = '<img src=x onerror="alert(1)">'
    fields = {"title": "T" + payload, "goal": "G" + payload, "nextAction": "N" + payload,
              "project": "P" + payload}
    doc = _doc(status="Paused", pauseReason="R" + payload, **fields)
    out = _node(f"""const root = new Node("div");
      pb.renderBoard(root, [{json.dumps(doc)}], {{}}, Date.UTC(2026, 8, 30, 12));
      console.log(JSON.stringify({{ tags: allNodes(root).map(n => n.tag), text: allText(root) }}));""")
    assert "img" not in out["tags"] and len(out["tags"]) > 5  # the helper really walked the tree
    for value in list(fields.values()) + ["R" + payload]:
        assert value in out["text"], value


def test_unknown_states_fall_back_to_a_safe_class():
    doc = _doc(status='x" onclick="boom', phases=[{"name": "Design", "state": 'evil" onmouseover="x'}])
    out = _node(f"""const root = new Node("div");
      pb.renderBoard(root, [{json.dumps(doc)}], {{}}, Date.UTC(2026, 8, 30, 12));
      console.log(JSON.stringify({{ classes: allNodes(root).map(n => n.className), text: allText(root) }}));""")
    for cls in out["classes"]:
        assert re.fullmatch(r"[a-z0-9 _-]*", cls), cls
    # An unknown phase state is drawn as pending, never as the string "undefined".
    assert "undefined" not in out["text"] and "undefined" not in " ".join(out["classes"])
    assert "○ Design" in out["text"] and "ph-pending" in " ".join(out["classes"])


def _board_text(docs, opts):
    return _node(f"""const root = new Node("div");
      pb.renderBoard(root, {json.dumps(docs)}, {json.dumps(opts)}, {NOW});
      console.log(JSON.stringify({{ text: allText(root), nodes: allNodes(root).map(n => [n.tag, n.className, n.attrs]) }}));""")


def test_open_view_hides_closed_features_and_filters_by_project():
    # Replaces the old "Hide complete" toggle: the Open view never lists closed features.
    docs = [_doc(id="1", title="Open one", project="a", status="In Progress"),
            _doc(id="2", title="Done one", project="a", status="Complete"),
            _doc(id="3", title="Other project", project="b", status="In Progress")]
    out = _board_text(docs, {"project": "a", "view": "open"})["text"]
    assert "Open one" in out and "Done one" not in out and "Other project" not in out
    assert "Open one" in _board_text(docs, {"project": "a"})["text"]  # open is the default view


def test_closed_view_lists_recent_closed_only_and_a_separate_archive():
    docs = [_doc(id="o", title="Open one")] + [_closed(i, "2026-10-01") for i in range(10)] + [_closed(99, "2026-01-01")]
    out = _board_text(docs, {"view": "closed"})["text"]
    assert "Open one" not in out and "c0" in out
    assert "Archive" in out and "c99" in out
    assert "Archive" not in _board_text(docs, {"view": "open"})["text"]


def test_selected_feature_fills_the_detail_pane_even_from_the_archive():
    docs = [_doc(id="o", title="Open one", schema=2, brief=BRIEF)] + [_closed(i, "2026-10-01") for i in range(10)] \
        + [_closed(99, "2026-01-01", schema=2, brief={"goal": "Old goal", "decisions": ["Old decision"]})]
    assert "Merge into Plan Board" in _board_text(docs, {"selectedId": "o"})["text"]
    out = _board_text(docs, {"view": "closed", "selectedId": "c99"})
    assert "Old decision" in out["text"]
    assert any(n[1] == "detail" for n in out["nodes"])
    assert not any(n[1] == "detail" for n in _board_text(docs, {})["nodes"])


def test_brief_board_link_only_for_https_urls():
    docs = [_doc(id="1", title="One", briefBoardUrl="https://claude.ai/artifact/BRIEFS")]
    nodes = _board_text(docs, {})["nodes"]
    assert [n[2].get("href") for n in nodes if n[0] == "a"] == ["https://claude.ai/artifact/BRIEFS"]
    for bad in ("javascript:alert(1)", "http://x", ""):
        assert not [n for n in _board_text([_doc(id="1", title="One", briefBoardUrl=bad)], {})["nodes"] if n[0] == "a"]
    assert not [n for n in _board_text([_doc(id="1", title="One")], {})["nodes"] if n[0] == "a"]


def test_empty_views_have_a_message():
    docs = [_doc(id="1", title="Open one")]
    assert "closed" in _board_text(docs, {"view": "closed"})["text"].lower()
    assert "No features yet" in _board_text([], {})["text"]
    assert "No features match" in _board_text(docs, {"project": "nope"})["text"]


def test_the_templates_pause_statuses_are_paused_in_ranking_counts_and_chips():
    docs = [_doc(id="a", title="a", status="Awaiting Confirmation"),
            _doc(id="b", title="b", status="Awaiting Implementation Request"),
            _doc(id="c", title="c", status="Blocked"),
            _doc(id="d", title="d", status="In Progress"),
            _doc(id="e", title="e", status="Complete")]
    out = _node(f"""const docs = {json.dumps(docs)};
      console.log(JSON.stringify({{ order: pb.sortDocs(docs).map(d => d.id), counts: pb.countByStatus(docs) }}));""")
    assert out["order"][0] == "d" and out["order"][-1] == "e"
    assert out["counts"] == {"active": 1, "paused": 3, "complete": 1, "other": 0, "total": 5}


def test_a_blocked_or_awaiting_feature_shows_its_reason_and_the_right_chip():
    docs = [_doc(id="1", title="Held", status="Awaiting Confirmation", pauseReason="Needs your sign-off"),
            _doc(id="2", title="Stuck", status="Blocked", pauseReason="Waiting on a fix")]
    out = _node(f"""const root = new Node("div");
      pb.renderBoard(root, {json.dumps(docs)}, {{}}, Date.UTC(2026, 8, 30, 12));
      console.log(JSON.stringify({{ text: allText(root), classes: allNodes(root).map(n => n.className) }}));""")
    assert "Needs your sign-off" in out["text"] and "Waiting on a fix" in out["text"]
    joined = " ".join(out["classes"])
    assert "st-paused" in joined and "st-blocked" in joined


# ---------------------------------------------------------------- partition (Slice 19)

NOW = "Date.UTC(2026, 9, 2, 12)"  # 2026-10-02


def _closed(i, day, **kw):
    return _doc(id=f"c{i}", title=f"c{i}", status="Complete", closedAt=day, updatedAt=day, **kw)


def _ids(parts):
    return {k: [d["id"] for d in v] for k, v in parts.items()}


def test_partition_splits_open_recent_and_archive_by_the_14_day_window():
    docs = [_doc(id="o1", title="o1"), _doc(id="o2", title="o2", status="Paused"),
            _closed(1, "2026-10-01")] + [_closed(i, "2026-10-01") for i in range(10, 19)] \
        + [_closed(2, "2026-09-18"), _closed(3, "2026-09-17")]  # 11th and 12th: only the window can save them
    out = _node(f"console.log(JSON.stringify(pb.partition({json.dumps(docs)}, {NOW})));")
    ids = {k: [d["id"] for d in v] for k, v in out.items()}
    assert ids["open"] == ["o1", "o2"]
    assert "c2" in ids["recent"] and len(ids["recent"]) == 11  # 14 days old is still inside
    assert ids["archive"] == ["c3"]  # 15 days old, outside the top ten


def test_partition_keeps_the_ten_most_recent_even_when_older_than_the_window():
    docs = [_closed(i, f"2026-0{1 + i // 10}-{10 + i % 10:02d}") for i in range(12)]
    out = _node(f"console.log(JSON.stringify(pb.partition({json.dumps(docs)}, {NOW})));")
    assert len(out["recent"]) == 10 and len(out["archive"]) == 2 and out["open"] == []
    newest = max(d["closedAt"] for d in out["archive"])
    assert all(d["closedAt"] >= newest for d in out["recent"])


def test_partition_union_when_more_than_ten_are_inside_the_window():
    docs = [_closed(i, f"2026-09-{20 + i % 10:02d}") for i in range(12)]
    out = _node(f"console.log(JSON.stringify(pb.partition({json.dumps(docs)}, {NOW})));")
    assert len(out["recent"]) == 12 and out["archive"] == []


def test_partition_schema_1_complete_docs_fall_back_to_updated_at():
    old = _doc(id="s1", title="s1", status="Complete", updatedAt="2026-01-01")
    new = _doc(id="s2", title="s2", status="Complete", updatedAt="2026-10-01")
    out = _node(f"console.log(JSON.stringify(pb.partition([{json.dumps(old)}], {NOW})));")
    assert [d["id"] for d in out["recent"]] == ["s1"]  # inside the top 10
    many = [_closed(i, "2026-02-01") for i in range(10)] + [old, new]
    out = _node(f"console.log(JSON.stringify(pb.partition({json.dumps(many)}, {NOW})));")
    assert "s2" in [d["id"] for d in out["recent"]] and "s1" in [d["id"] for d in out["archive"]]


def test_partition_orders_are_deterministic_newest_first_then_id():
    docs = [_closed(2, "2026-10-01"), _closed(1, "2026-10-01"), _closed(3, "2026-10-02")]
    out = _node(f"console.log(JSON.stringify(pb.partition({json.dumps(docs)}, {NOW})));")
    assert [d["id"] for d in out["recent"]] == ["c3", "c1", "c2"]


# ---------------------------------------------------------------- renderBrief (Slice 20)

BRIEF = {"goal": "Ship the brief", "requirements": {"state": "Approved", "openGaps": ["Window size"]},
         "design": {"state": "Approved", "summary": "Schema 2 adds a brief", "risks": [{"text": "Hook is reminder only"}],
                    "openQuestions": ["Doc size limit?"]},
         "slices": {"total": 24, "done": None, "items": [{"n": 1, "title": "Helper", "tier": "standard"}]},
         "decisions": ["Merge into Plan Board"], "openItems": [{"kind": "Risks", "text": "Partial slice progress"}]}


def _brief_text(doc):
    return _node(f"""const root = new Node("div");
      pb.renderBrief(root, {json.dumps(doc)});
      console.log(JSON.stringify({{ text: allText(root), tags: allNodes(root).map(n => n.tag) }}));""")


def test_render_brief_shows_every_section():
    out = _brief_text(_doc(schema=2, brief=BRIEF, nextAction="Slice 3"))
    for needle in ("Ship the brief", "Approved", "Window size", "Schema 2 adds a brief", "Hook is reminder only",
                   "Doc size limit?", "24 slices", "Helper", "standard", "Merge into Plan Board",
                   "Partial slice progress", "Slice 3"):
        assert needle in out["text"], needle
    assert "done" not in out["text"].replace("Approved", "")  # done count unknown: not shown


def test_render_brief_shows_done_count_only_when_known():
    brief = dict(BRIEF, slices={"total": 4, "done": 2, "items": []})
    assert "2 done" in _brief_text(_doc(schema=2, brief=brief))["text"]


def test_render_brief_schema_1_doc_shows_status_fields_only():
    out = _brief_text(_doc(nextAction="Do the thing", status="Paused", pauseReason="Waiting"))
    for needle in ("Feature", "Paused", "Design", "Do the thing", "Waiting"):
        assert needle in out["text"], needle
    assert "undefined" not in out["text"]


def test_render_brief_partial_brief_does_not_crash():
    out = _brief_text(_doc(schema=2, brief={"goal": "g", "design": {"state": "Draft"}, "slices": "junk", "openItems": [None]}))
    assert "Draft" in out["text"] and "undefined" not in out["text"]


def test_render_brief_hostile_text_stays_text():
    payload = '<img src=x onerror="alert(1)">'
    brief = {"goal": "G" + payload, "decisions": ["D" + payload], "design": {"state": "S", "risks": [{"text": "R" + payload}]}}
    out = _brief_text(_doc(schema=2, brief=brief))
    assert "img" not in out["tags"]
    for v in ("G" + payload, "D" + payload, "R" + payload):
        assert v in out["text"]
