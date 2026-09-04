"""Tests for hooks/nelly_slug_guard.py — PreToolUse deny-first slug guard for
Agent Nelly's independent memory root (Phase 4).

Drives the hook exactly as the harness does: pipe a JSON payload on stdin to
the script via subprocess, and assert on stdout + exit code.
"""
import json
import os
import subprocess
import sys

import pytest

HOOK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nelly_slug_guard.py")


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


def test_no_decision_for_correct_slug_write(tmp_path):
    import nelly_memory
    cwd = str(tmp_path / "project")
    target = os.path.join(nelly_memory.memory_dir(cwd), "entries", "note.md")
    payload = {"tool_input": {"file_path": target}, "cwd": cwd}

    proc = run_hook(payload)

    assert proc.returncode == 0
    assert proc.stdout.strip() == ""


def test_deny_for_wrong_slug_write(tmp_path):
    import nelly_memory
    cwd = str(tmp_path / "project")
    canonical = nelly_memory.project_slug(cwd)
    wrong_target = os.path.join(nelly_memory.BASE, "some-other-wrong-slug", "entries", "note.md")
    payload = {"tool_input": {"file_path": wrong_target}, "cwd": cwd}

    proc = run_hook(payload)

    assert proc.returncode == 0
    out = json.loads(proc.stdout)
    hso = out["hookSpecificOutput"]
    assert hso["hookEventName"] == "PreToolUse"
    assert hso["permissionDecision"] == "deny"
    assert canonical in hso["permissionDecisionReason"]
    assert "python3 hooks/nelly_memory.py --path" in hso["permissionDecisionReason"]


def test_no_decision_for_literal_global_segment(tmp_path):
    import nelly_memory
    target = os.path.join(nelly_memory.BASE, "global", "GLOBAL-MEMORY.md")
    payload = {"tool_input": {"file_path": target}, "cwd": str(tmp_path)}

    proc = run_hook(payload)

    assert proc.returncode == 0
    assert proc.stdout.strip() == ""


def test_no_decision_for_path_outside_base(tmp_path):
    target = str(tmp_path / "unrelated" / "file.md")
    payload = {"tool_input": {"file_path": target}, "cwd": str(tmp_path)}

    proc = run_hook(payload)

    assert proc.returncode == 0
    assert proc.stdout.strip() == ""


def test_nelly_gate_off_short_circuits_to_allow(tmp_path):
    import nelly_memory
    cwd = str(tmp_path / "project")
    wrong_target = os.path.join(nelly_memory.BASE, "some-other-wrong-slug", "entries", "note.md")
    payload = {"tool_input": {"file_path": wrong_target}, "cwd": cwd}

    proc = run_hook(payload, env={"NELLY_GATE": "off"})

    assert proc.returncode == 0
    out = json.loads(proc.stdout)
    assert out["hookSpecificOutput"]["permissionDecision"] == "allow"


@pytest.mark.parametrize("value", ["0", "false", "disabled", "OFF", "False"])
def test_nelly_gate_off_aliases_case_insensitive(tmp_path, value):
    import nelly_memory
    cwd = str(tmp_path / "project")
    wrong_target = os.path.join(nelly_memory.BASE, "some-other-wrong-slug", "entries", "note.md")
    payload = {"tool_input": {"file_path": wrong_target}, "cwd": cwd}

    proc = run_hook(payload, env={"NELLY_GATE": value})

    assert proc.returncode == 0
    out = json.loads(proc.stdout)
    assert out["hookSpecificOutput"]["permissionDecision"] == "allow"
