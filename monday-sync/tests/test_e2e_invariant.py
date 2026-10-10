"""End-to-end invariant (F5): Stuck pull -> apply isdd_updates -> re-plan is quiet -> record ->
flag_sync silent -> a second sync makes 0 writes. Runs the real CLI and hook as subprocesses."""
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLI = os.path.join(ROOT, "hooks", "cli.py")
HOOK = os.path.join(ROOT, "hooks", "flag_sync.py")
sys.path.insert(0, os.path.join(ROOT, "hooks"))

import planner  # noqa: E402

S, N = planner.STATUS_COL, planner.NOTES_COL
STATE = ("- Title: Feature X\n- Current Phase: Implementation\n- Workflow Status: In Progress\n"
         "- Pause Reason: None\n- Next Action: build\n- Hook Notes: ok\n")


def env(data):
    return dict(os.environ, CLAUDE_PLUGIN_DATA=str(data))


def cli(data, *args):
    proc = subprocess.run([sys.executable, CLI, *map(str, args)], capture_output=True, text=True,
                          env=env(data))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    return json.loads(proc.stdout)


def hook(data, path):
    payload = json.dumps({"tool_name": "Edit", "tool_input": {"file_path": str(path)}})
    proc = subprocess.run([sys.executable, HOOK], input=payload, capture_output=True, text=True,
                          env=env(data))
    assert proc.returncode == 0
    return proc.stdout.strip()


def write_item(path, item):
    path.write_text(json.dumps({"id": item["id"], "updates": item["updates"],
                                "column_values": {S: item["status"], N: item["notes"]}}))


def apply(item, writes):
    item = dict(item)
    item["status"] = writes.get(S, item["status"])
    item["notes"] = writes.get(N, item["notes"])
    return item


def sync(tmp_path, data, d, item):
    """The SKILL.md sequence: begin, plan, write, apply isdd_updates, re-plan, record, clear."""
    f = tmp_path / "item.json"
    cli(data, "sync-begin", d)
    write_item(f, item)
    p = cli(data, "plan", d, "--item", f)
    item = apply(item, p["writes"])
    state = d / "workflow-state.md"
    for field, value in p["isdd_updates"].items():            # the Edit tool, one line each
        text = state.read_text()
        old = next(l for l in text.splitlines() if l.startswith(f"- {field}:"))
        state.write_text(text.replace(old, f"- {field}: {value}"))
        assert hook(data, state) == ""                       # no nudge mid-sync
    write_item(f, item)
    re = cli(data, "plan", d, "--item", f)
    snap = tmp_path / "replan.json"
    snap.write_text(json.dumps(re))
    cli(data, "record", d, "--snapshot", snap)
    assert cli(data, "pending", "clear", d, "--expect-hash", re["state_hash"])["cleared"] is True
    return p, re, item


def test_stuck_pull_round_trip_settles(tmp_path):
    data = tmp_path / "data"
    d = tmp_path / "spec" / "2026-09-30-x"
    d.mkdir(parents=True)
    (d / "workflow-state.md").write_text(STATE)
    cli(data, "record", d, "--item-id", "1", "--project", "p")
    item = {"id": "1", "status": "To do", "notes": "", "updates": []}
    _, _, item = sync(tmp_path, data, d, item)                  # initial sync

    item["status"] = "Stuck"                                    # user blocks it on the board
    item["updates"] = [{"id": "u1", "body": "waiting on API key", "created_at": "2026-09-30T12:00:00Z"}]
    p, re, item = sync(tmp_path, data, d, item)
    assert p["isdd_updates"]["Workflow Status"] == "Blocked" and p["writes"] == {}
    assert re["writes"] == {} and re["isdd_updates"] == {}
    assert re["snapshot"]["synced_fields"]["workflow_status"] == "Blocked"
    assert "- Hook Notes: waiting on API key" in (d / "workflow-state.md").read_text()

    assert hook(data, d / "workflow-state.md") == ""            # recorded state == file state
    f = tmp_path / "item.json"
    write_item(f, item)
    again = cli(data, "plan", d, "--item", f)
    assert again["writes"] == {} and again["isdd_updates"] == {} and again["conflicts"] == []
