"""Slice 8: hooks/checkpoint_push.py Stop 1 -- a producer marker matching `last.id` skips the
block (R8 dedup): the same unresolved gate/input re-stopping the session must not push again."""
import json
import os
import subprocess
import sys
from pathlib import Path

HOOK = Path(__file__).resolve().parent.parent / "hooks" / "checkpoint_push.py"
SESSION = "sess-dedup"


def _assistant_line(text):
    return {"type": "assistant", "message": {"role": "assistant",
                                             "content": [{"type": "text", "text": text}]}}


def _write_transcript(path, lines):
    path.write_text("".join(json.dumps(line) + "\n" for line in lines), encoding="utf-8")
    return path


def _state_path(data_dir):
    return data_dir / "checkpoint-push" / f"{SESSION}.json"


def _write_state(data_dir, last=None):
    p = _state_path(data_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"opted_in": True, "pending": None, "last": last}))


def _read_state(data_dir):
    return json.loads(_state_path(data_dir).read_text())


def _run(tmp_path, text):
    data_dir = tmp_path / "plugin-data"
    data_dir.mkdir(exist_ok=True)
    cwd = tmp_path / "proj"
    cwd.mkdir(exist_ok=True)
    transcript = _write_transcript(tmp_path / "t.jsonl", [_assistant_line(text)])
    payload = {
        "session_id": SESSION,
        "transcript_path": str(transcript),
        "cwd": str(cwd),
        "hook_event_name": "Stop",
        "stop_hook_active": False,
        "last_assistant_message": text,
    }
    env = dict(os.environ, CLAUDE_PLUGIN_DATA=str(data_dir))
    env.pop("FOCUS_UX_CHECKPOINT_PUSH", None)
    proc = subprocess.run(
        [sys.executable, str(HOOK)], input=json.dumps(payload),
        capture_output=True, text=True, env=env, timeout=30,
    )
    return proc, data_dir


def test_matching_marker_name_skips_the_block(tmp_path):
    _write_state(tmp_path / "plugin-data", last={"type": "gate", "id": "isdd:design", "ts": "t"})
    marker = '<!--CHECKPOINT:type=gate name="isdd:design" need="approve"-->'
    proc, data_dir = _run(tmp_path, "Still waiting.\n" + marker)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == ""
    state = _read_state(data_dir)
    assert state["pending"] is None
    assert state["last"] == {"type": "gate", "id": "isdd:design", "ts": "t"}


def test_different_marker_name_still_blocks_with_last_id_in_reason(tmp_path):
    _write_state(tmp_path / "plugin-data", last={"type": "gate", "id": "isdd:design", "ts": "t"})
    marker = '<!--CHECKPOINT:type=gate name="isdd:tasks" need="approve"-->'
    proc, data_dir = _run(tmp_path, "Now this.\n" + marker)
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    assert out["decision"] == "block"
    assert "isdd:design" in out["reason"]
    state = _read_state(data_dir)
    assert isinstance(state["pending"], str) and state["pending"]


def test_no_last_and_no_marker_blocks_normally(tmp_path):
    _write_state(tmp_path / "plugin-data", last=None)
    proc, data_dir = _run(tmp_path, "Just finished.")
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    assert out["decision"] == "block"
