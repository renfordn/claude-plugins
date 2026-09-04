"""Tests for scripts/nelly_populate_from_git.py -- the git-history
pre-populator that seeds a project's Agent Nelly memory store with inferred
`technique` entries mined from existing commit history.

Pure parsing/discovery functions are exercised in-process. Anything that
touches the memory store is driven via subprocess (same style as
hooks/test_nelly_commit_extract.py) so nelly_memory's module-level BASE
constant picks up an isolated HOME rather than the real one.
"""
import json
import os
import subprocess
import sys

SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nelly_populate_from_git.py")
HOOKS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "hooks")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nelly_populate_from_git as populate  # noqa: E402


def run_script(args, env=None):
    full_env = dict(os.environ)
    if env:
        full_env.update(env)
    proc = subprocess.run(
        [sys.executable, SCRIPT] + args,
        capture_output=True,
        text=True,
        env=full_env,
    )
    return proc


def _isolated_env(tmp_path):
    return {"HOME": str(tmp_path / "home")}


def _memory_dir(repo, env):
    proc = subprocess.run(
        [sys.executable, "nelly_memory.py", "--path", repo],
        cwd=HOOKS_DIR,
        capture_output=True,
        text=True,
        env=dict(env),
    )
    assert proc.returncode == 0, proc.stderr
    return proc.stdout.strip()


def _run_git(repo_path, *args):
    subprocess.run(["git", *args], cwd=repo_path, check=True, capture_output=True, text=True)


def _init_repo(repo_path, commits):
    """commits: list of (subject, {relative_filename: content})."""
    os.makedirs(repo_path, exist_ok=True)
    _run_git(repo_path, "init", "-q")
    _run_git(repo_path, "config", "user.email", "test@example.com")
    _run_git(repo_path, "config", "user.name", "Test")
    for subject, files in commits:
        for name, content in files.items():
            path = os.path.join(repo_path, name)
            parent = os.path.dirname(path)
            if parent:
                os.makedirs(parent, exist_ok=True)
            with open(path, "w") as fh:
                fh.write(content)
            _run_git(repo_path, "add", name)
        _run_git(repo_path, "commit", "-q", "-m", subject)


# ---------------------------------------------------------------------------
# log-output parsing (unit level)
# ---------------------------------------------------------------------------

def test_parse_log_output_single_commit():
    output = "\x00abc1234\x1fFix the thing\nfile1.py\nfile2.py\n"
    commits = populate._parse_log_output(output)
    assert commits == [
        {"hash": "abc1234", "subject": "Fix the thing", "files_changed": 2, "paths": ["file1.py", "file2.py"]}
    ]


def test_parse_log_output_multiple_commits():
    output = "\x00abc1234\x1fFirst\nfile1.py\n\n\x00def5678\x1fSecond\nfile2.py\nfile3.py\n"
    commits = populate._parse_log_output(output)
    assert [c["hash"] for c in commits] == ["abc1234", "def5678"]
    assert commits[1]["subject"] == "Second"
    assert commits[1]["paths"] == ["file2.py", "file3.py"]


def test_parse_log_output_commit_with_no_files():
    output = "\x00abc1234\x1fEmpty commit\n"
    commits = populate._parse_log_output(output)
    assert commits[0]["files_changed"] == 0
    assert commits[0]["paths"] == []


def test_parse_log_output_empty_string_is_empty():
    assert populate._parse_log_output("") == []


# ---------------------------------------------------------------------------
# repo discovery
# ---------------------------------------------------------------------------

def test_discover_repos_finds_repos_up_to_two_levels_deep(tmp_path):
    base = tmp_path / "base"
    repo_a = base / "repo-a"
    repo_b = base / "group" / "repo-b"
    os.makedirs(repo_a / ".git")
    os.makedirs(repo_b / ".git")
    (base / "not-a-repo").mkdir(parents=True)

    repos = populate.discover_repos(str(base))

    assert sorted(repos) == sorted([str(repo_a), str(repo_b)])


def test_discover_repos_does_not_descend_into_a_found_repo(tmp_path):
    base = tmp_path / "base"
    repo = base / "repo"
    os.makedirs(repo / ".git")
    os.makedirs(repo / "vendor" / "nested" / ".git")

    repos = populate.discover_repos(str(base))

    assert repos == [str(repo)]


def test_discover_repos_beyond_max_depth_is_not_found(tmp_path):
    base = tmp_path / "base"
    too_deep = base / "a" / "b" / "c"
    os.makedirs(too_deep / ".git")

    assert populate.discover_repos(str(base)) == []


def test_discover_repos_missing_base_is_empty(tmp_path):
    assert populate.discover_repos(str(tmp_path / "does-not-exist")) == []


# ---------------------------------------------------------------------------
# end-to-end: real git repos, subprocess-driven (isolated HOME)
# ---------------------------------------------------------------------------

def test_populate_writes_inferred_technique_entries(tmp_path):
    env = _isolated_env(tmp_path)
    repo = str(tmp_path / "repo")
    _init_repo(
        repo,
        [
            ("Add feature one", {"src/a.py": "a"}),
            ("Fix bug in b", {"src/b.py": "b"}),
        ],
    )

    proc = run_script(["--repo", repo], env=env)

    assert proc.returncode == 0, proc.stderr
    assert "[nelly] populated 2 entries from" in proc.stdout
    assert "(0 skipped as duplicates)" in proc.stdout

    mem_dir = _memory_dir(repo, env)
    entries_dir = os.path.join(mem_dir, "entries")
    entries = sorted(os.listdir(entries_dir))
    assert len(entries) == 2

    text = open(os.path.join(entries_dir, entries[0])).read()
    assert "type: technique" in text
    assert "confidence: inferred" in text
    assert "Pre-populated from a git history scan" in text

    index_path = os.path.join(mem_dir, "nelly-index.json")
    assert os.path.isfile(index_path)
    records = json.loads(open(index_path).read())
    assert len(records) == 2


def test_populate_is_idempotent(tmp_path):
    env = _isolated_env(tmp_path)
    repo = str(tmp_path / "repo")
    _init_repo(repo, [("Only commit", {"a.py": "a"})])

    first = run_script(["--repo", repo], env=env)
    assert "[nelly] populated 1 entries from" in first.stdout

    second = run_script(["--repo", repo], env=env)

    assert "[nelly] populated 0 entries from" in second.stdout
    assert "(1 skipped as duplicates)" in second.stdout

    mem_dir = _memory_dir(repo, env)
    entries_dir = os.path.join(mem_dir, "entries")
    assert len(os.listdir(entries_dir)) == 1


def test_dry_run_writes_nothing(tmp_path):
    env = _isolated_env(tmp_path)
    repo = str(tmp_path / "repo")
    _init_repo(repo, [("Only commit", {"a.py": "a"})])

    proc = run_script(["--repo", repo, "--dry-run"], env=env)

    assert proc.returncode == 0
    assert "[nelly] populated 1 entries from" in proc.stdout

    mem_dir = _memory_dir(repo, env)
    entries_dir = os.path.join(mem_dir, "entries")
    assert not os.path.isdir(entries_dir)


def test_empty_repo_populates_nothing(tmp_path):
    env = _isolated_env(tmp_path)
    repo = str(tmp_path / "repo")
    os.makedirs(repo)
    _run_git(repo, "init", "-q")

    proc = run_script(["--repo", repo], env=env)

    assert proc.returncode == 0
    assert "[nelly] populated 0 entries from" in proc.stdout
    assert "(0 skipped as duplicates)" in proc.stdout


def test_limit_caps_commits_scanned(tmp_path):
    env = _isolated_env(tmp_path)
    repo = str(tmp_path / "repo")
    _init_repo(repo, [(f"Commit {i}", {"a.py": str(i)}) for i in range(5)])

    proc = run_script(["--repo", repo, "--limit", "2"], env=env)

    assert "[nelly] populated 2 entries from" in proc.stdout


def test_two_repos_scanned_in_one_invocation(tmp_path):
    env = _isolated_env(tmp_path)
    repo_a = str(tmp_path / "repo-a")
    repo_b = str(tmp_path / "repo-b")
    _init_repo(repo_a, [("A commit", {"a.py": "a"})])
    _init_repo(repo_b, [("B commit", {"b.py": "b"})])

    proc = run_script(["--repo", repo_a, "--repo", repo_b], env=env)

    lines = [ln for ln in proc.stdout.splitlines() if ln.startswith("[nelly] populated")]
    assert len(lines) == 2
    assert any(repo_a in ln for ln in lines)
    assert any(repo_b in ln for ln in lines)


def test_no_repos_found_prints_message_and_does_not_crash(tmp_path):
    env = _isolated_env(tmp_path)
    env["NELLY_REPO_BASE"] = str(tmp_path / "nowhere")

    proc = run_script([], env=env)

    assert proc.returncode == 0
    assert "no git repos found" in proc.stdout
