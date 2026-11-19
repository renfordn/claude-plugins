"""R9 red_first_guard: PreToolUse hook denying production edits for an open slice until Red,
coverage or a bypass is logged. Runs the hook as a subprocess inside temp git repos; evidence is
written through the tdd_check CLI."""
import datetime
import json
import os
import shlex
import subprocess
import sys
import time

import pytest

PLUGIN = os.path.realpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
HOOK = os.path.join(PLUGIN, "hooks", "red_first_guard.py")
CHECK = os.path.join(PLUGIN, "scripts", "tdd_check.py")
TITLE = "Slice X: guard me"
FAIL = [sys.executable, "-c", "raise SystemExit(1)"]
PASS = [sys.executable, "-c", "pass"]


def _env():
    return {k: v for k, v in os.environ.items() if k not in ("GIT_DIR", "GIT_WORK_TREE")}


def _git(cwd, *args):
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd=cwd, check=True,
                   capture_output=True, env=_env())


@pytest.fixture
def repo(tmp_path):
    root = os.path.realpath(tmp_path / "repo")
    os.makedirs(root)
    _git(root, "init", "-q")
    _git(root, "commit", "-q", "--allow-empty", "-m", "init")
    return root


def check(cwd, *args):
    return subprocess.run([sys.executable, CHECK, *args], cwd=cwd, capture_output=True, text=True,
                          env=_env())


def start(cwd, title=TITLE):
    assert check(cwd, "start", "--slice", title).returncode == 0


def red(cwd, title=TITLE, ok=True):
    r = check(cwd, "red", "--slice", title, "--", *(FAIL if ok else PASS))
    assert (r.returncode == 0) == ok, r.stdout + r.stderr


def run_hook(payload, cwd=None, raw=None):
    stdin = raw if raw is not None else json.dumps(payload)
    return subprocess.run([sys.executable, HOOK], input=stdin, capture_output=True, text=True,
                          cwd=cwd, env=_env(), timeout=20)


def edit(path, cwd, tool="Edit", key="file_path"):
    return run_hook({"tool_name": tool, "tool_input": {key: path}, "cwd": cwd}, cwd=cwd)


def log_path(repo):
    common = subprocess.run(["git", "rev-parse", "--git-common-dir"], cwd=repo, capture_output=True,
                            text=True, env=_env()).stdout.strip()
    return os.path.join(repo, common, "agent-tdd", "evidence.jsonl")


def assert_allowed(r):
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == ""


def assert_denied(r):
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip(), "expected a deny JSON on stdout, got nothing (stderr: %r)" % r.stderr
    out = json.loads(r.stdout)
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
    return out["hookSpecificOutput"]


def test_no_open_slice_allows_silently(repo):
    assert_allowed(edit(os.path.join(repo, "src", "app.py"), repo))


def test_open_slice_denies_prod_edit_with_actionable_reason(repo):
    start(repo)
    out = assert_denied(edit(os.path.join(repo, "src", "app.py"), repo))
    reason = out["permissionDecisionReason"]
    assert TITLE in reason
    assert CHECK in reason and os.path.isabs(CHECK)
    assert f"red --slice {shlex.quote(TITLE)}" in reason
    assert f"bypass --slice {shlex.quote(TITLE)} --reason" in reason
    assert f"cd {shlex.quote(repo)} && " in reason


def test_confirmed_red_unlocks(repo):
    start(repo)
    assert_denied(edit(os.path.join(repo, "src", "app.py"), repo))
    red(repo)
    assert_allowed(edit(os.path.join(repo, "src", "app.py"), repo))


def test_unconfirmed_red_does_not_unlock(repo):
    start(repo)
    red(repo, ok=False)
    assert_denied(edit(os.path.join(repo, "src", "app.py"), repo))


def test_confirmed_coverage_unlocks(repo):
    assert check(repo, "start", "--slice", TITLE, "--kind", "refactor").returncode == 0
    assert_denied(edit(os.path.join(repo, "src", "app.py"), repo))
    r = check(repo, "coverage", "--slice", TITLE, "--mutant", "exit 1", "--", *PASS)
    assert r.returncode == 0, r.stdout + r.stderr
    assert_allowed(edit(os.path.join(repo, "src", "app.py"), repo))


def test_bypass_unlocks(repo):
    start(repo)
    assert_denied(edit(os.path.join(repo, "src", "app.py"), repo))
    assert check(repo, "bypass", "--slice", TITLE, "--reason", "config only").returncode == 0
    assert_allowed(edit(os.path.join(repo, "src", "app.py"), repo))


def test_done_reallows_after_close(repo):
    start(repo)
    assert_denied(edit(os.path.join(repo, "src", "app.py"), repo))
    assert check(repo, "done", "--slice", TITLE).returncode == 0
    assert_allowed(edit(os.path.join(repo, "src", "app.py"), repo))


def test_new_start_relocks_after_earlier_red(repo):
    start(repo)
    red(repo)
    start(repo, "Slice Y: next")
    assert_denied(edit(os.path.join(repo, "src", "app.py"), repo))


@pytest.mark.parametrize("rel", ["tests/test_app.py", "src/app.test.js", "README.md", "docs/guide.md"])
def test_test_and_doc_files_always_allowed(repo, rel):
    start(repo)
    assert_denied(edit(os.path.join(repo, "src", "app.py"), repo))  # guard is live
    assert_allowed(edit(os.path.join(repo, rel), repo))


def test_path_outside_repo_allowed(repo, tmp_path):
    start(repo)
    assert_denied(edit(os.path.join(repo, "src", "app.py"), repo))  # guard is live
    outside = os.path.realpath(tmp_path / "elsewhere")
    os.makedirs(outside)
    assert_allowed(edit(os.path.join(outside, "x.py"), repo))


def test_open_slice_in_one_worktree_does_not_block_another(repo, tmp_path):
    other = os.path.join(os.path.realpath(tmp_path), "linked")
    _git(repo, "worktree", "add", "-q", "-b", "side", other)
    start(repo)
    assert_denied(edit(os.path.join(repo, "src", "app.py"), repo))
    assert_allowed(edit(os.path.join(other, "src", "app.py"), other))
    # reverse direction: the linked worktree locks itself, the main one (already red) stays free
    red(repo)
    start(other, "Slice Z: linked")
    assert_allowed(edit(os.path.join(repo, "src", "app.py"), repo))
    assert_denied(edit(os.path.join(other, "src", "app.py"), other))


def test_file_dir_decides_worktree_not_cwd(repo, tmp_path):
    other = os.path.join(os.path.realpath(tmp_path), "linked")
    _git(repo, "worktree", "add", "-q", "-b", "side", other)
    start(other, "Slice Z: linked")
    # hook cwd is the main worktree (no open slice); the edited file lives in the locked linked one
    assert_denied(edit(os.path.join(other, "src", "app.py"), repo))


def test_multiedit_covered(repo):
    start(repo)
    assert_denied(edit(os.path.join(repo, "src", "app.py"), repo, tool="MultiEdit"))


def test_notebook_edit_covered(repo):
    start(repo)
    assert_denied(edit(os.path.join(repo, "nb", "analysis.ipynb"), repo, tool="NotebookEdit",
                       key="notebook_path"))


def test_fail_open_bad_json(repo):
    start(repo)
    assert_allowed(run_hook(None, cwd=repo, raw="{not json"))


def test_fail_open_missing_file_path(repo):
    start(repo)
    assert_allowed(run_hook({"tool_name": "Edit", "tool_input": {}, "cwd": repo}, cwd=repo))


def test_fail_open_non_git_dir(tmp_path):
    plain = os.path.realpath(tmp_path / "plain")
    os.makedirs(plain)
    assert_allowed(edit(os.path.join(plain, "src", "app.py"), plain))


def test_fail_open_on_corrupt_log(repo):
    start(repo)
    assert_denied(edit(os.path.join(repo, "src", "app.py"), repo))  # guard is live
    with open(log_path(repo), "wb") as fh:
        fh.write(b"garbage\n\x00\xff not json\n")
    assert_allowed(edit(os.path.join(repo, "src", "app.py"), repo))


def test_large_log_decision_is_fast(repo):
    start(repo)  # creates the log dir; the file is then replaced with 20k entries plus a fresh start
    now = datetime.datetime.now().isoformat(timespec="seconds")
    with open(log_path(repo), "w", encoding="utf-8") as fh:
        for i in range(20000):
            fh.write(json.dumps({"phase": "red", "token": "%08x" % i, "at": now,
                                 "worktree": "/somewhere/else/%d" % (i % 50), "slice": "s%d" % i,
                                 "confirmed": True}) + "\n")
        fh.write(json.dumps({"phase": "start", "token": "deadbeef", "at": now, "worktree": repo,
                             "slice": TITLE, "confirmed": True}) + "\n")
    t0 = time.monotonic()
    r = edit(os.path.join(repo, "src", "app.py"), repo)
    elapsed = time.monotonic() - t0
    assert_denied(r)
    assert elapsed < 1.0, elapsed


def _write_log(repo, entries):
    os.makedirs(os.path.dirname(log_path(repo)), exist_ok=True)
    with open(log_path(repo), "w", encoding="utf-8") as fh:
        for e in entries:
            fh.write(json.dumps(e) + "\n")


def _entry(phase, wt, at=None, **kw):
    at = at or datetime.datetime.now().isoformat(timespec="seconds")
    return dict({"phase": phase, "token": "00000001", "at": at, "worktree": wt, "slice": TITLE,
                 "confirmed": True}, **kw)


@pytest.mark.parametrize("name", ["caf\u00e9-\u65e5\u672c", 'q"uote', "back\\slash"])
def test_special_character_repo_paths_are_guarded(tmp_path, name):
    root = os.path.join(os.path.realpath(tmp_path), name)
    try:
        os.makedirs(root)
    except OSError:
        pytest.skip("filesystem rejects this name")
    _git(root, "init", "-q")
    _git(root, "commit", "-q", "--allow-empty", "-m", "init")
    start(root)
    assert_denied(edit(os.path.join(root, "src", "app.py"), root))
    red(root)
    assert_allowed(edit(os.path.join(root, "src", "app.py"), root))


def test_deny_commands_survive_space_path_and_quote_title(tmp_path):
    root = os.path.join(os.path.realpath(tmp_path), "my repo")
    os.makedirs(root)
    _git(root, "init", "-q")
    _git(root, "commit", "-q", "--allow-empty", "-m", "init")
    title = 'Slice Q: say "hi"'
    start(root, title)
    reason = assert_denied(edit(os.path.join(root, "a.py"), root))["permissionDecisionReason"]
    prefix = reason.split("<P> = `", 1)[1].split("`", 1)[0]
    cmd = prefix + reason.split("`<P>", 1)[1].split(" -- <test cmd>")[0]
    argv = shlex.split(cmd)
    assert argv[:2] == ["cd", root] and argv[2] == "&&"
    assert argv[-1] == title and argv[-2] == "--slice"
    r = subprocess.run(cmd.replace("red --slice", "bypass --slice") + " --reason x", shell=True,
                       cwd="/", capture_output=True, text=True, env=_env())
    assert r.returncode == 0, r.stderr
    assert_allowed(edit(os.path.join(root, "a.py"), root))


def test_large_old_log_without_start_exits_early(repo):
    start(repo)
    old = (datetime.datetime.now() - datetime.timedelta(hours=6)).isoformat(timespec="seconds")
    _write_log(repo, [_entry("red", "/else/%d" % (i % 50), at=old) for i in range(20000)])
    t0 = time.monotonic()
    r = edit(os.path.join(repo, "src", "app.py"), repo)
    elapsed = time.monotonic() - t0
    assert_allowed(r)
    assert elapsed < 0.3 + 0.15, elapsed  # 0.3s decision plus interpreter start-up slack


def test_red_after_over_64kb_of_other_worktree_lines_unlocks(repo):
    entries = [_entry("start", repo)]
    entries += [_entry("red", "/else/%d" % (i % 50), slice="s%d" % i) for i in range(1000)]
    entries.append(_entry("red", repo))
    _write_log(repo, entries)
    assert os.path.getsize(log_path(repo)) > 64 * 1024
    assert_allowed(edit(os.path.join(repo, "src", "app.py"), repo))
    _write_log(repo, entries[:-1])
    assert_denied(edit(os.path.join(repo, "src", "app.py"), repo))


def test_relative_file_path_resolved_against_cwd(repo):
    start(repo)
    assert_denied(run_hook({"tool_name": "Edit", "tool_input": {"file_path": "src/app.py"},
                            "cwd": repo}, cwd=repo))


def test_symlinked_repo_path_is_guarded(repo, tmp_path):
    link = os.path.join(os.path.realpath(tmp_path), "link")
    os.symlink(repo, link)
    start(repo)
    assert_denied(edit(os.path.join(link, "src", "app.py"), link))


def test_case_variant_path_is_guarded(repo):
    start(repo)
    swapped = repo.swapcase()
    if not os.path.exists(swapped):
        pytest.skip("case-sensitive filesystem")
    assert_denied(edit(os.path.join(swapped, "src", "app.py"), repo))


def test_git_internal_file_allowed(repo):
    start(repo)
    assert_denied(edit(os.path.join(repo, "src", "app.py"), repo))  # guard is live
    assert_allowed(edit(os.path.join(repo, ".git", "hooks", "pre-commit"), repo))


def test_stale_start_allows(repo):
    start(repo)
    old = (datetime.datetime.now() - datetime.timedelta(hours=4, minutes=30)).isoformat(timespec="seconds")
    _write_log(repo, [_entry("start", repo, at=old)])
    assert_allowed(edit(os.path.join(repo, "src", "app.py"), repo))
