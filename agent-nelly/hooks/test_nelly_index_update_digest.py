"""Slice 5 regression (not Red): the PostToolUse hook nelly_index_update.py,
given a Write to a digest nested under entries/research-digest/, upserts it
into nelly-index.json. Expected to pass both before and after Slice 5.

Uses the same isolated-env subprocess pattern as test_nelly_index_update.py.
"""
import json
import os
import subprocess
import sys

HOOK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nelly_index_update.py")
NAME = "digest-hook-upsert-0123456789ab"


def _isolated_env(tmp_path):
    env = dict(os.environ)
    env.update({
        "HOME": str(tmp_path / "home"),
        "CLAUDE_PLUGIN_DATA": str(tmp_path / "home" / ".claude" / "plugins" / "data" / "agent-nelly"),
    })
    return env


def _memory_dir(cwd, env):
    proc = subprocess.run(
        [sys.executable, "nelly_memory.py", "--path", cwd],
        cwd=os.path.dirname(HOOK), capture_output=True, text=True, env=env,
    )
    assert proc.returncode == 0, proc.stderr
    return proc.stdout.strip()


def test_write_to_nested_digest_upserts_into_index(tmp_path):
    env = _isolated_env(tmp_path)
    cwd = str(tmp_path / "project")
    mem_dir = _memory_dir(cwd, env)
    digest_dir = os.path.join(mem_dir, "entries", "research-digest")
    os.makedirs(digest_dir, exist_ok=True)
    path = os.path.join(digest_dir, f"{NAME}.md")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(
            f"---\nname: {NAME}\ndescription: A topic\ntype: research-digest\n"
            "topic: A topic\nsources:\n  - path: a.py\n    hash: " + "a" * 40 + "\n"
            "updated: 2026-09-25T15:40:00Z\n---\nBody.\n"
        )

    proc = subprocess.run(
        [sys.executable, HOOK],
        input=json.dumps({"tool_input": {"file_path": path}, "cwd": cwd}),
        capture_output=True, text=True, env=env,
    )

    assert proc.returncode == 0, proc.stderr
    records = json.loads(open(os.path.join(mem_dir, "nelly-index.json")).read())
    assert [r["slug"] for r in records] == [NAME]
    assert records[0]["type"] == "research-digest"
    assert records[0]["file_path"] == os.path.join("entries", "research-digest", f"{NAME}.md")
