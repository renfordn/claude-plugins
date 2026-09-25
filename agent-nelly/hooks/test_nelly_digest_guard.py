"""Tests for hooks/nelly_digest_guard.py -- PreToolUse cap on research-digest bodies (2,000
chars) for direct Writes into entries/research-digest/ (scripts/research_digest.py truncates on
its own path; this guards hand-written digests)."""
import json
import os
import subprocess
import sys

HOOK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nelly_digest_guard.py")
HOOKS_JSON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hooks.json")


def run_hook(payload, env=None):
    return subprocess.run([sys.executable, HOOK], input=json.dumps(payload), capture_output=True,
                          text=True, env=dict(os.environ, **(env or {})))


def _content(body):
    return ("---\nname: digest-x\ndescription: t\ntype: research-digest\ntopic: t\n"
            "sources:\n  - path: a.py\n    hash: abc\nupdated: 2026-09-25T00:00:00Z\n---\n" + body + "\n")


def _payload(tmp_path, body, subdir="research-digest", tool="Write", inside=True):
    import nelly_memory
    cwd = str(tmp_path / "project")
    root = nelly_memory.memory_dir(cwd) if inside else str(tmp_path / "elsewhere")
    target = os.path.join(root, "entries", subdir, "digest-x.md")
    return {"tool_name": tool, "tool_input": {"file_path": target, "content": _content(body)},
            "cwd": cwd}


def test_denies_body_over_2000_chars(tmp_path):
    proc = run_hook(_payload(tmp_path, "x" * 2001))
    assert proc.returncode == 0
    hso = json.loads(proc.stdout)["hookSpecificOutput"]
    assert hso["permissionDecision"] == "deny"
    assert "2001 characters" in hso["permissionDecisionReason"]
    assert "2000-character cap" in hso["permissionDecisionReason"]
    assert "research_digest.py" in hso["permissionDecisionReason"]


def test_no_decision_at_exactly_2000_chars(tmp_path):
    proc = run_hook(_payload(tmp_path, "x" * 2000))
    assert (proc.returncode, proc.stdout.strip()) == (0, "")


def test_no_decision_outside_digest_subdir_or_store_or_for_edit(tmp_path):
    for payload in (_payload(tmp_path, "x" * 2001, subdir="file-folder-summary"),
                    _payload(tmp_path, "x" * 2001, inside=False),
                    _payload(tmp_path, "x" * 2001, tool="Edit")):
        proc = run_hook(payload)
        assert (proc.returncode, proc.stdout.strip()) == (0, ""), payload


def test_gate_off_gives_no_decision_never_allow(tmp_path):
    proc = run_hook(_payload(tmp_path, "x" * 2001), env={"NELLY_GATE": "off"})
    assert (proc.returncode, proc.stdout.strip()) == (0, "")


def test_registered_in_hooks_json_pretooluse_write():
    config = json.load(open(HOOKS_JSON))
    commands = [h["command"] for entry in config["hooks"]["PreToolUse"]
                if "Write" in entry.get("matcher", "") for h in entry["hooks"]]
    assert any("nelly_digest_guard.py" in c for c in commands)
