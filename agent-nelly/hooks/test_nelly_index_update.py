"""Tests for hooks/nelly_index_update.py -- PostToolUse index-freshness hook
that keeps nelly-index.json in sync with Agent Nelly's memory store.

Drives the hook exactly as the harness does: pipe a JSON payload on stdin to
the script via subprocess, and assert on the resulting nelly-index.json.
"""
import json
import os
import subprocess
import sys

HOOK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nelly_index_update.py")


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


def _write_entry(cwd, name, description="A test fact.", env=None):
    full_env = dict(os.environ)
    if env:
        full_env.update(env)
    proc = subprocess.run(
        [sys.executable, "-c", (
            "import sys; sys.path.insert(0, '.'); import nelly_memory; "
            f"d = nelly_memory.ensure_entries_dir({cwd!r}); "
            f"open(d + '/{name}.md', 'w').write("
            f"'---\\nname: {name}\\ndescription: {description}\\n"
            f"metadata:\\n  type: project\\n  last_referenced: 2026-08-16\\n---\\n\\nBody.')"
        )],
        cwd=os.path.dirname(HOOK),
        capture_output=True,
        text=True,
        env=full_env,
    )
    assert proc.returncode == 0, proc.stderr
    return os.path.join(_memory_dir(cwd, env), "entries", f"{name}.md")


def _memory_dir(cwd, env=None):
    full_env = dict(os.environ)
    if env:
        full_env.update(env)
    proc = subprocess.run(
        [sys.executable, "nelly_memory.py", "--path", cwd],
        cwd=os.path.dirname(HOOK),
        capture_output=True,
        text=True,
        env=full_env,
    )
    assert proc.returncode == 0, proc.stderr
    return proc.stdout.strip()


def _isolated_env(tmp_path):
    return {"HOME": str(tmp_path / "home")}


def test_no_op_for_path_outside_memory_store(tmp_path):
    env = _isolated_env(tmp_path)
    target = str(tmp_path / "unrelated" / "file.md")
    payload = {"tool_input": {"file_path": target}, "cwd": str(tmp_path)}

    proc = run_hook(payload, env=env)

    assert proc.returncode == 0
    assert proc.stdout.strip() == ""


def test_no_op_for_missing_file_path():
    payload = {"tool_input": {}, "cwd": "/tmp"}

    proc = run_hook(payload)

    assert proc.returncode == 0
    assert proc.stdout.strip() == ""


def test_entry_write_upserts_into_index(tmp_path):
    env = _isolated_env(tmp_path)
    cwd = str(tmp_path / "project")
    entry_path = _write_entry(cwd, "fresh-fact", env=env)
    payload = {"tool_input": {"file_path": entry_path}, "cwd": cwd}

    proc = run_hook(payload, env=env)

    assert proc.returncode == 0
    mem_dir = _memory_dir(cwd, env)
    index_path = os.path.join(mem_dir, "nelly-index.json")
    assert os.path.isfile(index_path)
    records = json.loads(open(index_path).read())
    assert [r["slug"] for r in records] == ["fresh-fact"]


def test_memory_md_edit_triggers_full_project_rescan(tmp_path):
    env = _isolated_env(tmp_path)
    cwd = str(tmp_path / "project")
    _write_entry(cwd, "entry-one", env=env)
    _write_entry(cwd, "entry-two", env=env)
    mem_dir = _memory_dir(cwd, env)
    memory_md = os.path.join(mem_dir, "MEMORY.md")
    payload = {"tool_input": {"file_path": memory_md}, "cwd": cwd}

    proc = run_hook(payload, env=env)

    assert proc.returncode == 0
    index_path = os.path.join(mem_dir, "nelly-index.json")
    records = json.loads(open(index_path).read())
    assert {r["slug"] for r in records} == {"entry-one", "entry-two"}


def test_memory_md_edit_resyncs_after_out_of_band_archive_move(tmp_path):
    """The hook can't observe a Bash `mv` (archive) directly, but every
    write-back path that archives an entry also edits MEMORY.md right after
    -- this is what actually resyncs the index in that case.
    """
    env = _isolated_env(tmp_path)
    cwd = str(tmp_path / "project")
    entry_path = _write_entry(cwd, "will-be-archived", env=env)
    run_hook({"tool_input": {"file_path": entry_path}, "cwd": cwd}, env=env)

    os.remove(entry_path)  # simulate the archive `mv` this hook never sees

    mem_dir = _memory_dir(cwd, env)
    memory_md = os.path.join(mem_dir, "MEMORY.md")
    proc = run_hook({"tool_input": {"file_path": memory_md}, "cwd": cwd}, env=env)

    assert proc.returncode == 0
    index_path = os.path.join(mem_dir, "nelly-index.json")
    records = json.loads(open(index_path).read())
    assert records == []


def test_global_memory_edit_triggers_global_rescan(tmp_path):
    env = _isolated_env(tmp_path)
    global_md_dir = os.path.join(str(tmp_path / "home"), ".claude", "agent-nelly-memory", "global")
    os.makedirs(global_md_dir, exist_ok=True)
    global_md = os.path.join(global_md_dir, "GLOBAL-MEMORY.md")
    with open(global_md, "w", encoding="utf-8") as fh:
        fh.write(
            "---\nname: global-fact\ndescription: A global fact.\n"
            "metadata:\n  type: reference\n  last_referenced: 2026-08-16\n---\n\nBody.\n"
        )
    payload = {"tool_input": {"file_path": global_md}, "cwd": str(tmp_path)}

    proc = run_hook(payload, env=env)

    assert proc.returncode == 0
    index_path = os.path.join(global_md_dir, "nelly-index.json")
    records = json.loads(open(index_path).read())
    assert [r["slug"] for r in records] == ["global-fact"]


def test_archive_path_under_store_is_no_op(tmp_path):
    env = _isolated_env(tmp_path)
    cwd = str(tmp_path / "project")
    mem_dir = _memory_dir(cwd, env)
    archived = os.path.join(mem_dir, "archive", "old-entry.md")
    os.makedirs(os.path.dirname(archived), exist_ok=True)
    with open(archived, "w") as fh:
        fh.write("---\nname: old-entry\ndescription: x\nmetadata:\n  type: project\n---\n")
    payload = {"tool_input": {"file_path": archived}, "cwd": cwd}

    proc = run_hook(payload, env=env)

    assert proc.returncode == 0
    assert not os.path.exists(os.path.join(mem_dir, "nelly-index.json"))
