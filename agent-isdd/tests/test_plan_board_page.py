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


def test_hiding_complete_and_filtering_by_project():
    docs = [_doc(id="1", title="Open one", project="a", status="In Progress"),
            _doc(id="2", title="Done one", project="a", status="Complete"),
            _doc(id="3", title="Other project", project="b", status="In Progress")]
    out = _node(f"""const root = new Node("div");
      pb.renderBoard(root, {json.dumps(docs)}, {{hideComplete: true, project: "a"}}, Date.UTC(2026, 8, 30, 12));
      console.log(JSON.stringify(allText(root)));""")
    assert "Open one" in out and "Done one" not in out and "Other project" not in out


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
