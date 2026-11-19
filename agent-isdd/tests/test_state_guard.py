"""state_guard.evaluate: deny illegal Track/Risk transitions on the active workflow-state.md."""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hooks"))
import state_guard  # noqa: E402


def _text(track="Standard", risk="low", mode="agent"):
    return ("# State\n- Feature: f\n- Track: %s\n- Risk: %s\n- Implementation Mode: %s\n"
            "- Current Phase: Design\n" % (track, risk, mode))


def _payload(tool, path, old, new, cwd):
    """Payload for a Write/Edit/MultiEdit turning the `old` state text into the `new` one."""
    if tool == "Write":
        ti = {"file_path": str(path), "content": new}
    elif tool == "Edit":
        ti = {"file_path": str(path), "old_string": old, "new_string": new}
    else:
        ti = {"file_path": str(path), "edits": [{"old_string": old, "new_string": new}]}
    return {"cwd": str(cwd), "tool_name": tool, "tool_input": ti}


@pytest.fixture
def state(tmp_path):
    return tmp_path / "workflow-state.md"


TOOLS = ["Write", "Edit", "MultiEdit"]


@pytest.mark.parametrize("tool", TOOLS)
@pytest.mark.parametrize("before,after,denied", [
    (dict(track="Standard"), dict(track="Fast"), True),                       # Standard -> Fast
    (dict(track="Standard", risk="elevated"), dict(track="Fast", risk="elevated"), True),
    (dict(track="", risk="elevated"), dict(track="Fast", risk="elevated"), True),  # newly Fast, Risk > low
    (dict(track="Fast", risk="low"), dict(track="Fast", risk="elevated"), True),   # result Fast + Risk > low
    (dict(track="Fast", risk="elevated"), dict(track="Fast", risk="elevated", mode="user"), True),  # pre-existing bad state: must fix
    (dict(track="Fast", risk="low"), dict(track="Standard", risk="elevated"), False),  # raise + Standard together
    (dict(track="Fast", risk="elevated"), dict(track="Standard", risk="elevated"), False),  # fix pre-existing
    (dict(risk="high"), dict(risk="elevated"), True),                         # downgrade
    (dict(risk="elevated"), dict(risk="low"), True),
    (dict(risk="high"), dict(risk="low"), True),
    (dict(risk="low"), dict(risk="elevated"), False),                         # raise ok
    (dict(risk="low"), dict(risk="high"), False),
    (dict(risk="elevated"), dict(risk="elevated"), False),                    # unchanged
    (dict(track="Fast", risk="low"), dict(track="Fast", risk="low", mode="user"), False),
    (dict(track="Fast", risk="elevated"), dict(track="Standard", risk="elevated"), False),
])
def test_transitions(state, tool, before, after, denied):
    old, new = _text(**before), _text(**after)
    state.write_text(old)
    reason = state_guard.evaluate(_payload(tool, state, old, new, state.parent), state_path=str(state))
    if denied:
        assert reason and isinstance(reason, str)
    else:
        assert reason is None


def test_reason_mentions_cause(state):
    old, new = _text(), _text(track="Fast")
    state.write_text(old)
    r = state_guard.evaluate(_payload("Write", state, old, new, state.parent), state_path=str(state))
    assert "Fast" in r
    old, new = _text(risk="high"), _text(risk="low")
    state.write_text(old)
    r = state_guard.evaluate(_payload("Write", state, old, new, state.parent), state_path=str(state))
    assert "Risk" in r


def test_fast_with_risk_text(state):
    old, new = _text(track="Fast", risk="low"), _text(track="Fast", risk="high")
    state.write_text(old)
    r = state_guard.evaluate(_payload("Write", state, old, new, state.parent), state_path=str(state))
    assert "Risk above low requires Track: Standard" in r
    assert "set Track: Standard in the same edit" in r


def test_other_files_untouched(tmp_path, state):
    state.write_text(_text())
    other = tmp_path / "notes.md"
    other.write_text("x")
    p = {"cwd": str(tmp_path), "tool_name": "Write",
         "tool_input": {"file_path": str(other), "content": _text(track="Fast")}}
    assert state_guard.evaluate(p, state_path=str(state)) is None


def test_symlinked_state_path_still_guarded(tmp_path, state):
    old, new = _text(), _text(track="Fast")
    state.write_text(old)
    link = tmp_path / "link.md"
    os.symlink(state, link)
    assert state_guard.evaluate(_payload("Write", link, old, new, tmp_path), state_path=str(state))


@pytest.mark.parametrize("payload,sp", [
    ({}, None), ({}, "/nonexistent/workflow-state.md"), ("junk", "x"),
    ({"tool_input": "bad"}, "x"), ({"tool_name": "Write", "tool_input": {}}, "x"),
])
def test_fail_open(payload, sp):
    assert state_guard.evaluate(payload, state_path=sp) is None


def test_mode_change_logged_not_denied(state, tmp_path):
    old, new = _text(mode="user"), _text(mode="agent")
    state.write_text(old)
    r = state_guard.evaluate(_payload("Write", state, old, new, tmp_path), state_path=str(state))
    assert r is None
    data = json.loads((tmp_path / "workflow-state.json").read_text())
    entry = data["hook_history"][-1]
    assert entry["hook"] == "state_guard/mode_switch"
    assert entry["from"] == "user" and entry["to"] == "agent"


def test_no_mode_change_no_log(state, tmp_path):
    old, new = _text(), _text(risk="high")
    state.write_text(old)
    state_guard.evaluate(_payload("Write", state, old, new, tmp_path), state_path=str(state))
    assert not (tmp_path / "workflow-state.json").exists()


def test_denied_write_not_logged(state, tmp_path):
    old, new = _text(mode="user", risk="high"), _text(mode="agent", risk="low")
    state.write_text(old)
    assert state_guard.evaluate(_payload("Write", state, old, new, tmp_path), state_path=str(state))
    assert not (tmp_path / "workflow-state.json").exists()


def _raw(track=None, risk=None):
    lines = ["# State", "- Feature: f"]
    if track is not None:
        lines.append("- Track: %s" % track)
    if risk is not None:
        lines.append("- Risk: %s" % risk)
    return "\n".join(lines) + "\n"


@pytest.mark.parametrize("tool", TOOLS)
@pytest.mark.parametrize("old,new,denied", [
    (_raw("Standard", "low"), _raw(None, "low"), True),            # Track removed
    (_raw("Standard", "low"), _raw("", "low"), True),              # Track blank
    (_raw("Standard", "low"), _raw("fast", "low"), True),
    (_raw("Standard", "low"), _raw("FAST ", "low"), True),
    (_raw("Standard", "low"), _raw("Standard (x)", "low"), False),  # annotated: first token compared (F1)
    (_raw("Standard (x)", "low"), _raw("Fast", "low"), True),      # old annotated
    (_raw("Standard", "low"), _raw("Standard", "low"), False),
    (_raw("Fast", "low"), _raw("Standard", "low"), False),         # Fast -> Standard legal
    (_raw(None, "low"), _raw("Fast", "low"), False),               # absent -> Fast (start)
    (_raw("TBD", "low"), _raw("Fast", "low"), False),
    (_raw(None, "elevated"), _raw("Fast", "elevated"), True),
    (_raw("Standard", "high"), _raw("Standard", None), True),      # Risk removed
    (_raw("Standard", "high"), _raw("Standard", ""), True),        # Risk blank
    (_raw("Standard", "high"), _raw("Standard", "medium"), True),  # unknown
    (_raw("Standard", "low"), _raw("Standard", "low (re-assessed)"), False),  # annotated, same level (F1)
    (_raw("Standard", "low"), _raw("Standard", "High"), False),
    (_raw("Standard", None), _raw("Standard", "low"), False),      # old Risk unset
])
def test_normalisation_and_removal(state, tool, old, new, denied):
    state.write_text(old)
    r = state_guard.evaluate(_payload(tool, state, old, new, state.parent), state_path=str(state))
    assert bool(r) is denied


def test_multiedit_edits_only_together_illegal(state):
    old = _text(track="Standard", risk="high")
    state.write_text(old)
    edits = [{"old_string": "- Track: Standard", "new_string": "- Track: Fast"},
             {"old_string": "- Risk: high", "new_string": "- Risk: low"}]
    p = {"cwd": str(state.parent), "tool_name": "MultiEdit",
         "tool_input": {"file_path": str(state), "edits": edits}}
    assert state_guard.evaluate(p, state_path=str(state))


def test_hook_history_trimmed_and_attempted(state, tmp_path):
    js = tmp_path / "workflow-state.json"
    js.write_text(json.dumps({"hook_history": [{"hook": "x"}] * 150}))
    old, new = _text(mode="user"), _text(mode="agent")
    state.write_text(old)
    assert state_guard.evaluate(_payload("Write", state, old, new, tmp_path), state_path=str(state)) is None
    hist = json.loads(js.read_text())["hook_history"]
    assert len(hist) == 100
    assert hist[-1]["outcome"] == "Attempted"
    assert hist[-1]["timestamp"].endswith("Z")


_BARE = "# State\n- Feature: f\n- Current Phase: Requirements\n"


@pytest.mark.parametrize("tool", TOOLS)
@pytest.mark.parametrize("added,denied", [
    ("- Track: Fast\n- Risk: low\n- Risk Reason: one doc file\n", False),  # Start: one write adds both
    ("- Track: Fast\n", False),                                             # Risk still blank
    ("- Track: Fast\n- Risk: elevated\n", True),
])
def test_start_time_fast_and_risk_written_together(state, tool, added, denied):
    """Slice 23 review F4: the documented Start step (Risk: low with/before Track: Fast)."""
    state.write_text(_BARE)
    payload = _payload(tool, state, _BARE, _BARE + added, state.parent)
    assert bool(state_guard.evaluate(payload, state_path=str(state))) is denied


@pytest.mark.parametrize("tool", TOOLS)
@pytest.mark.parametrize("before,after,denied", [
    # annotated old values: an unrelated edit is never denied
    (dict(track="Standard (escalated from Fast)", risk="high (auth)"),
     dict(track="Standard (escalated from Fast)", risk="high (auth)", mode="user"), False),
    (dict(track="Fast", risk="low (one-liner)"),
     dict(track="Fast", risk="low (one-liner)", mode="user"), False),
    (dict(track="Standard", risk="elevated (db)"),
     dict(track="Standard", risk="elevated (db)", mode="user"), False),
    # annotated new values are compared by first token too
    (dict(track="Fast", risk="low"), dict(track="Fast (small)", risk="low (tiny)"), False),
    (dict(track="Fast", risk="low"), dict(track="Standard (grew)", risk="high (auth)"), False),
    # still denied when the first token says so
    (dict(track="Standard (x)", risk="low"), dict(track="Fast (y)", risk="low"), True),
    (dict(track="Standard", risk="high (auth)"), dict(track="Standard", risk="low (oops)"), True),
    (dict(track="Fast", risk="low"), dict(track="Fast (a)", risk="high (auth)"), True),
])
def test_annotated_values(state, tool, before, after, denied):
    old, new = _text(**before), _text(**after)
    state.write_text(old)
    reason = state_guard.evaluate(_payload(tool, state, old, new, state.parent), state_path=str(state))
    assert bool(reason) is denied
