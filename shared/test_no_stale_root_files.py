"""The repo root must not carry the stale plugin-harness tasks.md."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_no_root_tasks_md():
    assert not (ROOT / "tasks.md").exists()
