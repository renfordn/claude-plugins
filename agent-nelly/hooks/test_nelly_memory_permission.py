"""Tests for hooks/nelly_memory_permission.py — PreToolUse auto-allow hook for
paths under Agent Nelly's memory_dir()/global_dir() (Phase 4).

Drives the hook exactly as the harness does: pipe a JSON payload on stdin to
the script via subprocess, and assert on stdout + exit code.
"""
import json
import os
import subprocess
import sys

import pytest

HOOK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nelly_memory_permission.py")


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


def test_allow_when_file_path_under_project_memory_dir(tmp_path):
    cwd = str(tmp_path / "some-project")
    import nelly_memory
    target = os.path.join(nelly_memory.memory_dir(cwd), "entries", "note.md")
    payload = {"tool_input": {"file_path": target}, "cwd": cwd}

    proc = run_hook(payload)

    assert proc.returncode == 0
    out = json.loads(proc.stdout)
    hso = out["hookSpecificOutput"]
    assert hso["hookEventName"] == "PreToolUse"
    assert hso["permissionDecision"] == "allow"
    assert "permissionDecisionReason" in hso


def test_allow_when_file_path_under_global_dir(tmp_path):
    import nelly_memory
    # Build the path directly (BASE/global/...) instead of calling
    # global_dir(), which has the side effect of creating real directories
    # under the user's actual ~/.claude/agent-nelly-memory tree.
    target = os.path.join(nelly_memory.BASE, "global", "GLOBAL-MEMORY.md")
    payload = {"tool_input": {"file_path": target}, "cwd": str(tmp_path)}

    proc = run_hook(payload)

    assert proc.returncode == 0
    out = json.loads(proc.stdout)
    assert out["hookSpecificOutput"]["permissionDecision"] == "allow"


def test_no_decision_when_file_path_outside_both_dirs(tmp_path):
    target = str(tmp_path / "unrelated" / "file.md")
    payload = {"tool_input": {"file_path": target}, "cwd": str(tmp_path)}

    proc = run_hook(payload)

    assert proc.returncode == 0
    assert proc.stdout.strip() == ""


def test_nelly_gate_off_short_circuits_to_allow(tmp_path):
    target = str(tmp_path / "unrelated" / "file.md")
    payload = {"tool_input": {"file_path": target}, "cwd": str(tmp_path)}

    proc = run_hook(payload, env={"NELLY_GATE": "off"})

    assert proc.returncode == 0
    out = json.loads(proc.stdout)
    assert out["hookSpecificOutput"]["permissionDecision"] == "allow"


@pytest.mark.parametrize("value", ["0", "false", "disabled", "OFF", "False"])
def test_nelly_gate_off_aliases_case_insensitive(tmp_path, value):
    target = str(tmp_path / "unrelated" / "file.md")
    payload = {"tool_input": {"file_path": target}, "cwd": str(tmp_path)}

    proc = run_hook(payload, env={"NELLY_GATE": value})

    assert proc.returncode == 0
    out = json.loads(proc.stdout)
    assert out["hookSpecificOutput"]["permissionDecision"] == "allow"


# RED TESTS - Slice 6: Validator + Audit Refactoring
# These tests define new behavior integrating with plugin_data_whitelist validators

def test_blocks_executable_files_under_memory_dir(tmp_path):
    """Executables (.exe) should be blocked even under memory_dir."""
    cwd = str(tmp_path / "some-project")
    import nelly_memory
    target = os.path.join(nelly_memory.memory_dir(cwd), "entries", "malware.exe")
    payload = {"tool_input": {"file_path": target}, "cwd": cwd}

    proc = run_hook(payload)

    assert proc.returncode == 0
    assert proc.stdout.strip() == ""  # No decision; blocked by validator


def test_audit_trail_populated_on_allow(tmp_path):
    """When hook allows, it should create audit trail entry."""
    cwd = str(tmp_path / "some-project")
    import nelly_memory
    target = os.path.join(nelly_memory.memory_dir(cwd), "entries", "note.md")
    payload = {"tool_input": {"file_path": target}, "cwd": cwd}

    proc = run_hook(payload)

    assert proc.returncode == 0
    out = json.loads(proc.stdout)
    hso = out["hookSpecificOutput"]
    # Audit trail should be present
    assert "auditTrailEntry" in hso or "audit" in hso.get("permissionDecisionReason", "").lower()


def test_cross_agent_access_still_denied(tmp_path):
    """Paths under agent-isdd or agent-tdd memory should be denied."""
    cwd = str(tmp_path / "some-project")
    import sdd_memory
    # Try to access agent-isdd's memory
    target = os.path.join(sdd_memory.memory_dir(cwd), "spec", "feature", "workflow-state.md")
    payload = {"tool_input": {"file_path": target}, "cwd": cwd}

    proc = run_hook(payload)

    assert proc.returncode == 0
    # Should be no_decision (not allowed for agent-nelly to approve)
    assert proc.stdout.strip() == ""
