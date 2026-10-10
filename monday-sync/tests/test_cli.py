"""cli.py subcommands, run as subprocesses the way the skill runs them."""
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLI = os.path.join(ROOT, "hooks", "cli.py")
sys.path.insert(0, os.path.join(ROOT, "hooks"))

import planner  # noqa: E402

STATE = "- Title: Feature X\n- Current Phase: Design\n- Workflow Status: In Progress\n- Next Action: approve\n"


def cli(*args, data=None):
    env = dict(os.environ)
    env.pop("CLAUDE_PLUGIN_DATA", None)
    if data:
        env["CLAUDE_PLUGIN_DATA"] = str(data)
    proc = subprocess.run([sys.executable, CLI, *map(str, args)], capture_output=True, text=True, env=env)
    return proc.returncode, json.loads(proc.stdout) if proc.stdout.strip() else None


def feature(tmp_path, name="2026-09-30-x"):
    d = tmp_path / "spec" / name
    d.mkdir(parents=True)
    (d / "workflow-state.md").write_text(STATE, encoding="utf-8")
    return d


def test_plan_reads_state_sidecar_and_item_files(tmp_path):
    d = feature(tmp_path)
    item = tmp_path / "item.json"
    item.write_text(json.dumps({"id": "5", "column_values": {planner.STATUS_COL: "To do"},
                                "group": {"title": "Backlog"}}))
    (d / "monday.json").write_text(json.dumps({"item_id": "5"}))
    rc, out = cli("plan", d, "--item", item)
    assert rc == 0 and out["create"] is False
    assert out["writes"][planner.NOTES_COL] == "Phase: Design · Next: approve · Spec: 2026-09-30-x"


def test_record_merges_sidecar_snapshot_and_links(tmp_path):
    d, data = feature(tmp_path), tmp_path / "data"
    rc, out = cli("plan", d)
    snap = tmp_path / "plan.json"
    snap.write_text(json.dumps(out))
    rc, _ = cli("record", d, "--item-id", "77", "--project", "file-organiser", "--snapshot", snap, data=data)
    sc = json.loads((d / "monday.json").read_text())
    assert rc == 0 and sc["item_id"] == "77" and sc["project"] == "file-organiser"
    assert sc["state_hash"] == out["state_hash"]
    assert json.loads((data / "store.json").read_text())["linked"] == {os.path.realpath(d): "77"}


def test_pending_clear_refused_when_state_changed_since_plan(tmp_path):
    d, data = feature(tmp_path), tmp_path / "data"
    import store
    os.environ["CLAUDE_PLUGIN_DATA"] = str(data)
    try:
        store.add_pending(str(d))
    finally:
        del os.environ["CLAUDE_PLUGIN_DATA"]
    rc, listed = cli("pending", "list", data=data)
    assert listed == [{"dir": os.path.realpath(d), "title": "Feature X", "slug": "2026-09-30-x"}]
    rc, out = cli("pending", "clear", d, "--expect-hash", "0000000000000000", data=data)
    assert out["cleared"] is False
    rc, out = cli("pending", "clear", d, "--expect-hash", planner.state_hash(STATE), data=data)
    assert out["cleared"] is True and cli("pending", "list", data=data)[1] == []


def test_candidates_excludes_linked_and_dismissed(tmp_path):
    data = tmp_path / "data"
    items = tmp_path / "items.json"
    todo = lambda i: {"id": i, "name": f"[p] {i}", "group": {"title": "Backlog"},
                      "column_values": {planner.STATUS_COL: "To do"}}
    items.write_text(json.dumps([todo("1"), todo("2"), todo("3")]))
    d = feature(tmp_path)
    cli("record", d, "--item-id", "1", data=data)
    cli("candidates", "--dismiss", "3", data=data)
    rc, out = cli("candidates", "--items", items, data=data)
    assert out == [{"id": "2", "name": "[p] 2"}]


def test_store_commands_without_plugin_data_fail_with_json_error(tmp_path):
    rc, out = cli("pending", "list")
    assert rc == 2 and "CLAUDE_PLUGIN_DATA" in out["error"]


def _linked_feature(tmp_path):
    d = feature(tmp_path)
    (d / "monday.json").write_text(json.dumps({"item_id": "5"}))
    return d


def test_plan_on_linked_feature_needs_item_or_item_missing(tmp_path):
    rc, out = cli("plan", _linked_feature(tmp_path))
    assert rc == 2 and "--item-missing" in out["error"]


def test_plan_item_missing_flag_is_the_only_way_to_recreate(tmp_path):
    rc, out = cli("plan", _linked_feature(tmp_path), "--item-missing")
    assert rc == 0 and out["recreate"] == "recreate"


def test_plan_accepts_single_item_in_list_or_items_wrapper_but_not_several(tmp_path):
    d = _linked_feature(tmp_path)
    one = {"id": "5", "column_values": {planner.STATUS_COL: "To do"}}
    for shape in ([one], {"items": [one]}, one):
        f = tmp_path / "i.json"
        f.write_text(json.dumps(shape))
        rc, out = cli("plan", d, "--item", f)
        assert rc == 0 and out["create"] is False
    f.write_text(json.dumps([one, one]))
    rc, out = cli("plan", d, "--item", f)
    assert rc == 2 and "exactly one" in out["error"]


def test_record_unlink_removes_linked_entry(tmp_path):
    d, data = feature(tmp_path), tmp_path / "data"
    cli("record", d, "--item-id", "9", data=data)
    cli("record", d, "--unlink", data=data)
    assert json.loads((data / "store.json").read_text())["linked"] == {}
    assert json.loads((d / "monday.json").read_text())["item_id"] is None


def test_accept_board_status_persists_the_answer(tmp_path):
    d = _linked_feature(tmp_path)
    rc, out = cli("record", d, "--accept-board-status", "Done")
    sc = json.loads((d / "monday.json").read_text())
    assert rc == 0 and sc["last_pushed"]["status"] == "Done" and sc["last_pushed"]["source"] == "user"
    assert sc["confirmed_done"] is True
    assert sc["accepted_fields"] == {"phase": "Design", "workflow_status": "In Progress", "git": None}
    item = tmp_path / "i.json"
    item.write_text(json.dumps({"id": "5", "column_values": {planner.STATUS_COL: "Done"}}))
    rc, out = cli("plan", d, "--item", item)
    assert out["conflicts"] == [] and planner.STATUS_COL not in out["writes"]


def test_accept_board_status_takes_the_kickoff_labels_and_rejects_unknown(tmp_path):
    d = _linked_feature(tmp_path)
    for label in ("Gather Requirements", "Implementation Ready"):
        rc, out = cli("record", d, "--accept-board-status", label)
        sc = json.loads((d / "monday.json").read_text())
        assert rc == 0 and sc["last_pushed"] == dict(sc["last_pushed"], status=label, source="user")
    rc, out = cli("record", d, "--accept-board-status", "Nope")
    assert rc == 2 and "Implementation Ready" in out["error"]


def test_unlink_opts_out_and_relink_opts_back_in(tmp_path):
    d, data = _linked_feature(tmp_path), tmp_path / "data"
    os.environ["CLAUDE_PLUGIN_DATA"] = str(data)
    try:
        import store
        store.add_pending(str(d))
    finally:
        del os.environ["CLAUDE_PLUGIN_DATA"]
    cli("record", d, "--unlink", data=data)
    sc = json.loads((d / "monday.json").read_text())
    assert sc["unlinked"] is True and sc["item_id"] is None
    assert cli("pending", "list", data=data)[1] == []
    rc, out = cli("plan", d)
    assert rc == 0 and out["skipped"] == "unlinked" and out["create"] is False
    cli("record", d, "--item-id", "8", data=data)
    assert json.loads((d / "monday.json").read_text())["unlinked"] is False


def test_forget_item_turns_a_missing_item_into_a_plain_create(tmp_path):
    d = _linked_feature(tmp_path)
    sc = json.loads((d / "monday.json").read_text())
    sc["recreated_from"] = "4"
    (d / "monday.json").write_text(json.dumps(sc))
    assert cli("plan", d, "--item-missing")[1]["recreate"] == "ask"
    cli("record", d, "--forget-item")
    rc, out = cli("plan", d)
    assert rc == 0 and out["create"] is True and out["recreate"] is None


def test_sync_begin_marks_and_record_snapshot_clears(tmp_path):
    d = _linked_feature(tmp_path)
    rc, out = cli("sync-begin", d)
    assert rc == 0 and json.loads((d / "monday.json").read_text())["syncing_since"]
    cli("record", d, "--project", "p")
    assert json.loads((d / "monday.json").read_text())["syncing_since"]
    snap = tmp_path / "s.json"
    snap.write_text(json.dumps({"snapshot": {"state_hash": "x"}}))
    cli("record", d, "--snapshot", snap)
    assert json.loads((d / "monday.json").read_text())["syncing_since"] is None


def test_accept_board_status_pins_git_state(tmp_path):
    d = _linked_feature(tmp_path)
    g = tmp_path / "git.json"
    g.write_text(json.dumps({"on_origin": True, "ahead": 1, "head": "h1", "merged": False}))
    cli("record", d, "--accept-board-status", "In progress", "--git", g)
    sc = json.loads((d / "monday.json").read_text())
    assert sc["accepted_fields"]["git"] == {"head": "h1", "on_origin": True, "merged": False}


def test_recreate_is_remembered_so_a_second_deletion_asks(tmp_path):
    d = _linked_feature(tmp_path)
    rc, p = cli("plan", d, "--item-missing")
    assert p["recreate"] == "recreate"
    pf = tmp_path / "plan.json"
    pf.write_text(json.dumps(p))
    cli("record", d, "--item-id", "6", "--snapshot", pf)          # SKILL create path
    item = tmp_path / "new.json"
    item.write_text(json.dumps({"id": "6", "column_values": {
        planner.STATUS_COL: p["writes"][planner.STATUS_COL], planner.NOTES_COL: p["writes"][planner.NOTES_COL]}}))
    rc, re = cli("plan", d, "--item", item)
    assert re["writes"] == {}
    rf = tmp_path / "replan.json"
    rf.write_text(json.dumps(re))
    cli("record", d, "--snapshot", rf)
    assert json.loads((d / "monday.json").read_text())["recreated_from"] == "5"
    assert cli("plan", d, "--item-missing")[1]["recreate"] == "ask"


def test_replan_snapshot_carries_recreated_from_forward(tmp_path):
    d = _linked_feature(tmp_path)
    sc = json.loads((d / "monday.json").read_text())
    sc["recreated_from"] = "4"
    (d / "monday.json").write_text(json.dumps(sc))
    item = tmp_path / "i.json"
    item.write_text(json.dumps({"id": "5", "column_values": {planner.STATUS_COL: "To do"}}))
    assert cli("plan", d, "--item", item)[1]["snapshot"]["recreated_from"] == "4"


def _gr_items(tmp_path, project="file-organiser"):
    f = tmp_path / "kick.json"
    f.write_text(json.dumps({"items": [{"id": "42", "name": "[file-organiser] Idea", "created_at": "2026-09-30T10:00:00Z",
                                        "column_values": {planner.STATUS_COL: "Gather Requirements",
                                                          planner.PROJECT_COL: project},
                                        "updates": []}]}))
    return f


def test_kickoff_candidates_uses_the_default_project_map_without_plugin_data(tmp_path):
    rc, out = cli("kickoff-candidates", "--items", _gr_items(tmp_path), "--now", "2026-10-01T12:00:00Z")
    assert rc == 0 and out == {"pick": {"id": "42", "name": "[file-organiser] Idea", "project": "file-organiser",
                                        "repo_path": "~/Codebase/AI/file-organiser", "attempt": 1},
                               "needs_project": [], "stuck": []}


def test_kickoff_candidates_project_map_override_and_bad_now(tmp_path):
    m = tmp_path / "map.json"
    m.write_text(json.dumps({"other": "~/src/other"}))
    items = _gr_items(tmp_path, project="other")
    rc, out = cli("kickoff-candidates", "--items", items, "--now", "2026-10-01T12:00:00Z", "--project-map", m)
    assert rc == 0 and out["pick"]["repo_path"] == "~/src/other"
    rc, out = cli("kickoff-candidates", "--items", items, "--now", "yesterday")
    assert rc == 2 and "--now" in out["error"]


def test_kickoff_candidates_spec_index_excludes_linked_tickets(tmp_path):
    idx = tmp_path / "index.json"
    idx.write_text(json.dumps([{"title": "Idea", "item_id": None, "dir": "~/r/spec/2026-09-01-idea"}]))
    rc, out = cli("kickoff-candidates", "--items", _gr_items(tmp_path), "--now", "2026-10-01T12:00:00Z",
                  "--spec-index", idx)
    assert rc == 0 and out["pick"] is None
    idx.write_text(json.dumps({"title": "Idea"}))
    rc, out = cli("kickoff-candidates", "--items", _gr_items(tmp_path), "--now", "2026-10-01T12:00:00Z",
                  "--spec-index", idx)
    assert rc == 2 and "--spec-index" in out["error"]
