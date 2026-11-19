"""user_led_guard.evaluate: deny non-test repo edits while Implementation Mode is user."""
import os
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hooks"))
import user_led_guard  # noqa: E402

MEM = "sdd-memory/proj/spec/feat"


@pytest.fixture
def env(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    mem = tmp_path / MEM
    mem.mkdir(parents=True)
    (tmp_path / "outside").mkdir()
    (repo / "src").mkdir()
    (repo / "src" / "real.py").write_text("x")
    os.symlink(repo / "src" / "real.py", tmp_path / "outside" / "link_in.py")
    os.symlink(tmp_path / "outside", repo / "tests_link")
    return tmp_path, repo, mem


def _state(mem, mode):
    p = mem / "workflow-state.md"
    lines = ["- Feature: f"] + ([f"- Implementation Mode: {mode}"] if mode else [])
    p.write_text("\n".join(lines) + "\n")
    return str(p)


def _payload(repo, path, tool="Write"):
    key = "notebook_path" if tool == "NotebookEdit" else "file_path"
    return {"cwd": str(repo), "tool_name": tool, "tool_input": {key: path}}


@pytest.mark.parametrize("rel,denied", [
    ("src/app.py", True),
    ("README.md", True),
    ("src/../src/app.py", True),
    ("test_app.py", False),
    ("src/app_test.py", False),
    ("src/app.spec.ts", False),
    ("src/app.test.ts", False),
    ("tests/helper.py", False),
    ("pkg/__tests__/x.js", False),
    ("spec/x.rb", False),
    ("src/spec/app.py", True),
    ("src/deep/tests/x.py", True),
    ("pkg/tests/x.py", False),
    ("tests_link/anything.py", False),  # symlink resolves outside the repo: not this guard's business
])
def test_paths(env, rel, denied):
    tmp, repo, mem = env
    state = _state(mem, "user")
    reason = user_led_guard.evaluate(_payload(repo, rel), state_path=state)
    assert bool(reason) is denied
    if denied:
        assert os.path.basename(rel) in reason
        assert "User-led mode" in reason and "Implementation Mode: agent" in reason


def test_symlink_into_repo_is_classified_by_target(env):
    tmp, repo, mem = env
    state = _state(mem, "user")
    reason = user_led_guard.evaluate(_payload(repo, str(tmp / "outside" / "link_in.py")), state_path=state)
    assert reason and "real.py" in reason


def test_symlinked_name_cannot_fake_test_path(env):
    tmp, repo, mem = env
    os.symlink(repo / "src" / "real.py", repo / "test_fake.py")
    reason = user_led_guard.evaluate(_payload(repo, "test_fake.py"), state_path=_state(mem, "user"))
    assert reason


def test_outside_repo_and_memory_dir_allowed(env):
    tmp, repo, mem = env
    state = _state(mem, "user")
    assert user_led_guard.evaluate(_payload(repo, str(tmp / "outside" / "a.py")), state_path=state) is None
    assert user_led_guard.evaluate(_payload(repo, str(mem / "design.md")), state_path=state) is None


def test_memory_dir_inside_repo_allowed(env):
    tmp, repo, _ = env
    mem = repo / "sdd-memory" / "p" / "spec" / "f"
    mem.mkdir(parents=True)
    state = _state(mem, "user")
    assert user_led_guard.evaluate(_payload(repo, str(mem / "tasks.md")), state_path=state) is None


@pytest.mark.parametrize("tool", ["Write", "Edit", "MultiEdit", "NotebookEdit"])
def test_all_write_tools_denied(env, tool):
    tmp, repo, mem = env
    assert user_led_guard.evaluate(_payload(repo, "src/app.py", tool), state_path=_state(mem, "user"))


@pytest.mark.parametrize("mode", ["agent", None])
def test_noop_when_not_user_mode(env, mode):
    tmp, repo, mem = env
    assert user_led_guard.evaluate(_payload(repo, "src/app.py"), state_path=_state(mem, mode)) is None


def test_mode_with_trailing_words_enables_guard(env):
    tmp, repo, mem = env
    state = _state(mem, "User (walk the slices)")
    assert user_led_guard.evaluate(_payload(repo, "src/app.py"), state_path=state)


def test_is_user_led_compares_lowercased_first_token():
    import sdd_state
    assert sdd_state.is_user_led({"implementation mode": "User (walk)"})
    assert sdd_state.is_user_led({"implementation mode": "user"})
    assert not sdd_state.is_user_led({"implementation mode": "agent"})
    assert not sdd_state.is_user_led({})


def test_noop_without_state_or_path(env):
    tmp, repo, mem = env
    assert user_led_guard.evaluate(_payload(repo, "src/app.py"), state_path=None) is None
    assert user_led_guard.evaluate(_payload(repo, "src/app.py"), state_path=str(mem / "nope.md")) is None
    assert user_led_guard.evaluate({"cwd": str(repo), "tool_input": {}}, state_path=_state(mem, "user")) is None


def test_case_variant_repo_path_denied(env):
    tmp, repo, mem = env
    variant = tmp / "REPO"
    if not variant.exists():
        pytest.skip("case-sensitive filesystem")
    reason = user_led_guard.evaluate(_payload(repo, str(variant / "src" / "app.py")), state_path=_state(mem, "user"))
    assert reason


def test_cwd_in_repo_subdir(env):
    tmp, repo, mem = env
    state = _state(mem, "user")
    assert user_led_guard.evaluate(_payload(repo / "src", "app.py"), state_path=state)
    assert user_led_guard.evaluate(_payload(repo / "src", "../tests/t.py"), state_path=state) is None


@pytest.mark.parametrize("exc", [FileNotFoundError("git"), subprocess.TimeoutExpired("git", 3)])
def test_git_unavailable_falls_back_to_cwd(env, monkeypatch, exc):
    tmp, repo, mem = env

    def boom(*a, **k):
        raise exc
    monkeypatch.setattr(user_led_guard.subprocess, "run", boom)
    state = _state(mem, "user")
    assert user_led_guard.evaluate(_payload(repo, "src/app.py"), state_path=state)
    assert user_led_guard.evaluate(_payload(repo, "tests/t.py"), state_path=state) is None


def test_other_feature_memory_dir_not_allowed_inside_repo(env):
    tmp, repo, _ = env
    mine = repo / "sdd-memory" / "p" / "spec" / "mine"
    other = repo / "sdd-memory" / "p" / "spec" / "other"
    mine.mkdir(parents=True)
    other.mkdir(parents=True)
    state = _state(mine, "user")
    assert user_led_guard.evaluate(_payload(repo, str(mine / "d.md")), state_path=state) is None
    assert user_led_guard.evaluate(_payload(repo, str(other / "d.md")), state_path=state)
