"""hooks/session_start.py -- the Plan Board backstop.

The workflow step is what normally keeps the board current. This hook is the safety net: when a
project has a Plan Board and any feature's record is missing or out of date, the session is told
which features and exactly what to run, so a missed update is noticed at the next session start.
"""
import os
import sys

import hook_test_utils as h

HOOKS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hooks")
sys.path.insert(0, HOOKS)

import plan_board  # noqa: E402

URL = "https://claude.ai/artifact/PLANBOARD123"


def _setup(home, cwd, slugs=("2026-09-01-alpha",), board=True):
    states = []
    mem = None
    for slug in slugs:
        spec = h.feature_spec_dir(home, cwd, slug)
        states.append(h.seed_state_file(spec, title=slug, slug=slug,
                                        current_phase="Design", workflow_status="In Progress"))
        mem = os.path.dirname(os.path.dirname(spec))
    if board:
        with open(os.path.join(mem, "PLAN-BOARD.md"), "w") as fh:
            fh.write(f"# Plan Board\n\n- URL: {URL}\n")
    return mem, states


def _ctx(home, cwd):
    decision, rc = h.run_hook("session_start.py", {"cwd": cwd}, env_extra={"HOME": home})
    assert rc == 0
    return decision["additionalContext"]


def test_a_stale_feature_is_named_with_the_commands_to_fix_it(tmp_path):
    with h.temp_home() as home:
        cwd = str(tmp_path)
        _mem, states = _setup(home, cwd)
        ctx = _ctx(home, cwd)
        assert "Plan Board is out of date" in ctx
        assert URL in ctx
        assert "2026-09-01-alpha" in ctx
        assert "plan_board.py" in ctx and " doc " in ctx and "mark-synced" in ctx
        assert states[0] in ctx
        assert "ArtifactData" in ctx and "plans" in ctx


def test_no_board_means_no_nudge(tmp_path):
    with h.temp_home() as home:
        cwd = str(tmp_path)
        _setup(home, cwd, board=False)
        assert "Plan Board" not in _ctx(home, cwd)


def test_a_synced_board_is_not_mentioned(tmp_path):
    with h.temp_home() as home:
        cwd = str(tmp_path)
        mem, states = _setup(home, cwd)
        plan_board.mark_synced(mem, plan_board.build_doc(states[0], project=os.path.basename(cwd)))
        # Deliberate change (verify cadence): a synced board is not "out of date"; it may still
        # carry the separate verify reminder.
        assert "out of date" not in _ctx(home, cwd)


def test_only_three_features_are_listed_and_the_rest_are_counted(tmp_path):
    with h.temp_home() as home:
        cwd = str(tmp_path)
        _setup(home, cwd, slugs=tuple(f"2026-09-0{i}-f{i}" for i in range(1, 6)))
        ctx = _ctx(home, cwd)
        assert "out of date for 5 features" in ctx
        block = ctx.split("Plan Board is out of date", 1)[1].split("\n\n", 1)[0]
        assert block.count("\n- 2026-09-0") == 3  # not the separate Active-workflows list
        assert "2 more" in block


def test_a_broken_sync_file_never_breaks_the_hook(tmp_path):
    with h.temp_home() as home:
        cwd = str(tmp_path)
        mem, _states = _setup(home, cwd)
        with open(os.path.join(mem, "plan-board-sync.json"), "w") as fh:
            fh.write("{ nope")
        ctx = _ctx(home, cwd)
        assert "SDD per-feature state for this project" in ctx


def test_the_nudge_tells_the_model_to_pin_the_write_to_the_records_version(tmp_path):
    with h.temp_home() as home:
        cwd = str(tmp_path)
        _setup(home, cwd)
        ctx = _ctx(home, cwd)
        assert "if_version" in ctx and "--out" in ctx


def test_the_nudge_says_never_to_block_on_it(tmp_path):
    with h.temp_home() as home:
        cwd = str(tmp_path)
        _setup(home, cwd)
        assert "never block" in _ctx(home, cwd).lower()


def test_sync_off_means_no_nudge_for_that_project(tmp_path):
    with h.temp_home() as home:
        cwd = str(tmp_path)
        mem, _states = _setup(home, cwd)
        assert "Plan Board is out of date" in _ctx(home, cwd)
        with open(os.path.join(mem, "PLAN-BOARD.md"), "a") as fh:
            fh.write("- Sync: off\n")
        assert "Plan Board" not in _ctx(home, cwd)


def _verified(mem, hours_ago):
    import datetime
    import plan_board_sync
    plan_board_sync.stamp_verified(
        mem, datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=hours_ago))


def _synced_setup(home, cwd):
    mem, states = _setup(home, cwd)
    plan_board.mark_synced(mem, plan_board.build_doc(states[0], project=os.path.basename(cwd)))
    return mem


def test_verify_reminder_when_never_verified(tmp_path):
    with h.temp_home() as home:
        cwd = str(tmp_path)
        _synced_setup(home, cwd)
        ctx = _ctx(home, cwd)
        assert "verify" in ctx and "/isdd-board-sync" in ctx and "plan_board_sync.py" in ctx


def test_verify_reminder_when_last_verify_is_over_24h_old(tmp_path):
    with h.temp_home() as home:
        cwd = str(tmp_path)
        _verified(_synced_setup(home, cwd), 25)
        assert "/isdd-board-sync" in _ctx(home, cwd)


def test_no_verify_reminder_when_verified_recently_or_sync_off(tmp_path):
    with h.temp_home() as home:
        cwd = str(tmp_path)
        mem = _synced_setup(home, cwd)
        _verified(mem, 1)
        assert "/isdd-board-sync" not in _ctx(home, cwd)
        _verified(mem, 48)
        with open(os.path.join(mem, "PLAN-BOARD.md"), "a") as fh:
            fh.write("- Sync: off\n")
        assert "isdd-board-sync" not in _ctx(home, cwd)


def test_stale_check_runs_every_start_and_points_to_resync(tmp_path):
    with h.temp_home() as home:
        cwd = str(tmp_path)
        mem, _ = _setup(home, cwd, slugs=tuple(f"2026-09-0{i}-f{i}" for i in range(1, 6)))
        _verified(mem, 1)  # a recent verify does not silence the local stale check
        ctx = _ctx(home, cwd)
        assert "out of date for 5 features" in ctx and "2 more" in ctx
        assert "/isdd-board-sync" in ctx
