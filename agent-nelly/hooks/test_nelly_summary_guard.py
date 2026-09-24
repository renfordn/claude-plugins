"""Tests for hooks/nelly_summary_guard.py -- PreToolUse structural cap on
`file-summary`/`folder-summary` entry descriptions (240 chars).

Drives the hook exactly as the harness does: pipe a JSON payload on stdin to
the script via subprocess, and assert on stdout + exit code.
"""
import json
import os
import subprocess
import sys

import pytest

HOOK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nelly_summary_guard.py")


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


def _entry_content(type_="file-summary", description="Short.", extra=""):
    return (
        "---\n"
        "name: some-entry\n"
        f"description: {description}\n"
        "metadata:\n"
        f"  type: {type_}\n"
        f"{extra}"
        "---\n\nBody.\n"
    )


def test_allows_short_file_summary_description(tmp_path):
    import nelly_memory
    cwd = str(tmp_path / "project")
    target = os.path.join(nelly_memory.memory_dir(cwd), "entries", "note.md")
    payload = {
        "tool_name": "Write",
        "tool_input": {"file_path": target, "content": _entry_content(description="Short summary.")},
        "cwd": cwd,
    }

    proc = run_hook(payload)

    assert proc.returncode == 0
    assert proc.stdout.strip() == ""


def test_denies_file_summary_description_over_240_chars(tmp_path):
    import nelly_memory
    cwd = str(tmp_path / "project")
    target = os.path.join(nelly_memory.memory_dir(cwd), "entries", "note.md")
    long_description = "x" * 241
    payload = {
        "tool_name": "Write",
        "tool_input": {"file_path": target, "content": _entry_content(description=long_description)},
        "cwd": cwd,
    }

    proc = run_hook(payload)

    assert proc.returncode == 0
    out = json.loads(proc.stdout)
    hso = out["hookSpecificOutput"]
    assert hso["hookEventName"] == "PreToolUse"
    assert hso["permissionDecision"] == "deny"
    assert "241 characters" in hso["permissionDecisionReason"]
    assert "240-character cap" in hso["permissionDecisionReason"]


def test_denies_folder_summary_description_over_240_chars(tmp_path):
    import nelly_memory
    cwd = str(tmp_path / "project")
    target = os.path.join(nelly_memory.memory_dir(cwd), "entries", "note.md")
    payload = {
        "tool_name": "Write",
        "tool_input": {
            "file_path": target,
            "content": _entry_content(type_="folder-summary", description="y" * 300),
        },
        "cwd": cwd,
    }

    proc = run_hook(payload)

    out = json.loads(proc.stdout)
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_allows_description_at_exactly_240_chars(tmp_path):
    import nelly_memory
    cwd = str(tmp_path / "project")
    target = os.path.join(nelly_memory.memory_dir(cwd), "entries", "note.md")
    payload = {
        "tool_name": "Write",
        "tool_input": {"file_path": target, "content": _entry_content(description="x" * 240)},
        "cwd": cwd,
    }

    proc = run_hook(payload)

    assert proc.returncode == 0
    assert proc.stdout.strip() == ""


def test_ignores_long_description_on_other_entry_types(tmp_path):
    import nelly_memory
    cwd = str(tmp_path / "project")
    target = os.path.join(nelly_memory.memory_dir(cwd), "entries", "note.md")
    payload = {
        "tool_name": "Write",
        "tool_input": {
            "file_path": target,
            "content": _entry_content(type_="project", description="z" * 500),
        },
        "cwd": cwd,
    }

    proc = run_hook(payload)

    assert proc.returncode == 0
    assert proc.stdout.strip() == ""


def test_ignores_writes_outside_memory_store(tmp_path):
    target = str(tmp_path / "unrelated" / "note.md")
    payload = {
        "tool_name": "Write",
        "tool_input": {"file_path": target, "content": _entry_content(description="z" * 500)},
        "cwd": str(tmp_path),
    }

    proc = run_hook(payload)

    assert proc.returncode == 0
    assert proc.stdout.strip() == ""


def test_ignores_edit_tool_calls(tmp_path):
    import nelly_memory
    cwd = str(tmp_path / "project")
    target = os.path.join(nelly_memory.memory_dir(cwd), "entries", "note.md")
    payload = {
        "tool_name": "Edit",
        "tool_input": {"file_path": target, "old_string": "a", "new_string": "b" * 500},
        "cwd": cwd,
    }

    proc = run_hook(payload)

    assert proc.returncode == 0
    assert proc.stdout.strip() == ""


def test_nelly_gate_off_short_circuits_to_allow(tmp_path):
    import nelly_memory
    cwd = str(tmp_path / "project")
    target = os.path.join(nelly_memory.memory_dir(cwd), "entries", "note.md")
    payload = {
        "tool_name": "Write",
        "tool_input": {"file_path": target, "content": _entry_content(description="x" * 500)},
        "cwd": cwd,
    }

    proc = run_hook(payload, env={"NELLY_GATE": "off"})

    assert proc.returncode == 0
    out = json.loads(proc.stdout)
    assert out["hookSpecificOutput"]["permissionDecision"] == "allow"


@pytest.mark.parametrize("value", ["0", "false", "disabled", "OFF", "False"])
def test_nelly_gate_off_aliases_case_insensitive(tmp_path, value):
    import nelly_memory
    cwd = str(tmp_path / "project")
    target = os.path.join(nelly_memory.memory_dir(cwd), "entries", "note.md")
    payload = {
        "tool_name": "Write",
        "tool_input": {"file_path": target, "content": _entry_content(description="x" * 500)},
        "cwd": cwd,
    }

    proc = run_hook(payload, env={"NELLY_GATE": value})

    assert proc.returncode == 0
    out = json.loads(proc.stdout)
    assert out["hookSpecificOutput"]["permissionDecision"] == "allow"
