"""Slice 5: one validated git common dir helper, shared by state_cwd and evidence_path."""
import os
import subprocess
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "hooks"))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "scripts"))
import tdd_state  # noqa: E402
import tdd_check  # noqa: E402

_real_run = subprocess.run


def _git(cwd, *args):
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t",
               GIT_COMMITTER_EMAIL="t@t")
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, env=env)


@pytest.fixture
def repo(tmp_path):
    main = tmp_path / "main"
    main.mkdir()
    _git(main, "init", "-q")
    (main / "f.txt").write_text("x")
    _git(main, "add", ".")
    _git(main, "commit", "-q", "-m", "init")
    (main / "sub").mkdir()
    wt = tmp_path / "wt"
    _git(main, "worktree", "add", "-q", str(wt), "-b", "wtb")
    return main, wt


def test_same_common_dir_from_main_worktree_and_subdir(repo):
    main, wt = repo
    expected = os.path.realpath(main / ".git")
    for d in (main, wt, main / "sub"):
        got = tdd_state.git_common_dir(str(d))
        assert os.path.isabs(got)
        assert os.path.realpath(got) == expected


def test_non_git_dir_is_none(tmp_path):
    d = tmp_path / "plain"
    d.mkdir()
    assert tdd_state.git_common_dir(str(d)) is None


def test_junk_output_from_old_git_falls_back(repo, monkeypatch):
    main, _ = repo

    def fake_run(cmd, *a, **kw):
        if "--path-format=absolute" in cmd:
            return subprocess.CompletedProcess(cmd, 0, stdout="--path-format=absolute\n.git\n", stderr="")
        return _real_run(cmd, *a, **kw)

    monkeypatch.setattr(tdd_state.subprocess, "run", fake_run)
    got = tdd_state.git_common_dir(str(main / "sub"))
    assert os.path.isabs(got)
    assert os.path.realpath(got) == os.path.realpath(main / ".git")


def test_state_cwd_uses_helper(monkeypatch):
    monkeypatch.setattr(tdd_state, "git_common_dir", lambda cwd: "/x/y/.git")
    assert tdd_state.state_cwd("/anywhere") == "/x/y"
    monkeypatch.setattr(tdd_state, "git_common_dir", lambda cwd: None)
    assert tdd_state.state_cwd("/anywhere") == "/anywhere"


def test_evidence_path_uses_helper(monkeypatch):
    monkeypatch.setattr(tdd_check, "git_common_dir", lambda cwd: "/x/y/.git")
    assert tdd_check.evidence_path("/anywhere") == "/x/y/.git/agent-tdd/evidence.jsonl"


def test_evidence_path_real_repo_shared_across_worktrees(repo):
    main, wt = repo
    a = tdd_check.evidence_path(str(main))
    b = tdd_check.evidence_path(str(wt))
    assert os.path.realpath(a) == os.path.realpath(b)


def test_tdd_check_inline_fallback_when_hooks_import_blocked(repo, tmp_path, monkeypatch):
    import importlib.util
    monkeypatch.setitem(sys.modules, "tdd_state", None)  # makes `from tdd_state import ...` raise ImportError
    spec = importlib.util.spec_from_file_location("tdd_check_standalone", tdd_check.__file__)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.git_common_dir is not tdd_state.git_common_dir
    main, wt = repo
    expected = os.path.realpath(main / ".git")
    for d in (main, wt, main / "sub"):
        assert os.path.realpath(mod.git_common_dir(str(d))) == expected
    plain = tmp_path / "plain"
    plain.mkdir()
    assert mod.git_common_dir(str(plain)) is None
