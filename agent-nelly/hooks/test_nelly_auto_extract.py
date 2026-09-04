"""Tests for hooks/nelly_auto_extract.py -- PostToolUse hook that auto-writes
draft `inferred`-confidence error-prevention entries from Bash test/error
output.

Drives the hook exactly as the harness does: pipe a JSON payload on stdin to
the script via subprocess, and assert on stdout + the resulting memory
store, same style as test_nelly_index_update.py and
test_nelly_proactive_surface.py.
"""
import json
import os
import re
import subprocess
import sys

import pytest

HOOK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nelly_auto_extract.py")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nelly_auto_extract as auto_extract  # noqa: E402


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
    state_dir = tmp_path / "session-state"
    state_dir.mkdir(exist_ok=True)
    return {
        "HOME": str(tmp_path / "home"),
        "NELLY_SESSION_STATE_DIR": str(state_dir),
    }


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


def _bash_payload(cwd, command="pytest", stdout="", stderr=""):
    return {
        "tool_name": "Bash",
        "tool_input": {"command": command},
        "tool_response": {"stdout": stdout, "stderr": stderr},
        "cwd": cwd,
    }


PYTEST_FAILURE_OUTPUT = """\
============================= FAILURES =============================
_________________________ test_foo _________________________

    def test_foo():
>       assert 1 == 2
E       assert 1 == 2

test_foo.py:5: AssertionError
=========================== short test summary info ===========================
FAILED test_foo.py::test_foo - assert 1 == 2
1 failed, 2 passed in 0.05s
"""

JEST_FAILURE_OUTPUT = """\
FAIL src/foo.test.js
  ✕ does the thing (5 ms)

  ● does the thing

    expect(received).toBe(expected)

    Expected: 2
    Received: 1
"""

PYTHON_TRACEBACK_OUTPUT = """\
Traceback (most recent call last):
  File "app.py", line 3, in <module>
    raise KeyError("config")
KeyError: 'config'
"""

CLEAN_PYTEST_OUTPUT = """\
collected 3 items

test_foo.py ...

3 passed in 0.02s
"""

JEST_PASSED_OUTPUT = """\
PASS src/foo.test.js

Tests:       5 passed, 5 total
"""

MOCHA_PASSING_OUTPUT = """\
  Suite
    ✓ does the thing

  5 passing (12ms)
"""


# ---------------------------------------------------------------------------
# signal detection (unit-level, via detect_signal directly)
# ---------------------------------------------------------------------------

def test_detect_signal_pytest_failure():
    result = auto_extract.detect_signal(PYTEST_FAILURE_OUTPUT, "")
    assert result is not None
    kind, basis, description = result
    assert kind == "pytest-failure"
    assert "test_foo.py::test_foo" in basis


def test_detect_signal_jest_failure():
    result = auto_extract.detect_signal(JEST_FAILURE_OUTPUT, "")
    assert result is not None
    assert result[0] == "test-failure"


def test_detect_signal_python_traceback():
    result = auto_extract.detect_signal("", PYTHON_TRACEBACK_OUTPUT)
    assert result is not None
    kind, basis, description = result
    assert kind == "exception"
    assert "KeyError" in basis


def test_detect_signal_clean_run_is_none():
    assert auto_extract.detect_signal(CLEAN_PYTEST_OUTPUT, "") is None


def test_detect_signal_empty_output_is_none():
    assert auto_extract.detect_signal("", "") is None


def test_detect_signal_generic_stderr_error():
    result = auto_extract.detect_signal("", "bash: fatal: something broke badly\n")
    assert result is not None
    assert result[0] == "command-error"


def test_detect_signal_plain_warning_is_none():
    # No recognized failure keyword/pattern -- must stay a no-op.
    assert auto_extract.detect_signal("all good, proceeding\n", "") is None


# ---------------------------------------------------------------------------
# end-to-end hook behavior
# ---------------------------------------------------------------------------

def test_pytest_failure_writes_inferred_entry(tmp_path):
    env = _isolated_env(tmp_path)
    cwd = str(tmp_path / "project")
    payload = _bash_payload(cwd, command="pytest", stdout=PYTEST_FAILURE_OUTPUT)

    proc = run_hook(payload, env=env)

    assert proc.returncode == 0
    assert proc.stdout.startswith("[nelly] inferred lesson saved: auto-")

    mem_dir = _memory_dir(cwd, env)
    entries_dir = os.path.join(mem_dir, "entries")
    entries = os.listdir(entries_dir)
    assert len(entries) == 1

    text = open(os.path.join(entries_dir, entries[0])).read()
    assert "type: error-prevention" in text
    assert "confidence: inferred" in text


def test_clean_run_is_silent_no_op(tmp_path):
    env = _isolated_env(tmp_path)
    cwd = str(tmp_path / "project")
    payload = _bash_payload(cwd, command="pytest", stdout=CLEAN_PYTEST_OUTPUT)

    proc = run_hook(payload, env=env)

    assert proc.returncode == 0
    assert proc.stdout.strip() == ""
    mem_dir = _memory_dir(cwd, env)
    assert not os.path.isdir(os.path.join(mem_dir, "entries"))


def test_non_bash_tool_is_ignored(tmp_path):
    env = _isolated_env(tmp_path)
    cwd = str(tmp_path / "project")
    payload = {
        "tool_name": "Write",
        "tool_input": {"file_path": "x.py"},
        "tool_response": {"stdout": PYTEST_FAILURE_OUTPUT},
        "cwd": cwd,
    }

    proc = run_hook(payload, env=env)

    assert proc.returncode == 0
    assert proc.stdout.strip() == ""


def test_duplicate_signal_is_not_written_twice(tmp_path):
    env = _isolated_env(tmp_path)
    cwd = str(tmp_path / "project")
    payload = _bash_payload(cwd, command="pytest", stdout=PYTEST_FAILURE_OUTPUT)

    first = run_hook(payload, env=env)
    assert first.stdout.startswith("[nelly] inferred lesson saved:")

    second = run_hook(payload, env=env)

    assert second.returncode == 0
    assert second.stdout.strip() == ""  # already recorded -- no duplicate write

    mem_dir = _memory_dir(cwd, env)
    entries_dir = os.path.join(mem_dir, "entries")
    assert len(os.listdir(entries_dir)) == 1


def test_gate_off_disables_hook(tmp_path):
    env = _isolated_env(tmp_path)
    env["NELLY_GATE"] = "off"
    cwd = str(tmp_path / "project")
    payload = _bash_payload(cwd, command="pytest", stdout=PYTEST_FAILURE_OUTPUT)

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


# ---------------------------------------------------------------------------
# auto-confirmation of recurring inferred entries (seen_count / promotion)
# ---------------------------------------------------------------------------

def test_new_entry_starts_with_seen_count_one(tmp_path):
    env = _isolated_env(tmp_path)
    cwd = str(tmp_path / "project")
    payload = _bash_payload(cwd, command="pytest", stdout=PYTEST_FAILURE_OUTPUT)

    run_hook(payload, env=env)

    mem_dir = _memory_dir(cwd, env)
    entries_dir = os.path.join(mem_dir, "entries")
    text = open(os.path.join(entries_dir, os.listdir(entries_dir)[0])).read()
    assert "seen_count: 1" in text


def test_dedup_hit_increments_seen_count(tmp_path):
    env = _isolated_env(tmp_path)
    cwd = str(tmp_path / "project")
    payload = _bash_payload(cwd, command="pytest", stdout=PYTEST_FAILURE_OUTPUT)

    run_hook(payload, env=env)  # seen_count: 1 (write)
    second = run_hook(payload, env=env)  # dedup hit -> seen_count: 2

    assert second.returncode == 0
    assert second.stdout.strip() == ""  # below threshold -- still silent

    mem_dir = _memory_dir(cwd, env)
    entries_dir = os.path.join(mem_dir, "entries")
    entries = os.listdir(entries_dir)
    assert len(entries) == 1
    text = open(os.path.join(entries_dir, entries[0])).read()
    assert "seen_count: 2" in text
    assert "confidence: inferred" in text


def test_dedup_hit_below_threshold_does_not_promote(tmp_path):
    env = _isolated_env(tmp_path)
    cwd = str(tmp_path / "project")
    payload = _bash_payload(cwd, command="pytest", stdout=PYTEST_FAILURE_OUTPUT)

    for _ in range(auto_extract.PROMOTION_THRESHOLD - 1):
        run_hook(payload, env=env)

    mem_dir = _memory_dir(cwd, env)
    entries_dir = os.path.join(mem_dir, "entries")
    text = open(os.path.join(entries_dir, os.listdir(entries_dir)[0])).read()
    assert "confidence: inferred" in text
    assert "confidence: explicit" not in text
    assert not os.path.isfile(os.path.join(mem_dir, "CONSOLIDATION-LOG.md"))


def test_dedup_hit_auto_promotes_at_threshold(tmp_path):
    env = _isolated_env(tmp_path)
    cwd = str(tmp_path / "project")
    payload = _bash_payload(cwd, command="pytest", stdout=PYTEST_FAILURE_OUTPUT)

    procs = [run_hook(payload, env=env) for _ in range(auto_extract.PROMOTION_THRESHOLD)]

    last = procs[-1]
    assert last.stdout.strip().startswith("[nelly] promoted to explicit:")

    mem_dir = _memory_dir(cwd, env)
    entries_dir = os.path.join(mem_dir, "entries")
    entries = os.listdir(entries_dir)
    assert len(entries) == 1
    text = open(os.path.join(entries_dir, entries[0])).read()
    assert f"seen_count: {auto_extract.PROMOTION_THRESHOLD}" in text
    assert "confidence: explicit" in text
    assert "confidence: inferred" not in text

    log_path = os.path.join(mem_dir, "CONSOLIDATION-LOG.md")
    assert os.path.isfile(log_path)
    log_text = open(log_path).read()
    assert "Action: promoted" in log_text
    assert entries[0][:-3] in log_text


def test_explicit_entry_is_never_re_promoted(tmp_path, monkeypatch):
    cwd = str(tmp_path / "project")
    monkeypatch.setattr(auto_extract.nelly_memory, "BASE", str(tmp_path / "agent-nelly-memory"))

    slug = auto_extract._make_slug("test_foo.py::test_foo")
    auto_extract.nelly_memory.ensure_entries_dir(cwd)
    entry_path = auto_extract.nelly_memory.entry_path(cwd, slug)
    with open(entry_path, "w", encoding="utf-8") as fh:
        fh.write(
            "---\nname: {0}\ndescription: x\nmetadata:\n  type: error-prevention\n"
            "  confidence: explicit\n  seen_count: 5\n---\n\nBody.\n".format(slug)
        )

    result = auto_extract._bump_seen_count_and_maybe_promote(cwd, slug)

    assert result == (6, False)
    text = open(entry_path).read()
    assert "confidence: explicit" in text
    assert "seen_count: 6" in text
    log_path = os.path.join(auto_extract.nelly_memory.memory_dir(cwd), "CONSOLIDATION-LOG.md")
    assert not os.path.isfile(log_path)


def test_bump_seen_count_missing_entry_file_returns_none(tmp_path, monkeypatch):
    cwd = str(tmp_path / "project")
    monkeypatch.setattr(auto_extract.nelly_memory, "BASE", str(tmp_path / "agent-nelly-memory"))

    assert auto_extract._bump_seen_count_and_maybe_promote(cwd, "does-not-exist") is None


def test_recovery_signal_pytest_passed():
    result = auto_extract.detect_recovery_signal(CLEAN_PYTEST_OUTPUT, "")
    assert result == ("pytest", 3)


def test_recovery_signal_jest_passed():
    result = auto_extract.detect_recovery_signal(JEST_PASSED_OUTPUT, "")
    assert result == ("jest", 5)


def test_recovery_signal_mocha_passing():
    result = auto_extract.detect_recovery_signal(MOCHA_PASSING_OUTPUT, "")
    assert result == ("mocha", 5)


def test_recovery_signal_mixed_result_is_none():
    # "1 failed, 2 passed" must never read as a clean recovery.
    assert auto_extract.detect_recovery_signal(PYTEST_FAILURE_OUTPUT, "") is None


def test_recovery_signal_empty_output_is_none():
    assert auto_extract.detect_recovery_signal("", "") is None


def test_tags_from_test_paths_uses_directory():
    tags = auto_extract._tags_from_test_paths("pytest tests/test_foo.py", "")
    assert tags == ["tests"]


def test_tags_from_test_paths_falls_back_to_filename():
    tags = auto_extract._tags_from_test_paths("pytest test_foo.py", "")
    assert tags == ["test_foo.py"]


def test_make_recovery_slug_matches_expected_format():
    slug = auto_extract._make_recovery_slug()
    assert re.match(r"^test-recovery-\d{4}-\d{2}-\d{2}-\d{4}$", slug)


def test_unreadable_index_falls_back_to_entries_scan(tmp_path, monkeypatch):
    """A corrupt/unreadable nelly-index.json must not crash the duplicate
    check -- it should fall back to scanning entries/*.md directly.
    """
    cwd = str(tmp_path / "project")
    monkeypatch.setattr(auto_extract.nelly_memory, "BASE", str(tmp_path / "agent-nelly-memory"))

    slug = auto_extract._make_slug("test_foo.py::test_foo")
    auto_extract.nelly_memory.ensure_entries_dir(cwd)
    entry_path = auto_extract.nelly_memory.entry_path(cwd, slug)
    with open(entry_path, "w", encoding="utf-8") as fh:
        fh.write(
            "---\nname: {0}\ndescription: x\nmetadata:\n  type: error-prevention\n"
            "  confidence: inferred\n---\n\nBody.\n".format(slug)
        )

    mem_dir = auto_extract.nelly_memory.memory_dir(cwd)
    index_path = os.path.join(mem_dir, "nelly-index.json")
    with open(index_path, "w", encoding="utf-8") as fh:
        fh.write("{ not valid json")

    assert auto_extract._entry_exists(cwd, slug) is True


# ---------------------------------------------------------------------------
# positive-pattern capture (test-suite recovery, end-to-end via subprocess)
# ---------------------------------------------------------------------------

def test_recovery_writes_technique_entry_after_prior_failure(tmp_path):
    env = _isolated_env(tmp_path)
    cwd = str(tmp_path / "project")

    fail = run_hook(_bash_payload(cwd, command="pytest", stdout=PYTEST_FAILURE_OUTPUT), env=env)
    assert fail.stdout.startswith("[nelly] inferred lesson saved:")

    recover = run_hook(
        _bash_payload(cwd, command="pytest tests/test_foo.py", stdout=CLEAN_PYTEST_OUTPUT), env=env
    )

    assert recover.returncode == 0
    assert recover.stdout.startswith("[nelly] technique saved: test-recovery-")
    assert "test suite recovered" in recover.stdout

    mem_dir = _memory_dir(cwd, env)
    entries_dir = os.path.join(mem_dir, "entries")
    entries = os.listdir(entries_dir)
    assert len(entries) == 2

    recovery_file = next(n for n in entries if n.startswith("test-recovery-"))
    text = open(os.path.join(entries_dir, recovery_file)).read()
    assert "type: technique" in text
    assert "confidence: inferred" in text
    assert "3 passing" in text
    assert "family: pytest" in text
    tags_line = next(ln for ln in text.splitlines() if ln.startswith("tags:"))
    assert "tests" in tags_line


def test_recovery_without_prior_failure_is_silent(tmp_path):
    env = _isolated_env(tmp_path)
    cwd = str(tmp_path / "project")

    proc = run_hook(_bash_payload(cwd, command="pytest", stdout=CLEAN_PYTEST_OUTPUT), env=env)

    assert proc.returncode == 0
    assert proc.stdout.strip() == ""
    mem_dir = _memory_dir(cwd, env)
    assert not os.path.isdir(os.path.join(mem_dir, "entries"))


def test_recovery_clears_session_state_so_it_fires_once(tmp_path):
    env = _isolated_env(tmp_path)
    cwd = str(tmp_path / "project")

    run_hook(_bash_payload(cwd, command="pytest", stdout=PYTEST_FAILURE_OUTPUT), env=env)
    first_recovery = run_hook(_bash_payload(cwd, command="pytest", stdout=CLEAN_PYTEST_OUTPUT), env=env)
    assert first_recovery.stdout.startswith("[nelly] technique saved:")

    second_recovery = run_hook(_bash_payload(cwd, command="pytest", stdout=CLEAN_PYTEST_OUTPUT), env=env)

    assert second_recovery.returncode == 0
    assert second_recovery.stdout.strip() == ""  # flag already cleared -- no re-fire

    mem_dir = _memory_dir(cwd, env)
    entries_dir = os.path.join(mem_dir, "entries")
    assert len(os.listdir(entries_dir)) == 2  # unchanged since the recovery write


def test_unrelated_clean_command_between_failure_and_recovery_stays_silent(tmp_path):
    env = _isolated_env(tmp_path)
    cwd = str(tmp_path / "project")

    run_hook(_bash_payload(cwd, command="pytest", stdout=PYTEST_FAILURE_OUTPUT), env=env)
    ls_proc = run_hook(_bash_payload(cwd, command="ls", stdout="README.md\n"), env=env)

    assert ls_proc.returncode == 0
    assert ls_proc.stdout.strip() == ""

    # the failure flag must still be set -- a later green run still recovers
    recover = run_hook(_bash_payload(cwd, command="pytest", stdout=CLEAN_PYTEST_OUTPUT), env=env)
    assert recover.stdout.startswith("[nelly] technique saved:")
