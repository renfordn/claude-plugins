"""hooks/plan_board_sync.py CLI: verify / resync / prune / mark."""
import json
import os
import subprocess
import sys

import hook_test_utils as h

HOOKS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hooks")
sys.path.insert(0, HOOKS)

import plan_board  # noqa: E402
import plan_board_sync  # noqa: E402

URL = "https://claude.ai/artifact/PLANBOARD123"


def _mem(tmp_path, sync_line=""):
    mem = tmp_path / "mem"
    for slug in ("2026-09-01-a", "2026-09-02-b"):
        h.seed_state_file(str(mem / "spec" / slug), title=slug, slug=slug,
                          current_phase="Design", workflow_status="In Progress")
    (mem / "PLAN-BOARD.md").write_text(f"# Plan Board\n\n- URL: {URL}\n{sync_line}")
    return mem


def _run(mem, *args):
    p = subprocess.run([sys.executable, os.path.join(HOOKS, "plan_board_sync.py"), *args,
                        "--memory-dir", str(mem), "--project", "proj"], capture_output=True, text=True)
    return p.returncode, p.stdout, p.stderr


def _board(tmp_path, records):
    f = tmp_path / "board.json"
    f.write_text(json.dumps(records))
    return str(f)


def _doc(mem, slug):
    return plan_board.build_doc(str(mem / "spec" / slug / "workflow-state.md"), project="proj")


def test_verify_reports_the_diff_and_stamps_last_verified(tmp_path):
    mem = _mem(tmp_path)
    a = _doc(mem, "2026-09-01-a")
    board = _board(tmp_path, [{"id": a["id"], "contentHash": "stale"},
                              {"id": "proj--gone", "contentHash": "x"}, {"id": "other--x", "contentHash": "x"}])
    rc, out, _ = _run(mem, "verify", "--board-json", board)
    assert rc == 0
    report = json.loads(out)
    assert report["missing"] == ["proj--2026-09-02-b"]
    assert report["mismatched"] == [a["id"]]
    assert report["orphaned"] == ["proj--gone"]  # other project's record is not ours to judge
    assert plan_board_sync.last_verified(str(mem)) is not None


def test_resync_prints_the_batch_and_mark_records_only_named_ids(tmp_path):
    mem = _mem(tmp_path)
    rc, out, _ = _run(mem, "resync")
    batch = json.loads(out)
    assert rc == 0 and len(batch["writes"]) == 2
    a = _doc(mem, "2026-09-01-a")["id"]
    rc, out, _ = _run(mem, "mark", a)
    assert rc == 0 and a in out
    assert list(json.loads((mem / "plan-board-sync.json").read_text())) == [a]


def test_prune_without_confirm_only_lists(tmp_path):
    mem = _mem(tmp_path)
    (mem / "plan-board-sync.json").write_text(json.dumps({"proj--gone": "h"}))
    rc, out, _ = _run(mem, "prune")
    assert rc == 0 and "proj--gone" in out
    assert "proj--gone" in (mem / "plan-board-sync.json").read_text()
    rc, out, _ = _run(mem, "prune", "--confirm")
    assert rc == 0 and "proj--gone" in out
    assert "proj--gone" not in (mem / "plan-board-sync.json").read_text()


def test_bad_args_exit_nonzero_with_one_stderr_line(tmp_path):
    mem = _mem(tmp_path)
    rc, _out, err = _run(mem, "verify")  # no --board-json
    assert rc == 2 and len(err.strip().splitlines()) == 1
    rc, _out, err = _run(mem, "bogus")
    assert rc == 2 and len(err.strip().splitlines()) == 1


def test_sync_off_is_silent_and_exit_zero(tmp_path):
    mem = _mem(tmp_path, "- Sync: off\n")
    for args in (("verify", "--board-json", _board(tmp_path, [])), ("resync",), ("prune",)):
        rc, out, err = _run(mem, *args)
        assert (rc, out, err) == (0, "", "")
