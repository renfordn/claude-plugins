"""Tests for hooks/nelly_proactive_surface.py — PreToolUse proactive nudge
hook (Phase 2 of the proactive-suggestion-hooks feature).

Drives the hook exactly as the harness does: pipe a JSON payload on stdin to
the script via subprocess, and assert on stdout + exit code. Same style as
test_nelly_slug_guard.py.

Tie-break note: when two index entries both match the same target path, this
hook emits a reason for the FIRST matching entry it finds while scanning
MEMORY.md top-to-bottom (not a highest-confidence/most-recently-referenced
pick) -- see hooks/nelly_proactive_surface.py's module docstring for the
rationale.
"""
import json
import os
import subprocess
import sys

import pytest

HOOK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nelly_proactive_surface.py")


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


def make_entry(cwd, name, entry_type, confidence=None, description="a test entry description"):
    """Write a real entries/<name>.md file with the given frontmatter, using
    nelly_memory.py's own helpers (ensure_entries_dir/entry_path) rather than
    hand-computing the path.
    """
    import nelly_memory

    nelly_memory.ensure_entries_dir(cwd)
    path = nelly_memory.entry_path(cwd, name)
    lines = [
        "---",
        f"name: {name}",
        f"description: {description}",
        "metadata:",
        f"  type: {entry_type}",
    ]
    if confidence is not None:
        lines.append(f"  confidence: {confidence}")
    lines.append("---")
    lines.append("")
    lines.append("Body text.")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    return path


def add_index_line(cwd, name, title, entry_type, index_confidence=None, paths=None):
    """Add an index line via nelly_memory.write_index_line (the canonical
    writer), so the test never hand-formats the field block.
    """
    import nelly_memory

    return nelly_memory.write_index_line(
        cwd, name, "some-hook", entry_type, confidence=index_confidence, paths=paths,
    )


def test_file_relevance_match_emits_reason_and_allows(tmp_path):
    cwd = str(tmp_path / "project")
    target_rel = "src/foo.py"
    target_abs = os.path.join(cwd, target_rel)
    make_entry(cwd, "foo-notes", "file-relevance", description="notes about foo.py")
    add_index_line(cwd, "foo-notes", "Foo Notes", "file-relevance", paths=[target_rel])

    proc = run_hook({"tool_input": {"file_path": target_abs}, "cwd": cwd})

    assert proc.returncode == 0
    out = json.loads(proc.stdout)
    hso = out["hookSpecificOutput"]
    assert hso["hookEventName"] == "PreToolUse"
    assert hso["permissionDecision"] == "allow"
    assert "permissionDecisionReason" in hso
    assert hso["permissionDecisionReason"]


def test_error_prevention_explicit_confidence_emits_reason(tmp_path):
    cwd = str(tmp_path / "project")
    target_rel = "src/bar.py"
    target_abs = os.path.join(cwd, target_rel)
    make_entry(cwd, "bar-mistake", "error-prevention", confidence="explicit",
               description="don't do the bar thing")
    add_index_line(cwd, "bar-mistake", "Bar Mistake", "error-prevention", paths=[target_rel])

    proc = run_hook({"tool_input": {"file_path": target_abs}, "cwd": cwd})

    assert proc.returncode == 0
    out = json.loads(proc.stdout)
    hso = out["hookSpecificOutput"]
    assert hso["permissionDecision"] == "allow"
    assert hso["permissionDecisionReason"]


def test_error_prevention_inferred_confidence_is_silent(tmp_path):
    """The single most safety-critical assertion in this feature: an
    error-prevention entry whose REAL metadata.confidence is 'inferred' must
    never surface, even if the index line's mirrored confidence field claims
    otherwise (index/entry drift must never leak an inferred lesson).
    """
    cwd = str(tmp_path / "project")
    target_rel = "src/baz.py"
    target_abs = os.path.join(cwd, target_rel)
    make_entry(cwd, "baz-mistake", "error-prevention", confidence="inferred",
               description="noticed unprompted, not yet confirmed")
    # Index line claims explicit -- must NOT be trusted; hook must read the
    # real entry file, not the index's mirrored copy.
    add_index_line(cwd, "baz-mistake", "Baz Mistake", "error-prevention",
                    index_confidence="explicit", paths=[target_rel])

    proc = run_hook({"tool_input": {"file_path": target_abs}, "cwd": cwd})

    assert proc.returncode == 0
    assert proc.stdout == ""


def test_no_matching_paths_is_silent(tmp_path):
    cwd = str(tmp_path / "project")
    make_entry(cwd, "unrelated", "file-relevance", description="about something else")
    add_index_line(cwd, "unrelated", "Unrelated", "file-relevance", paths=["src/other.py"])

    target_abs = os.path.join(cwd, "src", "foo.py")
    proc = run_hook({"tool_input": {"file_path": target_abs}, "cwd": cwd})

    assert proc.returncode == 0
    assert proc.stdout == ""


def test_missing_memory_store_is_silent(tmp_path):
    cwd = str(tmp_path / "project-with-no-memory")
    target_abs = os.path.join(cwd, "src", "foo.py")

    proc = run_hook({"tool_input": {"file_path": target_abs}, "cwd": cwd})

    assert proc.returncode == 0
    assert proc.stdout == ""


def test_nelly_gate_off_is_silent_even_on_match(tmp_path):
    cwd = str(tmp_path / "project")
    target_rel = "src/foo.py"
    target_abs = os.path.join(cwd, target_rel)
    make_entry(cwd, "foo-notes", "file-relevance", description="notes about foo.py")
    add_index_line(cwd, "foo-notes", "Foo Notes", "file-relevance", paths=[target_rel])

    proc = run_hook({"tool_input": {"file_path": target_abs}, "cwd": cwd}, env={"NELLY_GATE": "off"})

    assert proc.returncode == 0
    assert proc.stdout == ""


@pytest.mark.parametrize("value", ["0", "false", "disabled", "OFF", "False"])
def test_nelly_gate_off_aliases_case_insensitive(tmp_path, value):
    cwd = str(tmp_path / "project")
    target_rel = "src/foo.py"
    target_abs = os.path.join(cwd, target_rel)
    make_entry(cwd, "foo-notes", "file-relevance", description="notes about foo.py")
    add_index_line(cwd, "foo-notes", "Foo Notes", "file-relevance", paths=[target_rel])

    proc = run_hook({"tool_input": {"file_path": target_abs}, "cwd": cwd}, env={"NELLY_GATE": value})

    assert proc.returncode == 0
    assert proc.stdout == ""


def test_two_matching_entries_emit_exactly_one_reason(tmp_path):
    cwd = str(tmp_path / "project")
    target_rel = "src/foo.py"
    target_abs = os.path.join(cwd, target_rel)
    make_entry(cwd, "foo-notes", "file-relevance", description="first match")
    add_index_line(cwd, "foo-notes", "Foo Notes", "file-relevance", paths=[target_rel])
    make_entry(cwd, "foo-notes-2", "file-relevance", description="second match")
    add_index_line(cwd, "foo-notes-2", "Foo Notes 2", "file-relevance", paths=[target_rel])

    proc = run_hook({"tool_input": {"file_path": target_abs}, "cwd": cwd})

    assert proc.returncode == 0
    # Exactly one JSON object on stdout -> exactly one reason emitted.
    stdout_lines = [ln for ln in proc.stdout.splitlines() if ln.strip()]
    assert len(stdout_lines) == 1
    out = json.loads(stdout_lines[0])
    assert out["hookSpecificOutput"]["permissionDecision"] == "allow"
