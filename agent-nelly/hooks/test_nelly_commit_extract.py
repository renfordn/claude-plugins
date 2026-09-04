"""Tests for hooks/nelly_commit_extract.py -- PostToolUse hook that
auto-writes draft `inferred`-confidence `technique` entries from `git
commit` success signatures in Bash output.

Drives the hook exactly as the harness does: pipe a JSON payload on stdin to
the script via subprocess, and assert on stdout + the resulting memory
store, same style as test_nelly_auto_extract.py.
"""
import json
import os
import subprocess
import sys

HOOK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nelly_commit_extract.py")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nelly_commit_extract as commit_extract  # noqa: E402
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


def _bash_payload(cwd, command="git commit -m 'x'", stdout="", stderr=""):
    return {
        "tool_name": "Bash",
        "tool_input": {"command": command},
        "tool_response": {"stdout": stdout, "stderr": stderr},
        "cwd": cwd,
    }


SINGLE_FILE_COMMIT_OUTPUT = """\
[main abc1234] Fix the thing
 1 file changed, 3 insertions(+), 1 deletion(-)
"""

MULTI_FILE_COMMIT_OUTPUT = """\
[feature-branch 9f8e7d6] Add new feature
 3 files changed, 45 insertions(+), 2 deletions(-)
 create mode 100644 hooks/foo.py
 create mode 100644 scripts/bar.py
 delete mode 100644 old/baz.py
"""

ROOT_COMMIT_OUTPUT = """\
[main (root-commit) 1a2b3c4] Initial commit
 5 files changed, 100 insertions(+)
"""

NOTHING_TO_COMMIT_OUTPUT = """\
On branch main
nothing to commit, working tree clean
"""

STATUS_OUTPUT = """\
On branch main
Changes not staged for commit:
  modified:   hooks/foo.py
"""


# ---------------------------------------------------------------------------
# signal detection (unit-level, via detect_commits directly)
# ---------------------------------------------------------------------------

def test_detect_single_file_commit():
    commits = commit_extract.detect_commits(SINGLE_FILE_COMMIT_OUTPUT)
    assert len(commits) == 1
    c = commits[0]
    assert c["hash"] == "abc1234"
    assert c["subject"] == "Fix the thing"
    assert c["files_changed"] == 1
    assert c["paths"] == []


def test_detect_multi_file_commit_with_paths():
    commits = commit_extract.detect_commits(MULTI_FILE_COMMIT_OUTPUT)
    assert len(commits) == 1
    c = commits[0]
    assert c["hash"] == "9f8e7d6"
    assert c["files_changed"] == 3
    assert c["paths"] == ["hooks/foo.py", "scripts/bar.py", "old/baz.py"]


def test_detect_root_commit():
    commits = commit_extract.detect_commits(ROOT_COMMIT_OUTPUT)
    assert len(commits) == 1
    assert commits[0]["hash"] == "1a2b3c4"
    assert commits[0]["subject"] == "Initial commit"


def test_detect_nothing_to_commit_is_empty():
    assert commit_extract.detect_commits(NOTHING_TO_COMMIT_OUTPUT) == []


def test_detect_git_status_is_empty():
    # `git status` output must never be mistaken for a commit success.
    assert commit_extract.detect_commits(STATUS_OUTPUT) == []


def test_detect_empty_output_is_empty():
    assert commit_extract.detect_commits("") == []


def test_tags_derived_from_top_level_dirs():
    tags = commit_extract._tags_for_paths(["hooks/foo.py", "scripts/bar.py", "hooks/baz.py", "README.md"])
    assert tags == ["hooks", "scripts"]


def test_slug_generation():
    assert commit_extract._make_slug("abc1234") == "git-pattern-abc1234"
    assert commit_extract._make_slug("0123456789abcdef") == "git-pattern-0123456789ab"


# ---------------------------------------------------------------------------
# end-to-end hook behavior
# ---------------------------------------------------------------------------

def test_commit_writes_inferred_technique_entry(tmp_path):
    env = _isolated_env(tmp_path)
    cwd = str(tmp_path / "project")
    payload = _bash_payload(cwd, stdout=MULTI_FILE_COMMIT_OUTPUT)

    proc = run_hook(payload, env=env)

    assert proc.returncode == 0
    assert proc.stdout.strip() == "[nelly] commit pattern saved: git-pattern-9f8e7d6"

    mem_dir = _memory_dir(cwd, env)
    entries_dir = os.path.join(mem_dir, "entries")
    entries = os.listdir(entries_dir)
    assert entries == ["git-pattern-9f8e7d6.md"]

    text = open(os.path.join(entries_dir, entries[0])).read()
    assert "type: technique" in text
    assert "confidence: inferred" in text
    assert "commit: 9f8e7d6" in text
    assert "files_changed: 3" in text
    assert "description: Add new feature" in text
    assert "tags: [hooks, old, scripts]" in text


def test_no_commit_is_silent_no_op(tmp_path):
    env = _isolated_env(tmp_path)
    cwd = str(tmp_path / "project")
    payload = _bash_payload(cwd, command="git status", stdout=NOTHING_TO_COMMIT_OUTPUT)

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
        "tool_response": {"stdout": SINGLE_FILE_COMMIT_OUTPUT},
        "cwd": cwd,
    }

    proc = run_hook(payload, env=env)

    assert proc.returncode == 0
    assert proc.stdout.strip() == ""


def test_duplicate_commit_hash_is_not_written_twice(tmp_path):
    env = _isolated_env(tmp_path)
    cwd = str(tmp_path / "project")
    payload = _bash_payload(cwd, stdout=SINGLE_FILE_COMMIT_OUTPUT)

    first = run_hook(payload, env=env)
    assert first.stdout.startswith("[nelly] commit pattern saved:")

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
    payload = _bash_payload(cwd, stdout=SINGLE_FILE_COMMIT_OUTPUT)

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
    payload = _bash_payload(cwd, stdout=SINGLE_FILE_COMMIT_OUTPUT)

    run_hook(payload, env=env)

    mem_dir = _memory_dir(cwd, env)
    entries_dir = os.path.join(mem_dir, "entries")
    text = open(os.path.join(entries_dir, os.listdir(entries_dir)[0])).read()
    assert "seen_count: 1" in text


def test_repeated_commit_hash_auto_promotes_at_threshold(tmp_path):
    # Same hash re-detected (e.g. the same `[branch hash] subject` line
    # appearing again in a later Bash call) is the only way this hook's
    # hash-keyed slug can ever see a dedup hit.
    env = _isolated_env(tmp_path)
    cwd = str(tmp_path / "project")
    payload = _bash_payload(cwd, stdout=SINGLE_FILE_COMMIT_OUTPUT)

    procs = [run_hook(payload, env=env) for _ in range(auto_extract.PROMOTION_THRESHOLD)]

    last = procs[-1]
    assert last.stdout.strip() == "[nelly] promoted to explicit: git-pattern-abc1234 (seen 3x)"

    mem_dir = _memory_dir(cwd, env)
    entries_dir = os.path.join(mem_dir, "entries")
    entries = os.listdir(entries_dir)
    assert entries == ["git-pattern-abc1234.md"]
    text = open(os.path.join(entries_dir, entries[0])).read()
    assert f"seen_count: {auto_extract.PROMOTION_THRESHOLD}" in text
    assert "confidence: explicit" in text
    assert "confidence: inferred" not in text

    log_path = os.path.join(mem_dir, "CONSOLIDATION-LOG.md")
    assert os.path.isfile(log_path)
    assert "Action: promoted" in open(log_path).read()


def test_repeated_commit_hash_below_threshold_does_not_promote(tmp_path):
    env = _isolated_env(tmp_path)
    cwd = str(tmp_path / "project")
    payload = _bash_payload(cwd, stdout=SINGLE_FILE_COMMIT_OUTPUT)

    for _ in range(auto_extract.PROMOTION_THRESHOLD - 1):
        run_hook(payload, env=env)

    mem_dir = _memory_dir(cwd, env)
    entries_dir = os.path.join(mem_dir, "entries")
    text = open(os.path.join(entries_dir, os.listdir(entries_dir)[0])).read()
    assert "confidence: inferred" in text
    assert not os.path.isfile(os.path.join(mem_dir, "CONSOLIDATION-LOG.md"))


def test_two_commits_in_one_bash_call_both_written(tmp_path):
    env = _isolated_env(tmp_path)
    cwd = str(tmp_path / "project")
    combined = SINGLE_FILE_COMMIT_OUTPUT + MULTI_FILE_COMMIT_OUTPUT
    payload = _bash_payload(cwd, command="git commit -m a && git commit -m b", stdout=combined)

    proc = run_hook(payload, env=env)

    assert proc.returncode == 0
    lines = proc.stdout.strip().splitlines()
    assert lines == [
        "[nelly] commit pattern saved: git-pattern-abc1234",
        "[nelly] commit pattern saved: git-pattern-9f8e7d6",
    ]

    mem_dir = _memory_dir(cwd, env)
    entries_dir = os.path.join(mem_dir, "entries")
    assert len(os.listdir(entries_dir)) == 2
