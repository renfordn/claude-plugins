"""hooks/stop_check.py -- the Plan Board end-of-turn gate.

Reminders alone were ignored, so the board went stale for a week. At Stop, a feature whose
state changed in the last 24h and whose board record is out of date blocks the stop once (per
content hash) with the exact steps to sync. Never loops: a stop already continued by a Stop
hook (`stop_hook_active`) is never blocked, and a hash already nudged is not nudged again.
"""
import json
import os
import subprocess
import time

import hook_test_utils as h

SLUG = "2026-10-08-gate-feature"


def _setup(home, repo, board=True):
    spec = h.feature_spec_dir(home, repo, SLUG)
    state = h.seed_state_file(spec, title="Gate Feature", slug=SLUG,
                              current_phase="Implementation", workflow_status="In Progress")
    if board:
        h.seed_plan_board_url(os.path.dirname(os.path.dirname(spec)))
    return state


def _stop(home, repo, **extra):
    payload = dict({"cwd": repo, "hook_event_name": "Stop"}, **extra)
    result = subprocess.run(
        ["python3", os.path.join(h.HOOKS_DIR, "stop_check.py")], input=json.dumps(payload),
        capture_output=True, text=True, env=h._hook_env({"HOME": home}), timeout=10)
    assert result.returncode == 0, result.stderr
    out = result.stdout.strip()
    return json.loads(out) if out else {}


def test_recent_stale_feature_blocks_the_stop_once_with_sync_steps():
    with h.temp_git_repo() as repo, h.temp_home() as home:
        state = _setup(home, repo)
        out = _stop(home, repo)
        assert out.get("decision") == "block"
        assert SLUG in out["reason"] and "ArtifactData" in out["reason"]
        assert "mark-synced" in out["reason"] and state in out["reason"]
        assert _stop(home, repo).get("decision") is None   # same hash: nudged already


def test_a_new_change_after_the_nudge_blocks_again():
    with h.temp_git_repo() as repo, h.temp_home() as home:
        state = _setup(home, repo)
        _stop(home, repo)
        with open(state, "a", encoding="utf-8") as fh:
            fh.write("- Next Action: something new\n")
        assert _stop(home, repo).get("decision") == "block"


def test_stop_hook_active_never_blocks():
    with h.temp_git_repo() as repo, h.temp_home() as home:
        _setup(home, repo)
        assert _stop(home, repo, stop_hook_active=True).get("decision") is None


def test_no_board_or_old_change_does_not_block():
    with h.temp_git_repo() as repo, h.temp_home() as home:
        _setup(home, repo, board=False)
        assert _stop(home, repo).get("decision") is None
    with h.temp_git_repo() as repo, h.temp_home() as home:
        state = _setup(home, repo)
        old = time.time() - 3 * 86400
        os.utime(state, (old, old))
        assert _stop(home, repo).get("decision") is None


def test_worktree_session_uses_the_main_repo_board():
    with h.temp_git_repo() as repo, h.temp_home() as home:
        _setup(home, repo)
        subprocess.run(["git", "commit", "-q", "--allow-empty", "-m", "init"], cwd=repo, check=True)
        wt = os.path.join(repo, ".claude", "worktrees", "wt1")
        subprocess.run(["git", "worktree", "add", "-q", "-b", "wt1", wt], cwd=repo, check=True)
        out = _stop(home, wt)
        assert out.get("decision") == "block" and SLUG in out["reason"]
