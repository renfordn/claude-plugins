"""Features worked on in a git worktree belong to the originating project, not a project of their own.

repo_label() resolves a worktree to its main repo's name; the central run labels a
`<project>-claude-worktrees-<name>` memory folder with the project's label, so a worktree session and a
main-repo session produce the same record id for the same feature, and cards left under an old
worktree label are reported as superseded (and offered for pruning) instead of orphaned or duplicated."""
import json
import os
import subprocess
import sys

import hook_test_utils as h

HOOKS = h.HOOKS_DIR
sys.path.insert(0, HOOKS)
import plan_board  # noqa: E402

URL = "https://claude.ai/artifact/SHARED"


def test_a_git_worktree_is_labelled_with_its_main_repo(tmp_path):
    main = tmp_path / "file-organiser"
    wt = main / ".claude" / "worktrees" / "queue-timeout-cded2a"
    (main / ".git" / "worktrees" / "queue-timeout-cded2a").mkdir(parents=True)
    (main / ".git" / "worktrees" / "queue-timeout-cded2a" / "commondir").write_text("../..\n")
    wt.mkdir(parents=True)
    (wt / ".git").write_text(f"gitdir: {main}/.git/worktrees/queue-timeout-cded2a\n")
    assert plan_board.repo_label(str(wt)) == "file-organiser"
    assert plan_board.repo_label(str(wt / "sub")) == "file-organiser"  # a subfolder of the worktree
    assert plan_board.repo_label(str(main)) == "file-organiser"


def test_a_real_git_worktree_is_labelled_with_its_main_repo(tmp_path):
    main = tmp_path / "my-project"
    main.mkdir()
    env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t")
    for args in (["init", "-q"], ["commit", "-q", "--allow-empty", "-m", "x"],
                 ["worktree", "add", "-q", str(main / ".claude" / "worktrees" / "wt-a")]):
        subprocess.run(["git", *args], cwd=main, check=True, env=env, capture_output=True)
    assert plan_board.repo_label(str(main / ".claude" / "worktrees" / "wt-a")) == "my-project"


def _project(base, name, features, sync_label=None):
    mem = os.path.join(base, name)
    for f in features:
        h.seed_state_file(os.path.join(mem, "spec", f), title=f, slug=f,
                          current_phase="Design", workflow_status="In Progress")
    if sync_label:
        with open(os.path.join(mem, "plan-board-sync.json"), "w") as fh:
            json.dump({f"{sync_label}--{f}": "old" for f in features}, fh)
    return mem


def _setup(tmp_path, board_ids, base_features=("2026-10-01-a",), wt_features=("2026-10-02-b",)):
    base = str(tmp_path / "sdd-memory")
    os.makedirs(base)
    with open(os.path.join(base, "PLAN-BOARD.md"), "w") as fh:
        fh.write(f"# Plan Board\n\n- URL: {URL}\n")
    _project(base, "users-me-proj", base_features, "proj")
    _project(base, "users-me-proj-claude-worktrees-wt-1", wt_features, "wt-1")
    dump = str(tmp_path / "board.json")
    with open(dump, "w") as fh:
        json.dump([{"id": i, "contentHash": "x", "version": 3} for i in board_ids], fh)
    return base, dump


def _run(base, *args):
    p = subprocess.run([sys.executable, os.path.join(HOOKS, "plan_board_sync.py"), "all", *args, "--base", base],
                       capture_output=True, text=True, timeout=20)
    assert p.returncode == 0, p.stderr
    return p.stdout


def test_worktree_projects_are_reported_under_the_originating_project(tmp_path):
    base, dump = _setup(tmp_path, ["proj--2026-10-01-a"])
    out = json.loads(_run(base, "verify", "--board-json", dump))
    assert "wt-1" not in out["projects"]
    assert set(out["projects"]) == {"proj"}
    assert "proj--2026-10-02-b" in out["projects"]["proj"]["missing"]


def test_a_feature_already_carded_under_the_project_is_not_duplicated(tmp_path):
    """The card was written by a session in the main repo; the feature's folder sits in a worktree."""
    base, dump = _setup(tmp_path, ["proj--2026-10-01-a", "proj--2026-10-02-b"])
    out = json.loads(_run(base, "verify", "--board-json", dump))
    assert out["projects"]["proj"]["missing"] == []
    assert out.get("superseded", []) == []
    writes = json.loads(_run(base, "resync", "--board-json", dump))["writes"]
    assert all("2026-10-02-b" not in w["doc_id"] for w in writes if w["doc_id"] != "proj--2026-10-02-b")
    assert [w["doc_id"] for w in writes if "2026-10-02-b" in w["doc_id"]] in ([], ["proj--2026-10-02-b"])


def test_cards_under_an_old_worktree_label_are_superseded_not_orphans(tmp_path):
    base, dump = _setup(tmp_path, ["proj--2026-10-01-a", "wt-1--2026-10-02-b"])
    out = json.loads(_run(base, "verify", "--board-json", dump))
    assert out["superseded"] == ["wt-1--2026-10-02-b"]
    assert out["orphaned"] == []
    listing = _run(base, "prune", "--board-json", dump)
    assert "wt-1--2026-10-02-b" in listing
    done = json.loads(_run(base, "prune", "--board-json", dump, "--confirm"))
    assert [d["doc_id"] for d in done["board_instructions"]] == ["wt-1--2026-10-02-b"]
    assert done["board_instructions"][0]["if_version"] == 3


def test_resync_writes_each_record_once_when_a_slug_is_in_two_folders(tmp_path):
    base, dump = _setup(tmp_path, [], base_features=("2026-10-01-a", "2026-10-03-shared"),
                        wt_features=("2026-10-03-shared",))
    batch = json.loads(_run(base, "resync", "--board-json", dump))
    ids = [w["doc_id"] for w in batch["writes"]]
    assert len(ids) == len(set(ids)) and "proj--2026-10-03-shared" in ids
