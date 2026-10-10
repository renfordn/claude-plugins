"""flag_sync.py PostToolUse hook, run as a subprocess with JSON on stdin."""
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOK = os.path.join(ROOT, "hooks", "flag_sync.py")

STATE = "- Title: Feature X\n- Current Phase: {phase}\n- Workflow Status: {status}\n"


def run(stdin, data):
    env = dict(os.environ, CLAUDE_PLUGIN_DATA=str(data))
    return subprocess.run([sys.executable, HOOK], input=stdin, capture_output=True, text=True,
                          env=env, timeout=10)


def feature(tmp_path, phase="Design", status="In Progress"):
    d = tmp_path / "mem" / "spec" / "2026-09-30-x"
    d.mkdir(parents=True)
    (d / "workflow-state.md").write_text(STATE.format(phase=phase, status=status))
    return d


def payload(path, tool="Write"):
    return json.dumps({"hook_event_name": "PostToolUse", "tool_name": tool,
                       "tool_input": {"file_path": str(path)}})


def pending(data):
    return json.loads((data / "store.json").read_text())["pending"]


def test_matching_write_flags_feature_and_emits_context_when_phase_changed(tmp_path):
    d, data = feature(tmp_path), tmp_path / "data"
    (d / "monday.json").write_text(json.dumps(
        {"synced_fields": {"phase": "Requirements", "workflow_status": "In Progress"}}))
    proc = run(payload(d / "workflow-state.md", "Edit"), data)
    assert proc.returncode == 0
    assert pending(data) == [os.path.realpath(d)]
    ctx = json.loads(proc.stdout)["hookSpecificOutput"]
    assert ctx["hookEventName"] == "PostToolUse"
    assert "Feature X" in ctx["additionalContext"] and "monday-sync" in ctx["additionalContext"]


def test_matching_write_with_unchanged_phase_and_status_is_silent_but_flagged(tmp_path):
    d, data = feature(tmp_path), tmp_path / "data"
    (d / "monday.json").write_text(json.dumps(
        {"synced_fields": {"phase": "Design", "workflow_status": "In Progress"}}))
    proc = run(payload(d / "workflow-state.md"), data)
    assert proc.returncode == 0 and proc.stdout.strip() == ""
    assert pending(data) == [os.path.realpath(d)]


def test_non_matching_path_is_a_no_op(tmp_path):
    d, data = feature(tmp_path), tmp_path / "data"
    proc = run(payload(d / "recap" / "recap.md"), data)
    assert proc.returncode == 0 and proc.stdout.strip() == ""
    assert not (data / "store.json").exists()


def test_malformed_stdin_exits_zero(tmp_path):
    proc = run("{not json", tmp_path / "data")
    assert proc.returncode == 0 and proc.stdout.strip() == ""


def test_field_names_match_case_insensitively(tmp_path):
    d, data = feature(tmp_path), tmp_path / "data"
    (d / "workflow-state.md").write_text("- title: Feature X\n- current phase: Design\n"
                                         "- workflow status: In Progress\n")
    (d / "monday.json").write_text(json.dumps(
        {"synced_fields": {"phase": "Design", "workflow_status": "In Progress"}}))
    proc = run(payload(d / "workflow-state.md"), data)
    assert proc.returncode == 0 and proc.stdout.strip() == ""


def _iso(seconds_ago):
    import datetime
    t = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=seconds_ago)
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def test_unlinked_feature_is_not_flagged(tmp_path):
    d, data = feature(tmp_path), tmp_path / "data"
    (d / "monday.json").write_text(json.dumps({"unlinked": True}))
    proc = run(payload(d / "workflow-state.md"), data)
    assert proc.returncode == 0 and proc.stdout.strip() == ""
    assert not (data / "store.json").exists() or pending(data) == []


def test_sync_in_progress_flags_but_does_not_nudge(tmp_path):
    d, data = feature(tmp_path), tmp_path / "data"
    (d / "monday.json").write_text(json.dumps({"syncing_since": _iso(30)}))
    proc = run(payload(d / "workflow-state.md"), data)
    assert proc.returncode == 0 and proc.stdout.strip() == ""
    assert pending(data) == [os.path.realpath(d)]


def test_stale_sync_marker_nudges_again(tmp_path):
    d, data = feature(tmp_path), tmp_path / "data"
    (d / "monday.json").write_text(json.dumps({"syncing_since": _iso(11 * 60)}))
    proc = run(payload(d / "workflow-state.md"), data)
    assert "monday-sync" in json.loads(proc.stdout)["hookSpecificOutput"]["additionalContext"]


def run_bash(command, data, root):
    env = dict(os.environ, CLAUDE_PLUGIN_DATA=str(data), CLAUDE_PLUGIN_OPTION_SHARED_MEMORY_ROOT=str(root))
    stdin = json.dumps({"hook_event_name": "PostToolUse", "tool_name": "Bash",
                        "tool_input": {"command": command}})
    return subprocess.run([sys.executable, HOOK], input=stdin, capture_output=True, text=True,
                          env=env, timeout=10)


def shared_feature(tmp_path, slug="2026-10-07-bash-x"):
    d = tmp_path / "root" / "sdd-memory" / "users-me-proj" / "spec" / slug
    d.mkdir(parents=True)
    (d / "workflow-state.md").write_text(STATE.format(phase="Design", status="In Progress"))
    return d


def test_bash_write_to_a_shared_root_feature_flags_and_nudges(tmp_path):
    d, data = shared_feature(tmp_path), tmp_path / "data"
    cmd = 'D="$HOME/x/spec/2026-10-07-bash-x"; printf "x" >> "$D/workflow-state.md"'
    proc = run_bash(cmd, data, tmp_path / "root")
    assert proc.returncode == 0
    assert pending(data) == [os.path.realpath(d)]
    assert "monday-sync" in json.loads(proc.stdout)["hookSpecificOutput"]["additionalContext"]


def test_bash_without_workflow_state_is_a_no_op(tmp_path):
    shared_feature(tmp_path)
    data = tmp_path / "data"
    proc = run_bash("ls spec/2026-10-07-bash-x/design", data, tmp_path / "root")
    assert proc.returncode == 0 and proc.stdout.strip() == ""
    assert not (data / "store.json").exists()
