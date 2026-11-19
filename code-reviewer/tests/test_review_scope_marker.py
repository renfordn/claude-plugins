"""Test: the reviewer echoes the scope it was given so callers can scope review gates per slice."""

import os
import subprocess
from pathlib import Path

_PLUGIN = Path(__file__).resolve().parent.parent
_AGENT = (_PLUGIN / "agents" / "code-reviewer.md").read_text()
_SCRIPT = _PLUGIN / "scripts" / "review_headless.sh"


def _headless_prompt(tmp_path, args, env=None, expect_rc=None):
    fake = tmp_path / "claude"
    fake.write_text('#!/usr/bin/env bash\nprintf "%s\\nPWD=%s" "$2" "$PWD"\n')
    fake.chmod(0o755)
    e = {**os.environ, "PATH": f"{tmp_path}:{os.environ['PATH']}"}
    e.pop("REVIEW_SCOPE", None)
    e.pop("REVIEW_CWD", None)
    e.update(env or {})
    out = subprocess.run(["bash", str(_SCRIPT), *args], capture_output=True, text=True, env=e)
    if expect_rc is not None:
        assert out.returncode == expect_rc, out.stderr
        return out
    assert out.returncode == 0, out.stderr
    return out.stdout


def test_agent_documents_scope_marker_and_cwd_rule():
    assert "Review scope: slice=" in _AGENT
    marker = _AGENT.index("<!--REVIEW-SCOPE: slice=")
    report = _AGENT.index("<!--CODE-REVIEWER-REPORT-->", _AGENT.index("## Return this report"))
    assert marker < report
    assert "Review cwd:" in _AGENT


def test_headless_flag_and_env_add_scope_instruction(tmp_path):
    via_flag = _headless_prompt(tmp_path, ["--scope", "0a", "brief"])
    via_env = _headless_prompt(tmp_path, ["brief"], {"REVIEW_SCOPE": "3"})
    assert "<!--REVIEW-SCOPE: slice=0a-->" in via_flag
    assert "<!--REVIEW-SCOPE: slice=3-->" in via_env


def test_headless_without_scope_adds_no_scope_instruction(tmp_path):
    prompt = _headless_prompt(tmp_path, ["brief"])
    assert "<!--REVIEW-SCOPE: slice=" not in prompt.split("Headless run:")[1]


def test_headless_cwd_flag_adds_review_cwd(tmp_path):
    prompt = _headless_prompt(tmp_path, ["--cwd", str(tmp_path), "brief"])
    assert f"Review cwd: {tmp_path}" in prompt.split("Headless run:")[1]


def test_headless_cwd_env_and_chdir(tmp_path):
    wt = tmp_path / "wt"
    wt.mkdir()
    prompt = _headless_prompt(tmp_path, ["brief"], {"REVIEW_CWD": str(wt)})
    assert f"Review cwd: {wt}" in prompt
    assert f"PWD={wt.resolve()}" in prompt or f"PWD={wt}" in prompt


def test_headless_cwd_must_be_directory(tmp_path):
    _headless_prompt(tmp_path, ["--cwd", str(tmp_path / "nope"), "brief"], expect_rc=2)


def test_headless_flags_any_order(tmp_path):
    wt = tmp_path / "wt"
    wt.mkdir()
    for args in (["--scope", "1", "--cwd", str(wt), "b"], ["--cwd", str(wt), "--scope", "1", "b"]):
        prompt = _headless_prompt(tmp_path, args)
        assert "<!--REVIEW-SCOPE: slice=1-->" in prompt and f"Review cwd: {wt}" in prompt


def test_headless_scope_with_agent_flag_after(tmp_path):
    prompt = _headless_prompt(tmp_path, ["--scope", "1", "--agent", "finding-verifier", "b"])
    assert "<!--REVIEW-SCOPE: slice=1-->" not in prompt.split("Headless run:")[1]


def test_headless_rejects_bad_scope_and_unknown_flag(tmp_path):
    _headless_prompt(tmp_path, ["--scope", "x y", "b"], expect_rc=2)
    _headless_prompt(tmp_path, ["--scope", "1;rm", "b"], expect_rc=2)
    _headless_prompt(tmp_path, ["--bogus", "b"], expect_rc=2)
