"""Tests for hooks/nelly_hotspot_tracker.py -- PostToolUse hook that tracks
which files get touched (Write/Edit/MultiEdit/Read) into hotspots.json.

Drives the hook exactly as the harness does: pipe a JSON payload on stdin to
the script via subprocess (HOME overridden per-test so nelly_memory.BASE
resolves under an isolated tmp dir, same pattern as test_nelly_index_update.py),
then assert on the resulting hotspots.json.
"""
import json
import os
import subprocess
import sys

HOOK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nelly_hotspot_tracker.py")


def run_hook(payload, env=None):
    full_env = dict(os.environ)
    if env:
        full_env.update(env)
    proc = subprocess.run(
        [sys.executable, HOOK],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=full_env,
    )
    return proc


def _isolated_env(tmp_path):
    return {"HOME": str(tmp_path / "home")}


def _memory_dir(cwd, env):
    proc = subprocess.run(
        [sys.executable, "nelly_memory.py", "--path", cwd],
        cwd=os.path.dirname(HOOK),
        capture_output=True,
        text=True,
        env=dict(os.environ, **env),
    )
    assert proc.returncode == 0, proc.stderr
    return proc.stdout.strip()


def _hotspots(cwd, env):
    path = os.path.join(_memory_dir(cwd, env), "hotspots.json")
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _touch(cwd, target, tool_name="Edit", env=None):
    payload = {"tool_name": tool_name, "tool_input": {"file_path": target}, "cwd": cwd}
    proc = run_hook(payload, env=env)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout == ""
    assert proc.stderr == ""
    return proc


def test_first_touch_creates_hotspots_with_count_one(tmp_path):
    env = _isolated_env(tmp_path)
    cwd = str(tmp_path / "project")
    os.makedirs(cwd)
    target = os.path.join(cwd, "src", "widget.py")

    _touch(cwd, target, env=env)

    data = _hotspots(cwd, env)
    assert data["files"]["src/widget.py"]["count"] == 1
    assert data["files"]["src/widget.py"]["last_seen"]
    assert data["updated_at"]


def test_repeated_touch_increments_count(tmp_path):
    env = _isolated_env(tmp_path)
    cwd = str(tmp_path / "project")
    os.makedirs(cwd)
    target = os.path.join(cwd, "src", "widget.py")

    for _ in range(3):
        _touch(cwd, target, env=env)

    data = _hotspots(cwd, env)
    assert data["files"]["src/widget.py"]["count"] == 3


def test_last_seen_updates_on_each_touch(tmp_path):
    env = _isolated_env(tmp_path)
    cwd = str(tmp_path / "project")
    os.makedirs(cwd)
    target = os.path.join(cwd, "src", "widget.py")

    _touch(cwd, target, env=env)
    first_seen = _hotspots(cwd, env)["files"]["src/widget.py"]["last_seen"]

    _touch(cwd, target, env=env)
    second_seen = _hotspots(cwd, env)["files"]["src/widget.py"]["last_seen"]

    assert second_seen >= first_seen


def test_tracks_write_edit_multiedit_and_read(tmp_path):
    env = _isolated_env(tmp_path)
    cwd = str(tmp_path / "project")
    os.makedirs(cwd)

    for tool_name, fname in [
        ("Write", "a.py"),
        ("Edit", "b.py"),
        ("MultiEdit", "c.py"),
        ("Read", "d.py"),
    ]:
        _touch(cwd, os.path.join(cwd, fname), tool_name=tool_name, env=env)

    data = _hotspots(cwd, env)
    assert set(data["files"].keys()) == {"a.py", "b.py", "c.py", "d.py"}


def test_untracked_tool_is_no_op(tmp_path):
    env = _isolated_env(tmp_path)
    cwd = str(tmp_path / "project")
    os.makedirs(cwd)
    target = os.path.join(cwd, "widget.py")

    payload = {"tool_name": "Bash", "tool_input": {"file_path": target}, "cwd": cwd}
    proc = run_hook(payload, env=env)

    assert proc.returncode == 0
    mem_dir = _memory_dir(cwd, env)
    assert not os.path.isfile(os.path.join(mem_dir, "hotspots.json"))


def test_missing_file_path_is_no_op(tmp_path):
    env = _isolated_env(tmp_path)
    cwd = str(tmp_path / "project")
    os.makedirs(cwd)

    payload = {"tool_name": "Edit", "tool_input": {}, "cwd": cwd}
    proc = run_hook(payload, env=env)

    assert proc.returncode == 0
    mem_dir = _memory_dir(cwd, env)
    assert not os.path.isfile(os.path.join(mem_dir, "hotspots.json"))


def test_caps_at_fifty_files_evicting_least_recently_seen(tmp_path):
    env = _isolated_env(tmp_path)
    cwd = str(tmp_path / "project")
    os.makedirs(cwd)

    for i in range(50):
        _touch(cwd, os.path.join(cwd, f"file-{i:02d}.py"), env=env)

    # file-00.py is now the least-recently-seen; touching one more evicts it.
    _touch(cwd, os.path.join(cwd, "file-50.py"), env=env)

    data = _hotspots(cwd, env)
    assert len(data["files"]) == 50
    assert "file-00.py" not in data["files"]
    assert "file-50.py" in data["files"]


def test_gate_off_disables_tracking(tmp_path):
    env = _isolated_env(tmp_path)
    env["NELLY_GATE"] = "off"
    cwd = str(tmp_path / "project")
    os.makedirs(cwd)
    target = os.path.join(cwd, "widget.py")

    payload = {"tool_name": "Edit", "tool_input": {"file_path": target}, "cwd": cwd}
    proc = run_hook(payload, env=env)

    assert proc.returncode == 0
    mem_dir = _memory_dir(cwd, env)
    assert not os.path.isfile(os.path.join(mem_dir, "hotspots.json"))


def test_malformed_stdin_is_silent_no_op():
    proc = subprocess.run(
        [sys.executable, HOOK],
        input="not json",
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    assert proc.stdout == ""
    assert proc.stderr == ""
