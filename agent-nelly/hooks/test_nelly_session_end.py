"""Tests for hooks/nelly_session_end.py -- SessionEnd hook that writes a
`session-handoff` entry summarizing session activity, reconstructed purely
from the session's own transcript file (SessionEnd's payload carries only a
`transcript_path`, not inline tool-call history).

Drives the hook exactly as the harness does: pipe a JSON payload on stdin to
the script via subprocess, and assert on stdout + the resulting memory
store, same style as test_nelly_commit_extract.py. Also unit-tests the
transcript-scanning helpers directly, since building realistic transcript
fixtures is easier to reason about at that level than through the full
subprocess round-trip for every case.
"""
import json
import os
import re
import subprocess
import sys

HOOK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nelly_session_end.py")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nelly_session_end as session_end  # noqa: E402


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
        env=dict(env),
    )
    assert proc.returncode == 0, proc.stderr
    return proc.stdout.strip()


def _assistant_tool_use(tool_id, name, tool_input):
    return {
        "type": "assistant",
        "message": {"content": [{"type": "tool_use", "id": tool_id, "name": name, "input": tool_input}]},
    }


def _user_tool_result(tool_id, content_text):
    return {
        "type": "user",
        "message": {"content": [{"type": "tool_result", "tool_use_id": tool_id, "content": content_text}]},
    }


def _write_transcript(tmp_path, lines, name="transcript.jsonl"):
    path = tmp_path / name
    with open(path, "w", encoding="utf-8") as fh:
        for obj in lines:
            fh.write(json.dumps(obj) + "\n")
    return str(path)


def _session_end_payload(cwd, transcript_path, reason="other"):
    return {
        "session_id": "test-session",
        "transcript_path": transcript_path,
        "cwd": cwd,
        "hook_event_name": "SessionEnd",
        "reason": reason,
    }


COMMIT_OUTPUT = """\
[main abc1234] Fix the thing
 1 file changed, 3 insertions(+), 1 deletion(-)
"""


# ---------------------------------------------------------------------------
# scan_transcript / helpers (unit-level)
# ---------------------------------------------------------------------------

def test_scan_transcript_extracts_edited_files(tmp_path):
    cwd = str(tmp_path / "project")
    lines = [
        _assistant_tool_use("t1", "Write", {"file_path": os.path.join(cwd, "hooks/foo.py")}),
        _assistant_tool_use("t2", "Edit", {"file_path": os.path.join(cwd, "scripts/bar.py")}),
    ]
    path = _write_transcript(tmp_path, lines)

    summary = session_end.scan_transcript(path, cwd)

    assert summary["edited_files"] == ["hooks/foo.py", "scripts/bar.py"]
    assert summary["touched_files"] == ["hooks/foo.py", "scripts/bar.py"]


def test_scan_transcript_dedupes_repeated_edits(tmp_path):
    cwd = str(tmp_path / "project")
    lines = [
        _assistant_tool_use("t1", "Write", {"file_path": os.path.join(cwd, "hooks/foo.py")}),
        _assistant_tool_use("t2", "Edit", {"file_path": os.path.join(cwd, "hooks/foo.py")}),
    ]
    path = _write_transcript(tmp_path, lines)

    summary = session_end.scan_transcript(path, cwd)

    assert summary["edited_files"] == ["hooks/foo.py"]


def test_scan_transcript_read_only_has_no_edited_files(tmp_path):
    cwd = str(tmp_path / "project")
    lines = [_assistant_tool_use("t1", "Read", {"file_path": os.path.join(cwd, "hooks/foo.py")})]
    path = _write_transcript(tmp_path, lines)

    summary = session_end.scan_transcript(path, cwd)

    assert summary["edited_files"] == []
    assert summary["touched_files"] == ["hooks/foo.py"]


def test_scan_transcript_detects_commit_from_bash_result(tmp_path):
    cwd = str(tmp_path / "project")
    lines = [
        _assistant_tool_use("t1", "Bash", {"command": "git commit -m 'Fix the thing'"}),
        _user_tool_result("t1", COMMIT_OUTPUT),
    ]
    path = _write_transcript(tmp_path, lines)

    summary = session_end.scan_transcript(path, cwd)

    assert summary["commit_subjects"] == ["Fix the thing"]


def test_scan_transcript_ignores_non_bash_tool_result(tmp_path):
    cwd = str(tmp_path / "project")
    lines = [
        _assistant_tool_use("t1", "Read", {"file_path": os.path.join(cwd, "foo.py")}),
        _user_tool_result("t1", COMMIT_OUTPUT),  # coincidentally looks like a commit
    ]
    path = _write_transcript(tmp_path, lines)

    summary = session_end.scan_transcript(path, cwd)

    assert summary["commit_subjects"] == []


def test_scan_transcript_counts_test_runs(tmp_path):
    cwd = str(tmp_path / "project")
    lines = [
        _assistant_tool_use("t1", "Bash", {"command": "pytest hooks/"}),
        _assistant_tool_use("t2", "Bash", {"command": "npm test"}),
        _assistant_tool_use("t3", "Bash", {"command": "git status"}),
    ]
    path = _write_transcript(tmp_path, lines)

    summary = session_end.scan_transcript(path, cwd)

    assert summary["test_run_count"] == 2


def test_scan_transcript_missing_file_is_empty(tmp_path):
    cwd = str(tmp_path / "project")
    summary = session_end.scan_transcript(str(tmp_path / "does-not-exist.jsonl"), cwd)
    assert summary == {
        "edited_files": [],
        "touched_files": [],
        "commit_subjects": [],
        "test_run_count": 0,
    }


def test_scan_transcript_skips_malformed_lines(tmp_path):
    cwd = str(tmp_path / "project")
    path = tmp_path / "transcript.jsonl"
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("not json at all\n")
        fh.write(json.dumps(_assistant_tool_use("t1", "Write", {"file_path": os.path.join(cwd, "foo.py")})) + "\n")
        fh.write("{broken\n")  # truncated tail, as an async-written transcript can have

    summary = session_end.scan_transcript(str(path), cwd)

    assert summary["edited_files"] == ["foo.py"]


def test_recent_focus_most_recent_first_deduped():
    touched = ["hooks/a.py", "scripts/b.py", "hooks/c.py", "README.md"]
    assert session_end._recent_focus(touched, n=4) == ["README.md", "hooks", "scripts"]


def test_build_description_includes_files_commit_and_focus():
    desc = session_end._build_description(
        ["hooks/foo.py", "scripts/bar.py"], ["Fix the thing"], ["hooks", "scripts"]
    )
    assert desc == (
        "Session ended -- active files: hooks/foo.py, scripts/bar.py. "
        "Last commit: Fix the thing. Recent focus: hooks, scripts."
    )


def test_build_description_no_activity_fallback():
    assert session_end._build_description([], [], []) == "Session ended -- no significant activity detected."


# ---------------------------------------------------------------------------
# end-to-end hook behavior
# ---------------------------------------------------------------------------

def test_active_session_writes_handoff_entry(tmp_path):
    env = _isolated_env(tmp_path)
    cwd = str(tmp_path / "project")
    transcript_lines = [
        _assistant_tool_use("t1", "Write", {"file_path": os.path.join(cwd, "hooks/nelly_session_end.py")}),
        _assistant_tool_use("t2", "Bash", {"command": "git commit -m 'Fix the thing'"}),
        _user_tool_result("t2", COMMIT_OUTPUT),
    ]
    transcript_path = _write_transcript(tmp_path, transcript_lines)
    payload = _session_end_payload(cwd, transcript_path)

    proc = run_hook(payload, env=env)

    assert proc.returncode == 0, proc.stderr
    m = re.match(r"\[nelly\] session handoff saved: (session-handoff-\S+)", proc.stdout.strip())
    assert m, proc.stdout
    slug = m.group(1)

    mem_dir = _memory_dir(cwd, env)
    entries_dir = os.path.join(mem_dir, "entries")
    entries = os.listdir(entries_dir)
    assert entries == [f"{slug}.md"]

    text = open(os.path.join(entries_dir, entries[0])).read()
    assert "type: technique" in text
    assert "confidence: inferred" in text
    assert "hooks/nelly_session_end.py" in text
    assert "Fix the thing" in text
    assert "tags: [hooks]" in text

    index = open(os.path.join(mem_dir, "MEMORY.md")).read()
    assert slug in index


def test_idle_session_is_noop(tmp_path):
    env = _isolated_env(tmp_path)
    cwd = str(tmp_path / "project")
    transcript_lines = [
        _assistant_tool_use("t1", "Read", {"file_path": os.path.join(cwd, "hooks/foo.py")}),
        _assistant_tool_use("t2", "Bash", {"command": "git status"}),
    ]
    transcript_path = _write_transcript(tmp_path, transcript_lines)
    payload = _session_end_payload(cwd, transcript_path)

    proc = run_hook(payload, env=env)

    assert proc.returncode == 0
    assert proc.stdout.strip() == ""
    mem_dir = _memory_dir(cwd, env)
    assert not os.path.isdir(os.path.join(mem_dir, "entries"))


def test_slug_matches_expected_format(tmp_path):
    env = _isolated_env(tmp_path)
    cwd = str(tmp_path / "project")
    transcript_lines = [
        _assistant_tool_use("t1", "Write", {"file_path": os.path.join(cwd, "foo.py")}),
    ]
    transcript_path = _write_transcript(tmp_path, transcript_lines)
    payload = _session_end_payload(cwd, transcript_path)

    proc = run_hook(payload, env=env)

    m = re.match(r"\[nelly\] session handoff saved: (session-handoff-\d{4}-\d{2}-\d{2}-\d{4})$", proc.stdout.strip())
    assert m, proc.stdout


def test_missing_transcript_path_is_noop(tmp_path):
    env = _isolated_env(tmp_path)
    cwd = str(tmp_path / "project")
    payload = _session_end_payload(cwd, str(tmp_path / "nope.jsonl"))

    proc = run_hook(payload, env=env)

    assert proc.returncode == 0
    assert proc.stdout.strip() == ""


def test_gate_off_disables_hook(tmp_path):
    env = _isolated_env(tmp_path)
    env["NELLY_GATE"] = "off"
    cwd = str(tmp_path / "project")
    transcript_lines = [
        _assistant_tool_use("t1", "Write", {"file_path": os.path.join(cwd, "foo.py")}),
    ]
    transcript_path = _write_transcript(tmp_path, transcript_lines)
    payload = _session_end_payload(cwd, transcript_path)

    proc = run_hook(payload, env=env)

    assert proc.returncode == 0
    assert proc.stdout.strip() == ""
    mem_dir = _memory_dir(cwd, env)
    assert not os.path.isdir(os.path.join(mem_dir, "entries"))


def test_malformed_stdin_is_swallowed_silently():
    proc = subprocess.run(
        [sys.executable, HOOK],
        input="not json",
        capture_output=True,
        text=True,
    )

    assert proc.returncode == 0
    assert proc.stdout.strip() == ""
    assert proc.stderr.strip() == ""


def test_duplicate_slug_within_same_minute_not_written_twice(tmp_path):
    env = _isolated_env(tmp_path)
    cwd = str(tmp_path / "project")
    transcript_lines = [
        _assistant_tool_use("t1", "Write", {"file_path": os.path.join(cwd, "foo.py")}),
    ]
    transcript_path = _write_transcript(tmp_path, transcript_lines)
    payload = _session_end_payload(cwd, transcript_path)

    first = run_hook(payload, env=env)
    assert first.stdout.startswith("[nelly] session handoff saved:")
    slug = first.stdout.strip().split(": ", 1)[1]

    second = run_hook(payload, env=env)

    mem_dir = _memory_dir(cwd, env)
    entries_dir = os.path.join(mem_dir, "entries")
    entries = os.listdir(entries_dir)
    if second.stdout.strip() == "":
        # Ran within the same minute as `first` -- same slug, correctly deduped.
        assert entries == [f"{slug}.md"]
    else:
        # Ran a minute later -- a second, distinct handoff entry is expected.
        assert len(entries) == 2
