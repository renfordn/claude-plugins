"""Slice 7 -- checkpoint_push Stop hook, second Stop (pending set): records a matching ack and
never re-blocks.

Runs hooks/checkpoint_push.py as a subprocess with JSON stdin and CLAUDE_PLUGIN_DATA=<tmp_path>.
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parent.parent / "hooks" / "checkpoint_push.py"

SESSION = "sess-stop2"
NONCE = "a1b2c3d4"
OTHER_NONCE = "deadbeef"


def ack(type_="gate", id_="gate:deploy", nonce=NONCE, reason=None):
    extra = f' reason="{reason}"' if reason else ""
    return f'<!--CHECKPOINT-PUSHED:type={type_} id="{id_}" nonce="{nonce}"{extra}-->'


def state_dir(data: Path) -> Path:
    return data / "checkpoint-push"


def state_path(data: Path, session=SESSION) -> Path:
    return state_dir(data) / f"{session}.json"


def log_path(data: Path) -> Path:
    return data / "checkpoint-push.log"


def write_state(data: Path, pending=NONCE, session=SESSION):
    state_dir(data).mkdir(parents=True, exist_ok=True)
    state_path(data, session).write_text(
        json.dumps({"opted_in": True, "pending": pending, "last": None})
    )


def write_transcript(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "transcript.jsonl"
    lines = [
        {"type": "user", "message": {"role": "user", "content": "hi"}},
        {
            "type": "assistant",
            "message": {"role": "assistant", "content": [{"type": "text", "text": text}]},
        },
    ]
    path.write_text("\n".join(json.dumps(l) for l in lines) + "\n")
    return path


def run_hook(data: Path, transcript: Path, last_msg=None):
    payload = {
        "session_id": SESSION,
        "transcript_path": str(transcript),
        "cwd": str(data),
        "hook_event_name": "Stop",
        "stop_hook_active": False,
    }
    if last_msg is not None:
        payload["last_assistant_message"] = last_msg
    env = dict(os.environ, CLAUDE_PLUGIN_DATA=str(data))
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )


def read_state(data: Path) -> dict:
    return json.loads(state_path(data).read_text())


def log_lines(data: Path) -> list:
    p = log_path(data)
    return p.read_text().splitlines() if p.exists() else []


def seed_log(data: Path):
    data.mkdir(parents=True, exist_ok=True)
    log_path(data).write_text("preexisting line\n")


# --- matching ack ---------------------------------------------------------------------------

def assert_recorded(data: Path, result, type_="gate", id_="gate:deploy"):
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == ""
    state = read_state(data)
    assert state["pending"] is None
    last = state["last"]
    assert isinstance(last, dict)
    assert last["type"] == type_
    assert last["id"] == id_
    assert last.get("ts"), "last.ts must be a non-empty timestamp"


def test_matching_ack_via_payload_records_last_and_clears_pending(tmp_path):
    data = tmp_path / "data"
    write_state(data)
    transcript = write_transcript(tmp_path, "no ack in transcript")
    result = run_hook(data, transcript, last_msg=f"Deploy approved.\n{ack()}")
    assert_recorded(data, result)


def test_matching_ack_via_transcript_fallback(tmp_path):
    data = tmp_path / "data"
    write_state(data)
    transcript = write_transcript(
        tmp_path, f"Step done.\n{ack(type_='step', id_='step:3-build')}"
    )
    result = run_hook(data, transcript)  # no last_assistant_message
    assert_recorded(data, result, type_="step", id_="step:3-build")


# --- mismatch / missing ack: never re-block, clear pending, log -----------------------------

def assert_logged_no_block(data: Path, result):
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "", "Stop 2 must never emit a block decision"
    assert read_state(data)["pending"] is None
    lines = log_lines(data)
    assert lines[0] == "preexisting line", "log must be appended to, not truncated"
    assert len(lines) >= 2, "expected a new line appended to checkpoint-push.log"
    return lines[1:]


def test_wrong_nonce_ack_does_not_block_and_logs(tmp_path):
    data = tmp_path / "data"
    write_state(data)
    seed_log(data)
    transcript = write_transcript(tmp_path, "nothing")
    result = run_hook(data, transcript, last_msg=ack(nonce=OTHER_NONCE))
    assert_logged_no_block(data, result)


def test_no_ack_does_not_block_and_logs(tmp_path):
    data = tmp_path / "data"
    write_state(data)
    seed_log(data)
    transcript = write_transcript(tmp_path, "plain answer, no ack")
    result = run_hook(data, transcript, last_msg="plain answer, no ack")
    assert_logged_no_block(data, result)


def test_no_ack_in_transcript_fallback_does_not_block_and_logs(tmp_path):
    data = tmp_path / "data"
    write_state(data)
    seed_log(data)
    transcript = write_transcript(tmp_path, "plain answer, no ack")
    result = run_hook(data, transcript)
    assert_logged_no_block(data, result)


def test_none_unavailable_ack_is_logged(tmp_path):
    data = tmp_path / "data"
    write_state(data)
    seed_log(data)
    transcript = write_transcript(tmp_path, "nothing")
    result = run_hook(
        data, transcript,
        last_msg=ack(type_="none", id_="none", reason="unavailable"),
    )
    new_lines = assert_logged_no_block(data, result)
    assert any("unavailable" in l for l in new_lines), new_lines


# --- stale-state pruning --------------------------------------------------------------------

def test_prunes_stale_other_session_state_keeps_fresh(tmp_path):
    data = tmp_path / "data"
    write_state(data)
    d = state_dir(data)
    stale = d / "old-session.json"
    fresh = d / "recent-session.json"
    for p in (stale, fresh):
        p.write_text(json.dumps({"opted_in": True, "pending": None, "last": None}))
    now = time.time()
    old = now - 8 * 24 * 3600
    os.utime(stale, (old, old))
    recent = now - 1 * 24 * 3600
    os.utime(fresh, (recent, recent))

    transcript = write_transcript(tmp_path, "nothing")
    result = run_hook(data, transcript, last_msg=ack())

    assert result.returncode == 0, result.stderr
    assert not stale.exists(), "state older than 7 days must be pruned"
    assert fresh.exists(), "state younger than 7 days must be kept"
    assert state_path(data).exists(), "current session state must be kept"
