"""subagent_stop.py: an agent-TDD or code-reviewer report flags linked features whose
implementation progress moved since the last board sync."""
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOK = os.path.join(ROOT, "hooks", "subagent_stop.py")


def _feature(tmp_path, synced_at):
    d = tmp_path / "root" / "sdd-memory" / "users-me-proj" / "spec" / "2026-10-09-impl"
    d.mkdir(parents=True)
    text = "- Title: Impl\n- Current Phase: Implementation\n"
    (d / "workflow-state.md").write_text(text)
    import hashlib
    (d / "monday.json").write_text(json.dumps({"item_id": "1", "synced_at": synced_at,
        "state_hash": hashlib.sha256(text.encode()).hexdigest()[:16]}))
    (d / "impl-progress.json").write_text(json.dumps({"slices": {"1": "refactor_complete"}}))
    return os.path.realpath(d)


def run(tmp_path, message):
    env = dict(os.environ, CLAUDE_PLUGIN_DATA=str(tmp_path / "data"),
               CLAUDE_PLUGIN_OPTION_SHARED_MEMORY_ROOT=str(tmp_path / "root"))
    return subprocess.run([sys.executable, HOOK], capture_output=True, text=True, env=env, timeout=10,
                          input=json.dumps({"hook_event_name": "SubagentStop",
                                            "last_assistant_message": message}))


def test_tdd_report_flags_feature_with_newer_progress(tmp_path):
    d = _feature(tmp_path, "2020-01-01T00:00:00Z")
    proc = run(tmp_path, "<!--AGENT-TDD-REPORT-->\n<!--AGENT-TDD-PHASE:refactor_complete-->\n")
    assert proc.returncode == 0
    assert "monday-sync" in json.loads(proc.stdout)["systemMessage"]
    assert json.loads((tmp_path / "data" / "store.json").read_text())["pending"] == [d]


def test_unrelated_or_already_synced_is_silent(tmp_path):
    _feature(tmp_path, "2999-01-01T00:00:00Z")
    assert run(tmp_path, "<!--CODE-REVIEWER-REPORT-->\n").stdout.strip() == ""
    assert run(tmp_path, "just an answer").stdout.strip() == ""
