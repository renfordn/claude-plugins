"""StoreLocked (an OSError) must not crash best-effort hook callers when the store lock is held
by another process."""
import io
import json
import os
import subprocess
import sys
import time

import pytest

import nelly_index_update
import nelly_memory
import nelly_session_start

SCRIPTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts")
CWD = os.path.expanduser("~/Codebase/proj-locked")

_HOLD = """
import sys, time
sys.path.insert(0, %r)
import nelly_store
with nelly_store.lock(sys.argv[1]):
    open(sys.argv[2], "w").close()
    time.sleep(30)
""" % SCRIPTS


@pytest.fixture
def held_store(tmp_path, monkeypatch):
    base = str(tmp_path / "agent-nelly-memory")
    monkeypatch.setattr(nelly_memory, "BASE", base)
    monkeypatch.setattr(nelly_memory, "LOCAL_BASE", base)
    entries = nelly_memory.ensure_entries_dir(CWD)
    with open(os.path.join(entries, "x.md"), "w") as fh:
        fh.write("---\nname: x\ndescription: d\nmetadata:\n  type: project\n---\n")
    ready = str(tmp_path / "ready")
    holder = subprocess.Popen([sys.executable, "-c", _HOLD, nelly_memory.memory_dir(CWD), ready])
    deadline = time.time() + 15
    while not os.path.exists(ready):
        assert time.time() < deadline
        time.sleep(0.02)
    yield entries
    holder.kill()
    holder.wait()


def test_session_start_still_prints_brief_when_store_locked(held_store, monkeypatch, capsys, tmp_path):
    shared = str(tmp_path / "shared")
    monkeypatch.setattr(nelly_memory, "SHARED_ROOT", shared)
    monkeypatch.setattr(nelly_session_start, "SHARED_ROOT", shared)
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": CWD})))
    with pytest.raises(SystemExit) as exc:
        nelly_session_start.main()
    assert exc.value.code == 0
    payload = json.loads(capsys.readouterr().out)
    assert "agent-nelly" in payload["hookSpecificOutput"]["additionalContext"].lower() or \
        payload["hookSpecificOutput"]["additionalContext"]


def test_index_update_exits_zero_when_store_locked(held_store, monkeypatch):
    payload = {"cwd": CWD, "tool_input": {"file_path": os.path.join(held_store, "x.md")}}
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
    with pytest.raises(SystemExit) as exc:
        nelly_index_update.main()
    assert exc.value.code == 0
