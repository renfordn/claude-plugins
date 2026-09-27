"""Slice 9: hooks/checkpoint_push.py fails open on bad input, corrupt state, and missing
plugin data -- including the New-F2 infinite-reblock case (env-only opt-in with no
CLAUDE_PLUGIN_DATA to persist a nonce)."""
import json
import os
import subprocess
import sys
from pathlib import Path

HOOK = Path(__file__).resolve().parent.parent / "hooks" / "checkpoint_push.py"
SESSION = "sess-failopen"


def _ack(nonce="a1b2c3d4"):
    return f'<!--CHECKPOINT-PUSHED:type=gate id="x" nonce="{nonce}"-->'


def _run(payload, env_extra):
    # Explicitly clear both vars rather than relying on them being absent from the inherited
    # environment: in the combined `pytest focus-ux agent-isdd agent-tdd` run, agent-isdd's
    # conftest.py sets CLAUDE_PLUGIN_DATA process-wide at import time, which would otherwise
    # silently take these "no plugin data" tests down a different (real-state) code path.
    env = {k: v for k, v in os.environ.items()
           if k not in ("FOCUS_UX_CHECKPOINT_PUSH", "CLAUDE_PLUGIN_DATA")}
    env.update(env_extra)
    return subprocess.run(
        [sys.executable, str(HOOK)], input=json.dumps(payload) if payload is not None else "",
        capture_output=True, text=True, env=env, timeout=30,
    )


def _payload(tmp_path, **extra):
    cwd = tmp_path / "proj"
    cwd.mkdir(exist_ok=True)
    transcript = tmp_path / "t.jsonl"
    transcript.write_text("")
    base = {
        "session_id": SESSION, "transcript_path": str(transcript), "cwd": str(cwd),
        "hook_event_name": "Stop", "stop_hook_active": False,
    }
    base.update(extra)
    return base


def test_non_json_stdin_exits_zero_silently(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    result = subprocess.run(
        [sys.executable, str(HOOK)], input="not json at all",
        capture_output=True, text=True, timeout=30,
        env={**os.environ, "CLAUDE_PLUGIN_DATA": str(data)},
    )
    assert result.returncode == 0
    assert result.stdout.strip() == ""


def test_corrupt_state_file_with_env_one_treated_as_defaults(tmp_path):
    data = tmp_path / "data"
    state_dir = data / "checkpoint-push"
    state_dir.mkdir(parents=True)
    (state_dir / f"{SESSION}.json").write_text("{not json")
    result = _run(_payload(tmp_path), {"CLAUDE_PLUGIN_DATA": str(data),
                                        "FOCUS_UX_CHECKPOINT_PUSH": "1"})
    assert result.returncode == 0, result.stderr
    out = json.loads(result.stdout)
    assert out["decision"] == "block"


def test_no_plugin_data_and_no_env_stays_quiet(tmp_path):
    result = _run(_payload(tmp_path), {})
    assert result.returncode == 0
    assert result.stdout.strip() == ""


# ---------------------------- New-F2: no plugin data, must never re-block forever ----------


def test_no_plugin_data_env_one_stop_hook_active_and_valid_ack_does_not_reblock(tmp_path):
    """The exact New-F2 reproduction: with nowhere to persist a nonce, checkpoint_push.py must
    not re-block forever. stop_hook_active true plus a parseable ack in the model's last turn
    is trusted as "this was Stop 2" (accepted quiet-miss risk over an infinite block loop)."""
    result = _run(
        _payload(tmp_path, stop_hook_active=True, last_assistant_message=_ack()),
        {"FOCUS_UX_CHECKPOINT_PUSH": "1"},
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == ""


def test_no_plugin_data_env_one_stop_hook_active_alone_stays_quiet(tmp_path):
    result = _run(
        _payload(tmp_path, stop_hook_active=True),
        {"FOCUS_UX_CHECKPOINT_PUSH": "1"},
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == ""


def test_no_plugin_data_env_one_valid_ack_alone_stays_quiet(tmp_path):
    result = _run(
        _payload(tmp_path, stop_hook_active=False, last_assistant_message=_ack()),
        {"FOCUS_UX_CHECKPOINT_PUSH": "1"},
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == ""


def test_no_plugin_data_env_one_neither_signal_blocks(tmp_path):
    """Without stop_hook_active or an ack, this is a genuine first Stop -- it must still block,
    even though nothing can be persisted."""
    result = _run(
        _payload(tmp_path, stop_hook_active=False),
        {"FOCUS_UX_CHECKPOINT_PUSH": "1"},
    )
    assert result.returncode == 0, result.stderr
    out = json.loads(result.stdout)
    assert out["decision"] == "block"


def test_with_plugin_data_stop_hook_active_alone_still_blocks():
    """F4 regression guard: once real state CAN be persisted, stop_hook_active alone must
    never suppress Stop 1 -- only the New-F2 no-plugin-data fallback trusts it."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        data = tmp_path / "data"
        state_dir = data / "checkpoint-push"
        state_dir.mkdir(parents=True)
        (state_dir / f"{SESSION}.json").write_text(
            json.dumps({"opted_in": True, "pending": None, "last": None})
        )
        result = _run(
            _payload(tmp_path, stop_hook_active=True, last_assistant_message=_ack()),
            {"CLAUDE_PLUGIN_DATA": str(data)},
        )
        assert result.returncode == 0, result.stderr
        out = json.loads(result.stdout)
        assert out["decision"] == "block"
