"""Release 5 slice 1D review fix (F2): hotspots.json updates are a locked read-modify-write
(nelly_store.update_entry on the local state dir), so concurrent updates keep every count, and a
corrupt file is kept as a conflicts/ sidecar instead of being silently reset."""
import json
import os
import subprocess
import sys

import pytest

HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))
HOOK = os.path.join(HOOKS_DIR, "nelly_hotspot_tracker.py")


@pytest.fixture
def env(tmp_path):
    full = dict(os.environ)
    full.update({
        "HOME": str(tmp_path / "home"),
        "CLAUDE_CONFIG_DIR": str(tmp_path / "home" / ".claude"),
        "CLAUDE_PLUGIN_DATA": str(tmp_path / "home" / ".claude" / "plugins" / "data" / "agent-nelly"),
    })
    full.pop("NELLY_GATE", None)
    return full


@pytest.fixture
def cwd(tmp_path):
    d = tmp_path / "proj"
    d.mkdir()
    return str(d)


def _state_dir(cwd, env):
    code = "import sys; sys.path.insert(0, %r); import nelly_memory; print(nelly_memory.local_state_dir(sys.argv[1]))" % HOOKS_DIR
    return subprocess.run([sys.executable, "-c", code, cwd], env=env, capture_output=True,
                          text=True, check=True).stdout.strip()


_LOOP = """
import json, subprocess, sys
hook, cwd, f, n = sys.argv[1:5]
payload = json.dumps({"tool_name": "Read", "tool_input": {"file_path": f}, "cwd": cwd})
for _ in range(int(n)):
    subprocess.run([sys.executable, hook], input=payload, text=True, check=True)
"""


def test_concurrent_hotspot_updates_keep_all_counts(cwd, env):
    procs_n, loops = 6, 12
    procs = [subprocess.Popen([sys.executable, "-c", _LOOP, HOOK, cwd, "a.py", str(loops)], env=env,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
             for _ in range(procs_n)]
    for p in procs:
        _so, se = p.communicate(timeout=180)
        assert p.returncode == 0, se
    with open(os.path.join(_state_dir(cwd, env), "hotspots.json"), encoding="utf-8") as fh:
        data = json.load(fh)
    assert data["files"]["a.py"]["count"] == procs_n * loops


def test_corrupt_hotspots_file_is_kept_as_sidecar(cwd, env):
    d = _state_dir(cwd, env)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "hotspots.json"), "w", encoding="utf-8") as fh:
        fh.write("{not json")
    proc = subprocess.run([sys.executable, HOOK], env=env, text=True, capture_output=True,
                          input=json.dumps({"tool_name": "Read", "tool_input": {"file_path": "a.py"},
                                            "cwd": cwd}))
    assert proc.returncode == 0 and "Traceback" not in proc.stderr
    with open(os.path.join(d, "hotspots.json"), encoding="utf-8") as fh:
        assert json.load(fh)["files"]["a.py"]["count"] == 1
    sidecars = os.listdir(os.path.join(d, "conflicts"))
    assert len(sidecars) == 1 and sidecars[0].startswith("hotspots.")
    with open(os.path.join(d, "conflicts", sidecars[0]), encoding="utf-8") as fh:
        assert fh.read() == "{not json"


_HOLD = """
import sys, time
sys.path.insert(0, %r)
import nelly_store
with nelly_store.lock(sys.argv[1]):
    open(sys.argv[2], "w").close()
    time.sleep(30)
""" % os.path.join(HOOKS_DIR, "..", "scripts")


def test_hotspot_hook_gives_up_quickly_when_store_is_locked(cwd, env, tmp_path):
    import time
    d = _state_dir(cwd, env)
    ready = str(tmp_path / "ready")
    holder = subprocess.Popen([sys.executable, "-c", _HOLD, d, ready], stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, text=True)
    try:
        deadline = time.time() + 15
        while not os.path.exists(ready):
            assert holder.poll() is None and time.time() < deadline
            time.sleep(0.02)
        start = time.time()
        proc = subprocess.run([sys.executable, HOOK], env=env, text=True, capture_output=True,
                              input=json.dumps({"tool_name": "Read",
                                                "tool_input": {"file_path": "a.py"}, "cwd": cwd}))
        elapsed = time.time() - start
    finally:
        holder.kill()
        holder.communicate()
    assert proc.returncode == 0 and "Traceback" not in proc.stderr
    assert not os.path.exists(os.path.join(d, "hotspots.json"))
    assert elapsed < 0.6, elapsed
