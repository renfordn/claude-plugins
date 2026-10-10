"""plan_board_sync.py all <verify|resync|prune|mark>: one central run over every project under
sdd-memory/ that uses the shared board. Projects are labelled by their sync-file ids; a card is an
orphan only when no project has that feature."""
import json
import os
import subprocess
import sys

import hook_test_utils as h

HOOKS = h.HOOKS_DIR
sys.path.insert(0, HOOKS)
import plan_board  # noqa: E402

URL = "https://claude.ai/artifact/SHARED"


def _project(base, slug, label, features):
    mem = os.path.join(base, slug)
    docs = {}
    for f in features:
        d = os.path.join(mem, "spec", f)
        state = h.seed_state_file(d, title=f, slug=f, current_phase="Design", workflow_status="In Progress")
        docs[f] = plan_board.build_doc(state, project=label)
    with open(os.path.join(mem, "plan-board-sync.json"), "w") as fh:
        json.dump({d["id"]: "old" for d in docs.values()}, fh)
    return mem, docs


def _setup(tmp_path):
    base = str(tmp_path / "sdd-memory")
    os.makedirs(base)
    with open(os.path.join(base, "PLAN-BOARD.md"), "w") as fh:
        fh.write(f"# Plan Board\n\n- URL: {URL}\n")
    a_mem, a = _project(base, "users-me-alpha", "alpha", ["2026-10-01-a1", "2026-10-02-a2"])
    b_mem, b = _project(base, "users-me-beta", "beta", ["2026-10-03-b1"])
    os.makedirs(os.path.join(base, "users-me-nolabel", "spec", "2026-10-04-n1"))
    board = [{"id": a["2026-10-01-a1"]["id"], "contentHash": a["2026-10-01-a1"]["contentHash"], "version": "v1"},
             {"id": a["2026-10-02-a2"]["id"], "contentHash": "stale", "version": "v2"},
             {"id": "gone--2026-01-01-x", "contentHash": "h", "version": "v3"}]
    dump = str(tmp_path / "board.json")
    with open(dump, "w") as fh:
        json.dump(board, fh)
    return base, dump, a, b, a_mem


def _run(base, *args):
    p = subprocess.run([sys.executable, os.path.join(HOOKS, "plan_board_sync.py"), "all", *args,
                        "--base", base], capture_output=True, text=True, timeout=20)
    assert p.returncode == 0, p.stderr
    return p.stdout


def test_verify_covers_every_project_and_only_true_orphans(tmp_path):
    base, dump, a, b, _ = _setup(tmp_path)
    out = json.loads(_run(base, "verify", "--board-json", dump))
    assert out["projects"]["alpha"] == {"missing": [], "mismatched": [a["2026-10-02-a2"]["id"]]}
    assert out["projects"]["beta"] == {"missing": [b["2026-10-03-b1"]["id"]], "mismatched": []}
    assert out["orphaned"] == ["gone--2026-01-01-x"]
    assert out["skipped"] == ["users-me-nolabel"]


def test_resync_is_one_batch_across_projects_and_mark_routes_by_id(tmp_path):
    base, dump, a, b, a_mem = _setup(tmp_path)
    batch = json.loads(_run(base, "resync", "--board-json", dump))
    assert sorted(batch["ids"]) == sorted([a["2026-10-02-a2"]["id"], b["2026-10-03-b1"]["id"]])
    w = {x["doc_id"]: x for x in batch["writes"]}
    assert w[a["2026-10-02-a2"]["id"]]["if_version"] == "v2"
    assert "if_version" not in w[b["2026-10-03-b1"]["id"]]
    _run(base, "mark", *batch["ids"])
    assert plan_board._read_sync(a_mem)[a["2026-10-02-a2"]["id"]] == a["2026-10-02-a2"]["contentHash"]


def test_prune_lists_board_only_orphans_and_deletes_only_on_confirm(tmp_path):
    base, dump, *_ = _setup(tmp_path)
    assert "gone--2026-01-01-x" in _run(base, "prune", "--board-json", dump)
    out = json.loads(_run(base, "prune", "--board-json", dump, "--confirm"))
    assert out["board_instructions"] == [{"op": "delete", "collection": "plans",
                                          "doc_id": "gone--2026-01-01-x", "if_version": "v3"}]


def test_cards_of_skipped_or_sync_off_projects_are_never_orphans(tmp_path):
    base, dump, *_ = _setup(tmp_path)
    off = os.path.join(base, "users-me-off")
    os.makedirs(os.path.join(off, "spec", "2026-10-05-off1"))
    with open(os.path.join(off, "PLAN-BOARD.md"), "w") as fh:
        fh.write(f"- URL: {URL}\n- Sync: off\n")
    board = json.load(open(dump)) + [
        {"id": "nolabel--2026-10-04-n1", "contentHash": "h", "version": "v4"},
        {"id": "off--2026-10-05-off1", "contentHash": "h", "version": "v5"}]
    json.dump(board, open(dump, "w"))
    out = json.loads(_run(base, "verify", "--board-json", dump))
    assert out["orphaned"] == ["gone--2026-01-01-x"]
    deletes = json.loads(_run(base, "prune", "--board-json", dump, "--confirm"))["board_instructions"]
    assert [d["doc_id"] for d in deletes] == ["gone--2026-01-01-x"]
