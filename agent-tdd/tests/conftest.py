"""Hermetic env for every agent-tdd test: no read/write of the real shared memory root."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "hooks"))
import tdd_state  # noqa: E402


@pytest.fixture(autouse=True)
def _hermetic_env(tmp_path, monkeypatch):
    data = tmp_path / "plugin-data"
    monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(data))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "claude-config"))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.delenv("CLAUDE_PLUGIN_OPTION_SHARED_MEMORY_ROOT", raising=False)
    monkeypatch.setattr(tdd_state, "BASE", str(data / "agent-tdd-state"))
    yield
