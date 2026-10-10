"""session_start.py: notice when features need board sync; silent otherwise."""
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOK = os.path.join(ROOT, "hooks", "session_start.py")


def run(data):
    env = dict(os.environ, CLAUDE_PLUGIN_DATA=str(data))
    return subprocess.run([sys.executable, HOOK], input='{"hook_event_name":"SessionStart"}',
                          capture_output=True, text=True, env=env, timeout=10)


def seed(tmp_path, n):
    dirs = []
    for i in range(n):
        d = tmp_path / "spec" / f"f{i}"
        d.mkdir(parents=True)
        (d / "workflow-state.md").write_text(f"- Title: Feature {i}\n- Current Phase: Design\n")
        dirs.append(os.path.realpath(d))
    data = tmp_path / "data"
    data.mkdir()
    (data / "store.json").write_text(json.dumps({"pending": dirs, "linked": {}, "dismissed_candidates": []}))
    return data


def test_pending_features_produce_a_notice_with_at_most_five_titles(tmp_path):
    proc = run(seed(tmp_path, 7))
    assert proc.returncode == 0
    out = json.loads(proc.stdout)["hookSpecificOutput"]
    assert out["hookEventName"] == "SessionStart"
    ctx = out["additionalContext"]
    assert ctx.startswith("monday: 7 features need board sync") and "monday-sync" in ctx
    assert "Feature 4" in ctx and "Feature 5" not in ctx


def test_empty_or_missing_store_is_silent(tmp_path):
    proc = run(tmp_path / "nothing")
    assert proc.returncode == 0 and proc.stdout.strip() == ""
    proc = run(seed(tmp_path, 0))
    assert proc.returncode == 0 and proc.stdout.strip() == ""


def test_titles_are_read_case_insensitively(tmp_path):
    data = seed(tmp_path, 1)
    d = tmp_path / "spec" / "f0"
    (d / "workflow-state.md").write_text("- title: Lower Case Title\n")
    ctx = json.loads(run(data).stdout)["hookSpecificOutput"]["additionalContext"]
    assert "Lower Case Title" in ctx


def _drift_feature(tmp_path, slug, sidecar):
    d = tmp_path / "root" / "sdd-memory" / "users-me-proj" / "spec" / slug
    d.mkdir(parents=True)
    (d / "workflow-state.md").write_text(f"- Title: {slug}\n- Current Phase: Design\n")
    if sidecar is not None:
        (d / "monday.json").write_text(json.dumps(sidecar))
    return os.path.realpath(d)


def run_scan(tmp_path):
    env = dict(os.environ, CLAUDE_PLUGIN_DATA=str(tmp_path / "data"),
               CLAUDE_PLUGIN_OPTION_SHARED_MEMORY_ROOT=str(tmp_path / "root"))
    return subprocess.run([sys.executable, HOOK], input='{"hook_event_name":"SessionStart"}',
                          capture_output=True, text=True, env=env, timeout=10)


def test_linked_feature_whose_state_changed_since_last_sync_is_flagged(tmp_path):
    changed = _drift_feature(tmp_path, "2026-10-01-changed", {"item_id": "1", "state_hash": "0" * 16})
    proc = run_scan(tmp_path)
    ctx = json.loads(proc.stdout)["hookSpecificOutput"]["additionalContext"]
    assert ctx.startswith("monday: 1 feature need") and "2026-10-01-changed" in ctx
    store = json.loads((tmp_path / "data" / "store.json").read_text())
    assert store["pending"] == [changed]


def test_in_sync_unlinked_and_unknown_features_are_not_flagged(tmp_path):
    import hashlib
    d = _drift_feature(tmp_path, "2026-10-01-same", None)
    text = open(os.path.join(d, "workflow-state.md")).read()
    h16 = hashlib.sha256(text.encode()).hexdigest()[:16]
    with open(os.path.join(d, "monday.json"), "w") as fh:
        json.dump({"item_id": "1", "state_hash": h16}, fh)
    _drift_feature(tmp_path, "2026-10-01-off", {"item_id": "2", "state_hash": "0" * 16, "unlinked": True})
    _drift_feature(tmp_path, "2026-10-01-new", None)
    proc = run_scan(tmp_path)
    assert proc.returncode == 0 and proc.stdout.strip() == ""
