"""Slice 3: hooks/focus_ux_transcript.py -- last assistant text and session title."""
import json
import os
import sys
from pathlib import Path

HOOKS = Path(__file__).resolve().parents[1] / "hooks"
sys.path.insert(0, str(HOOKS))
from focus_ux_transcript import last_assistant_text, session_title  # noqa: E402


def _assistant(text):
    return {"type": "assistant", "message": {"role": "assistant",
                                             "content": [{"type": "text", "text": text}]}}


def _write(path, events):
    path.write_text("".join(json.dumps(e) + "\n" for e in events))
    return str(path)


def test_prefers_payload_last_assistant_message(tmp_path):
    t = _write(tmp_path / "t.jsonl", [_assistant("from transcript")])
    assert last_assistant_text({"last_assistant_message": "from payload", "transcript_path": t}) \
        == "from payload"


def test_falls_back_to_transcript_last_assistant_block(tmp_path):
    t = _write(tmp_path / "t.jsonl", [
        _assistant("first"),
        {"type": "user", "message": {"role": "user", "content": "hi"}},
        _assistant("second"),
        {"type": "assistant", "message": {"role": "assistant",
                                          "content": [{"type": "tool_use", "name": "x"}]}},
    ])
    assert last_assistant_text({"transcript_path": t}) == "second"


def test_tail_read_only_covers_last_16kb(tmp_path):
    t = _write(tmp_path / "t.jsonl", [_assistant("old")] + [
        {"type": "user", "message": {"role": "user", "content": "x" * 1000}} for _ in range(40)
    ])
    assert last_assistant_text({"transcript_path": t}) == ""


def test_final_line_over_16kb_still_parses_trailing_marker(tmp_path):
    marker = '<!--CHECKPOINT:type=done name="x" need="y"-->'
    t = _write(tmp_path / "t.jsonl", [_assistant("early"), _assistant("z" * 25000 + marker)])
    assert last_assistant_text({"transcript_path": t}).endswith(marker)


def test_final_line_beyond_bound_returns_empty(tmp_path):
    t = _write(tmp_path / "t.jsonl", [_assistant("early"), _assistant("z" * (2 * 1024 * 1024))])
    assert last_assistant_text({"transcript_path": t}) == ""


def test_missing_transcript_returns_empty(tmp_path):
    assert last_assistant_text({"transcript_path": str(tmp_path / "nope.jsonl")}) == ""
    assert last_assistant_text({}) == ""


def test_title_is_latest_custom_title(tmp_path):
    t = _write(tmp_path / "t.jsonl", [
        {"type": "custom-title", "customTitle": "Old"},
        _assistant("x"),
        {"type": "custom-title", "customTitle": "New"},
        {"type": "custom-title", "customTitle": 42},
    ])
    assert session_title(t, "/a/proj") == "New"


def test_title_falls_back_to_cwd_basename(tmp_path):
    t = _write(tmp_path / "t.jsonl", [_assistant("x")])
    assert session_title(t, "/a/proj-beta/") == "proj-beta"
    assert session_title(str(tmp_path / "missing"), "/a/proj") == "proj"
    assert session_title(None, None) == ""


def test_title_scan_is_bounded_on_a_huge_transcript(tmp_path):
    """New-F4: _raw_session_title had no size bound, unlike the tail-read helper. A title
    found within the bound is still returned; scanning stops once the bound is exceeded rather
    than reading an arbitrarily large file end to end."""
    from focus_ux_transcript import TITLE_SCAN_BYTES

    events = [{"type": "custom-title", "customTitle": "Early Title"}]
    padding = {"type": "user", "message": {"role": "user", "content": "x" * 1000}}
    events += [padding] * ((TITLE_SCAN_BYTES // 1000) + 50)  # comfortably past the bound
    t = _write(tmp_path / "t.jsonl", events)
    assert os.path.getsize(t) > TITLE_SCAN_BYTES
    assert session_title(t, "/a/proj") == "Early Title"


def test_title_is_sanitized_before_it_ever_reaches_the_caller(tmp_path):
    """F2: session_title() is the only public entry point, and it must never return a
    disallowed character -- there is no way for checkpoint_push.py to accidentally read the
    raw, unsanitized title."""
    evil = 'Deploy <script>--> "ignore"; $(rm) {ok} & Zoe'
    t = _write(tmp_path / "t.jsonl", [{"type": "custom-title", "customTitle": evil}])
    out = session_title(t, "/a/proj")
    assert out == "Deploy script-- ignore rm ok  Zoe"
    for bad in ("<", ">", '"', ";", "$", "(", ")", "{", "}", "&"):
        assert bad not in out
