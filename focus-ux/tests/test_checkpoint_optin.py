"""Slice 5: hooks/checkpoint_optin.py -- UserPromptSubmit opt-in, `last` reset, R1 rule inject."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from focus_ux_hook_test_utils import run_hook  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "hooks"))
import focus_ux_state as st  # noqa: E402

SESSION = "sess-optin"


def _payload(prompt, session_id=SESSION):
    return {"session_id": session_id, "prompt": prompt, "hook_event_name": "UserPromptSubmit"}


def _env(tmp_path, flag=None):
    env = {"CLAUDE_PLUGIN_DATA": str(tmp_path / "data")}
    if flag is not None:
        env["FOCUS_UX_CHECKPOINT_PUSH"] = flag
    return env


def _state(tmp_path, session_id=SESSION):
    return st.load_state(session_id, {"CLAUDE_PLUGIN_DATA": str(tmp_path / "data")})


def test_marker_opts_in_and_injects_r1_rule(tmp_path):
    out, rc = run_hook("checkpoint_optin.py", _payload("please help [checkpoint-push]"),
                        env_extra=_env(tmp_path))
    assert rc == 0
    assert _state(tmp_path)["opted_in"] is True
    ctx = out["hookSpecificOutput"]["additionalContext"]
    assert "PushNotification" in ctx
    assert "AskUserQuestion" in ctx


@pytest.mark.parametrize("prompt", [
    "the agent said `[checkpoint-push]` earlier",
    "report:\n```\n[checkpoint-push]\n```\ndone",
    "unterminated fence\n```\n[checkpoint-push]",
])
def test_quoted_marker_does_not_opt_in(tmp_path, prompt):
    out, rc = run_hook("checkpoint_optin.py", _payload(prompt), env_extra=_env(tmp_path))
    assert rc == 0
    assert out in (None, "", {})
    assert _state(tmp_path)["opted_in"] is False


def test_marker_outside_code_still_opts_in_when_also_quoted(tmp_path):
    run_hook("checkpoint_optin.py", _payload("`x` [checkpoint-push]"), env_extra=_env(tmp_path))
    assert _state(tmp_path)["opted_in"] is True


def test_marker_clears_last_on_opt_in(tmp_path):
    env = _env(tmp_path)
    st.save_state(SESSION, {"opted_in": False, "pending": None,
                             "last": {"type": "gate", "id": "x", "ts": "t"}}, env)
    run_hook("checkpoint_optin.py", _payload("[checkpoint-push] go"), env_extra=env)
    assert _state(tmp_path)["last"] is None


def test_later_prompt_without_marker_keeps_opt_in_but_clears_last(tmp_path):
    env = _env(tmp_path)
    st.save_state(SESSION, {"opted_in": True, "pending": None,
                             "last": {"type": "step", "id": "y", "ts": "t"}}, env)
    out, rc = run_hook("checkpoint_optin.py", _payload("do the next thing"), env_extra=env)
    assert rc == 0
    state = _state(tmp_path)
    assert state["opted_in"] is True
    assert state["last"] is None


def test_no_marker_and_not_opted_in_is_silent_and_writes_no_state(tmp_path):
    out, rc = run_hook("checkpoint_optin.py", _payload("just a normal prompt"),
                        env_extra=_env(tmp_path))
    assert rc == 0
    assert out is None
    assert not (tmp_path / "data" / "checkpoint-push" / f"{SESSION}.json").exists()


def test_env_one_opts_in_without_marker(tmp_path):
    out, rc = run_hook("checkpoint_optin.py", _payload("hello"), env_extra=_env(tmp_path, "1"))
    assert rc == 0
    assert _state(tmp_path)["opted_in"] is True


def test_env_zero_overrides_marker_off(tmp_path):
    out, rc = run_hook("checkpoint_optin.py", _payload("[checkpoint-push] go"),
                        env_extra=_env(tmp_path, "0"))
    assert rc == 0
    assert out is None
    assert not (tmp_path / "data" / "checkpoint-push" / f"{SESSION}.json").exists()


def test_marker_injects_rule_once_not_on_every_prompt(tmp_path):
    """Review F1/New-F3: the R1 rule must be injected exactly once per session, not on every
    prompt that happens to still carry the marker (or any prompt at all, while opted in)."""
    env = _env(tmp_path)
    out1, rc1 = run_hook("checkpoint_optin.py", _payload("[checkpoint-push] first"),
                          env_extra=env)
    assert rc1 == 0
    assert out1 is not None
    assert "PushNotification" in out1["hookSpecificOutput"]["additionalContext"]

    out2, rc2 = run_hook("checkpoint_optin.py", _payload("[checkpoint-push] second"),
                          env_extra=env)
    assert rc2 == 0
    assert out2 is None
    assert _state(tmp_path)["opted_in"] is True  # still opted in, just no re-injection


def test_env_one_injects_rule_once_across_repeated_calls(tmp_path):
    """Same guarantee for the persistent-env-var opt-in path: FOCUS_UX_CHECKPOINT_PUSH=1 stays
    set on every call, but the rule must not be reprinted on the second or third call."""
    env = _env(tmp_path, "1")
    out1, rc1 = run_hook("checkpoint_optin.py", _payload("hello"), env_extra=env)
    assert rc1 == 0
    assert out1 is not None

    out2, rc2 = run_hook("checkpoint_optin.py", _payload("hello again"), env_extra=env)
    assert rc2 == 0
    assert out2 is None

    out3, rc3 = run_hook("checkpoint_optin.py", _payload("and again"), env_extra=env)
    assert rc3 == 0
    assert out3 is None
    assert _state(tmp_path)["opted_in"] is True


def test_bad_stdin_json_exits_zero():
    import os
    import subprocess

    from focus_ux_hook_test_utils import HOOKS_DIR

    result = subprocess.run(
        ["python3", os.path.join(HOOKS_DIR, "checkpoint_optin.py")],
        input="not json", capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0
    assert result.stdout.strip() == ""


import pytest  # noqa: E402


@pytest.mark.parametrize("prompt,flag", [
    ("just a normal prompt", None),          # already opted in, no marker on this prompt
    ("go on [checkpoint-push]", None),        # marker on this prompt
    ("just a normal prompt", "1"),            # env-var opt-in
])
def test_new_prompt_clears_stale_pending(tmp_path, prompt, flag):
    """F2: a new user prompt starts a fresh cycle. A `pending` nonce left over from a Stop 1
    whose ack turn never produced a Stop 2 (API error / cancel) is stale, and must not make the
    next real Stop resolve as a Stop 2 and be allowed through with no push."""
    env = _env(tmp_path, flag)
    st.save_state(
        SESSION,
        {"opted_in": True, "pending": "3eeede8b", "last": None, "rule_injected": True},
        env,
    )
    assert _state(tmp_path)["pending"] == "3eeede8b"  # control: the seed really persisted

    _out, rc = run_hook("checkpoint_optin.py", _payload(prompt), env_extra=env)

    assert rc == 0
    assert _state(tmp_path)["pending"] is None
