"""Tests for Agent Nelly's shared memory root (userConfig `shared_memory_root`).

Every case runs the real hook/CLI in a subprocess with its own CLAUDE_PLUGIN_DATA and
CLAUDE_PLUGIN_OPTION_SHARED_MEMORY_ROOT, because nelly_memory resolves BASE at import time.
"""
import json
import os
import subprocess
import sys

import pytest

HOOKS = os.path.dirname(os.path.abspath(__file__))
ENV_KEY = "CLAUDE_PLUGIN_OPTION_SHARED_MEMORY_ROOT"


@pytest.fixture
def roots(tmp_path):
    return {
        "data": str(tmp_path / "data" / "agent-nelly-inline"),
        "shared": str(tmp_path / "shared"),
        "cwd": str(tmp_path / "project"),
    }


def _env(roots, shared=True):
    env = dict(os.environ)
    env["CLAUDE_PLUGIN_DATA"] = roots["data"]
    if shared:
        env[ENV_KEY] = roots["shared"]
    else:
        env.pop(ENV_KEY, None)
    return env


def run(script, args=(), payload=None, roots=None, shared=True):
    return subprocess.run(
        [sys.executable, os.path.join(HOOKS, script), *args],
        input=json.dumps(payload) if payload is not None else "",
        capture_output=True, text=True, env=_env(roots, shared),
    )


def slug(cwd):
    sys.path.insert(0, HOOKS)
    from shared_slug import get_project_slug
    return get_project_slug(cwd)


def decision(proc):
    assert proc.returncode == 0, proc.stderr
    if not proc.stdout.strip():
        return None
    return json.loads(proc.stdout)["hookSpecificOutput"]["permissionDecision"]


def test_path_uses_shared_root_when_set(roots):
    proc = run("nelly_memory.py", ["--path", roots["cwd"]], roots=roots)
    assert proc.returncode == 0, proc.stderr
    expected = os.path.join(roots["shared"], "agent-nelly-memory", slug(roots["cwd"]))
    assert proc.stdout.strip() == expected
    assert os.path.isfile(os.path.join(expected, "MEMORY.md"))


def test_path_falls_back_to_plugin_data_when_unset(roots):
    proc = run("nelly_memory.py", ["--path", roots["cwd"]], roots=roots, shared=False)
    assert proc.stdout.strip() == os.path.join(roots["data"], "agent-nelly-memory", slug(roots["cwd"]))


def test_global_path_uses_shared_root(roots):
    proc = run("nelly_memory.py", ["--global-path"], roots=roots)
    assert proc.stdout.strip() == os.path.join(roots["shared"], "agent-nelly-memory", "global")


def test_relative_shared_root_fails_clearly(roots):
    roots = dict(roots, shared="relative/dir")
    proc = run("nelly_memory.py", ["--path", roots["cwd"]], roots=roots)
    assert proc.returncode != 0
    assert "absolute" in proc.stderr


def test_permission_hook_allows_writes_under_shared_root(roots):
    for target in (
        os.path.join(roots["shared"], "agent-nelly-memory", slug(roots["cwd"]), "entries", "x.md"),
        os.path.join(roots["shared"], "agent-nelly-memory", "global", "GLOBAL-MEMORY.md"),
    ):
        proc = run("nelly_memory_permission.py",
                   payload={"tool_input": {"file_path": target}, "cwd": roots["cwd"]}, roots=roots)
        assert decision(proc) == "allow", target


def test_permission_hook_does_not_allow_stale_local_store(roots):
    target = os.path.join(roots["data"], "agent-nelly-memory", slug(roots["cwd"]), "entries", "x.md")
    proc = run("nelly_memory_permission.py",
               payload={"tool_input": {"file_path": target}, "cwd": roots["cwd"]}, roots=roots)
    assert decision(proc) is None


def test_slug_guard_passes_correct_slug_under_shared_root(roots):
    target = os.path.join(roots["shared"], "agent-nelly-memory", slug(roots["cwd"]), "MEMORY.md")
    proc = run("nelly_slug_guard.py",
               payload={"tool_input": {"file_path": target}, "cwd": roots["cwd"]}, roots=roots)
    assert decision(proc) is None


def test_slug_guard_denies_wrong_slug_under_shared_root(roots):
    target = os.path.join(roots["shared"], "agent-nelly-memory", "wrong-slug", "MEMORY.md")
    proc = run("nelly_slug_guard.py",
               payload={"tool_input": {"file_path": target}, "cwd": roots["cwd"]}, roots=roots)
    assert decision(proc) == "deny"


def test_slug_guard_denies_local_store_while_shared_root_active(roots):
    target = os.path.join(roots["data"], "agent-nelly-memory", slug(roots["cwd"]), "MEMORY.md")
    proc = run("nelly_slug_guard.py",
               payload={"tool_input": {"file_path": target}, "cwd": roots["cwd"]}, roots=roots)
    assert decision(proc) == "deny"
    assert "merge_plugin_data.py" in proc.stdout


def test_slug_guard_leaves_local_store_alone_without_shared_root(roots):
    target = os.path.join(roots["data"], "agent-nelly-memory", slug(roots["cwd"]), "MEMORY.md")
    proc = run("nelly_slug_guard.py",
               payload={"tool_input": {"file_path": target}, "cwd": roots["cwd"]},
               roots=roots, shared=False)
    assert decision(proc) is None


def test_hotspots_stay_machine_local(roots):
    os.makedirs(roots["cwd"])
    touched = os.path.join(roots["cwd"], "a.py")
    open(touched, "w").close()
    proc = run("nelly_hotspot_tracker.py",
               payload={"tool_name": "Read", "tool_input": {"file_path": touched}, "cwd": roots["cwd"]},
               roots=roots)
    assert proc.returncode == 0
    local = os.path.join(roots["data"], "agent-nelly-memory", slug(roots["cwd"]), "hotspots.json")
    shared = os.path.join(roots["shared"], "agent-nelly-memory", slug(roots["cwd"]), "hotspots.json")
    assert os.path.isfile(local)
    assert not os.path.exists(shared)


def test_session_start_scaffolds_root_and_rebuilds_index(roots):
    mem = os.path.join(roots["shared"], "agent-nelly-memory", slug(roots["cwd"]))
    os.makedirs(os.path.join(mem, "entries"))
    with open(os.path.join(mem, "entries", "synced-fact.md"), "w") as fh:
        fh.write("---\nname: synced-fact\ndescription: arrived from another machine\n---\nbody\n")

    proc = run("nelly_session_start.py", payload={"cwd": roots["cwd"]}, roots=roots)
    assert proc.returncode == 0, proc.stderr
    ctx = json.loads(proc.stdout)["hookSpecificOutput"]["additionalContext"]
    assert mem in ctx
    assert roots["shared"] in ctx

    assert os.path.isfile(os.path.join(roots["shared"], ".gitignore"))
    assert os.path.isfile(os.path.join(roots["shared"], ".gitattributes"))
    with open(os.path.join(mem, "nelly-index.json")) as fh:
        assert "synced-fact" in fh.read()
