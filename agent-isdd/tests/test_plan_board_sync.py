"""hooks/plan_board.py -- which features' Plan Board records are out of date.

The board is opt-in: a project turns it on by recording the page URL in PLAN-BOARD.md in its SDD
memory directory. After that, a feature is "stale" until its current record has been written and
marked synced, and stale again whenever its workflow-state.md changes in a way the board shows.
"""
import json
import os
import subprocess
import sys

import hook_test_utils as h

HOOKS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hooks")
sys.path.insert(0, HOOKS)

import plan_board  # noqa: E402

URL = "https://claude.ai/artifact/PLANBOARD123"


def _project(tmp_path, url=URL, features=None):
    mem = tmp_path / "mem"
    for slug, fields in (features or {"2026-09-01-alpha": {"current_phase": "Design", "workflow_status": "In Progress"}}).items():
        h.seed_state_file(str(mem / "spec" / slug), title=slug, slug=slug, **fields)
    if url is not None:
        (mem / "PLAN-BOARD.md").write_text(f"# Plan Board\n\n- URL: {url}\n")
    return str(mem)


def _stale(mem):
    return [slug for slug, _p, _d in plan_board.stale_features(mem, "proj")]


def test_the_board_is_opt_in(tmp_path):
    mem = _project(tmp_path, url=None)
    assert _stale(mem) == []


def test_a_url_that_is_not_https_counts_as_unset(tmp_path):
    mem = _project(tmp_path, url="javascript:alert(1)")
    assert plan_board.board_url(mem) is None
    assert _stale(mem) == []


def test_a_new_feature_is_stale_until_synced(tmp_path):
    mem = _project(tmp_path)
    assert _stale(mem) == ["2026-09-01-alpha"]
    path = os.path.join(mem, "spec", "2026-09-01-alpha", "workflow-state.md")
    assert plan_board.mark_synced(mem, plan_board.build_doc(path, project="proj")) is True
    assert _stale(mem) == []


def test_a_visible_change_makes_it_stale_again(tmp_path):
    mem = _project(tmp_path)
    path = os.path.join(mem, "spec", "2026-09-01-alpha", "workflow-state.md")
    plan_board.mark_synced(mem, plan_board.build_doc(path, project="proj"))
    h.seed_state_file(os.path.dirname(path), title="2026-09-01-alpha", slug="2026-09-01-alpha",
                      current_phase="Design", workflow_status="Paused")
    assert _stale(mem) == ["2026-09-01-alpha"]


def test_touching_the_file_without_a_visible_change_is_not_stale(tmp_path):
    mem = _project(tmp_path)
    path = os.path.join(mem, "spec", "2026-09-01-alpha", "workflow-state.md")
    plan_board.mark_synced(mem, plan_board.build_doc(path, project="proj"))
    with open(path, "a") as fh:
        fh.write("\n## Last Updated\n\n- Date: 2030-01-01\n")
    os.utime(path, None)
    assert _stale(mem) == []


def test_marking_one_feature_keeps_the_others_marks(tmp_path):
    mem = _project(tmp_path, features={
        "2026-09-01-alpha": {"current_phase": "Design", "workflow_status": "In Progress"},
        "2026-09-02-beta": {"current_phase": "Tasks", "workflow_status": "In Progress"},
    })
    for slug in ("2026-09-01-alpha", "2026-09-02-beta"):
        path = os.path.join(mem, "spec", slug, "workflow-state.md")
        plan_board.mark_synced(mem, plan_board.build_doc(path, project="proj"))
    assert _stale(mem) == []
    data = json.load(open(os.path.join(mem, "plan-board-sync.json")))
    assert set(data) == {"proj--2026-09-01-alpha", "proj--2026-09-02-beta"}


def test_folders_without_a_state_file_are_ignored(tmp_path):
    mem = _project(tmp_path)
    os.makedirs(os.path.join(mem, "spec", "2026-09-09-empty"))
    assert _stale(mem) == ["2026-09-01-alpha"]


def test_a_corrupt_sync_file_just_means_everything_is_stale(tmp_path):
    mem = _project(tmp_path)
    with open(os.path.join(mem, "plan-board-sync.json"), "w") as fh:
        fh.write("{ not json")
    assert _stale(mem) == ["2026-09-01-alpha"]


def test_cli_stale_lists_slug_and_path(tmp_path):
    with h.temp_home() as home:
        cwd = str(tmp_path)
        spec = h.feature_spec_dir(home, cwd, "2026-09-01-alpha")
        h.seed_state_file(spec, title="Alpha", slug="2026-09-01-alpha",
                          current_phase="Design", workflow_status="In Progress")
        mem = os.path.dirname(os.path.dirname(spec))
        with open(os.path.join(mem, "PLAN-BOARD.md"), "w") as fh:
            fh.write(f"- URL: {URL}\n")
        result = subprocess.run(
            [sys.executable, os.path.join(HOOKS, "plan_board.py"), "stale", "--cwd", cwd],
            capture_output=True, text=True, timeout=20, env=h._hook_env({"HOME": home}),
        )
        assert result.returncode == 0, result.stderr
        assert result.stdout.split("\t")[0] == "2026-09-01-alpha"
        assert result.stdout.strip().endswith("workflow-state.md")


def test_cli_mark_synced_then_stale_is_empty(tmp_path):
    with h.temp_home() as home:
        cwd = str(tmp_path)
        spec = h.feature_spec_dir(home, cwd, "2026-09-01-alpha")
        state = h.seed_state_file(spec, title="Alpha", slug="2026-09-01-alpha",
                                  current_phase="Design", workflow_status="In Progress")
        mem = os.path.dirname(os.path.dirname(spec))
        with open(os.path.join(mem, "PLAN-BOARD.md"), "w") as fh:
            fh.write(f"- URL: {URL}\n")
        env = h._hook_env({"HOME": home})
        script = os.path.join(HOOKS, "plan_board.py")
        marked = subprocess.run([sys.executable, script, "mark-synced", state, "--project", os.path.basename(cwd)],
                                capture_output=True, text=True, timeout=20, env=env, cwd=cwd)
        assert marked.returncode == 0, marked.stderr
        after = subprocess.run([sys.executable, script, "stale", "--cwd", cwd],
                               capture_output=True, text=True, timeout=20, env=env)
        assert after.stdout.strip() == ""


def test_mark_synced_uses_the_state_files_own_project_not_the_current_folder(tmp_path):
    """Any project can be synced from anywhere: the memory dir comes from the workflow-state.md
    path (<mem>/spec/<feature>/workflow-state.md), never from whichever folder the command ran in."""
    proj_a = _project(tmp_path / "a")
    elsewhere = tmp_path / "some-other-project"
    elsewhere.mkdir()
    state = os.path.join(proj_a, "spec", "2026-09-01-alpha", "workflow-state.md")
    result = subprocess.run(
        [sys.executable, os.path.join(HOOKS, "plan_board.py"), "mark-synced", state, "--project", "proj"],
        capture_output=True, text=True, timeout=20, cwd=str(elsewhere),
    )
    assert result.returncode == 0, result.stderr
    assert os.path.isfile(os.path.join(proj_a, "plan-board-sync.json"))
    assert plan_board.stale_features(proj_a, "proj") == []


def test_two_projects_share_one_board_without_colliding(tmp_path):
    """One page can hold several projects: ids carry the project label, and each project's stale
    list is tracked in its own memory dir."""
    a = _project(tmp_path / "a", features={"2026-09-01-same": {"current_phase": "Design", "workflow_status": "In Progress"}})
    b = _project(tmp_path / "b", features={"2026-09-01-same": {"current_phase": "Tasks", "workflow_status": "Paused"}})
    doc_a = plan_board.build_doc(os.path.join(a, "spec", "2026-09-01-same", "workflow-state.md"), project="alpha-app")
    doc_b = plan_board.build_doc(os.path.join(b, "spec", "2026-09-01-same", "workflow-state.md"), project="beta-app")
    assert doc_a["id"] != doc_b["id"]
    plan_board.mark_synced(a, doc_a)
    assert [s for s, _p, _d in plan_board.stale_features(a, "alpha-app")] == []
    assert [s for s, _p, _d in plan_board.stale_features(b, "beta-app")] == ["2026-09-01-same"]


def _board_file(mem, *lines):
    with open(os.path.join(mem, "PLAN-BOARD.md"), "w") as fh:
        fh.write("# Plan Board\n\n" + "".join(l + "\n" for l in lines))


def test_sync_enabled_defaults_on_and_off_switch_wins(tmp_path):
    mem = _project(tmp_path, url=None)
    assert plan_board.sync_enabled(mem) is False  # no PLAN-BOARD.md: the hard off
    _board_file(mem, f"- URL: {URL}")
    assert plan_board.sync_enabled(mem) is True
    _board_file(mem, f"- URL: {URL}", "- Sync: off")
    assert plan_board.sync_enabled(mem) is False
    _board_file(mem, f"- URL: {URL}", "- Sync: ON")
    assert plan_board.sync_enabled(mem) is True


def test_sync_off_means_nothing_is_stale(tmp_path):
    mem = _project(tmp_path)
    _board_file(mem, f"- URL: {URL}", "- Sync: off")
    assert _stale(mem) == []


def test_brief_board_url_is_https_only_and_optional(tmp_path):
    mem = _project(tmp_path)
    assert plan_board.brief_board_url(mem) is None
    _board_file(mem, f"- URL: {URL}", "- Brief Board: https://claude.ai/artifact/BRIEFS")
    assert plan_board.brief_board_url(mem) == "https://claude.ai/artifact/BRIEFS"
    _board_file(mem, f"- URL: {URL}", "- Brief Board: http://insecure")
    assert plan_board.brief_board_url(mem) is None


def test_doc_carries_brief_board_url_only_when_known(tmp_path):
    mem = _project(tmp_path)
    path = os.path.join(mem, "spec", "2026-09-01-alpha", "workflow-state.md")
    assert "briefBoardUrl" not in plan_board.build_doc(path, project="proj")
    _board_file(mem, f"- URL: {URL}", "- Brief Board: https://claude.ai/artifact/BRIEFS")
    assert plan_board.build_doc(path, project="proj")["briefBoardUrl"] == "https://claude.ai/artifact/BRIEFS"


def test_a_project_without_its_own_file_uses_the_shared_board(tmp_path):
    import plan_board
    base = tmp_path / "sdd-memory"
    proj = base / "users-me-new-project"
    proj.mkdir(parents=True)
    (base / "PLAN-BOARD.md").write_text("# Plan Board\n\n- URL: https://claude.ai/artifact/SHARED\n")
    assert plan_board.board_url(str(proj)) == "https://claude.ai/artifact/SHARED"
    assert plan_board.sync_enabled(str(proj))
    (proj / "PLAN-BOARD.md").write_text("# Plan Board\n\n- URL: https://claude.ai/artifact/OWN\n- Sync: off\n")
    assert plan_board.board_url(str(proj)) == "https://claude.ai/artifact/OWN"
    assert not plan_board.sync_enabled(str(proj))
