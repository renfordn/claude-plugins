"""scripts/agent_stall.py: flags a subagent idle past the limit while waiting on background work."""
import datetime
import json
import os
import subprocess
import sys

SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts", "agent_stall.py")
sys.path.insert(0, os.path.dirname(SCRIPT))
import agent_stall as s  # noqa: E402

NOW = datetime.datetime(2026, 11, 22, 12, 0, tzinfo=datetime.timezone.utc)
LOOP = 'while pgrep -f "git commit" >/dev/null; do sleep 15; done'


def _line(ts, content, kind="assistant"):
    return json.dumps({"type": kind, "timestamp": ts, "message": {"role": kind, "content": content}})


def write(tmp_path, minutes_ago, text="Done.", background=None):
    ts = (NOW - datetime.timedelta(minutes=minutes_ago)).isoformat().replace("+00:00", "Z")
    lines = []
    for cmd in background or []:
        lines.append(_line(ts, [{"type": "tool_use", "name": "Bash",
                                 "input": {"command": cmd, "run_in_background": True}}]))
    lines.append("not json")
    lines.append(_line(ts, [{"type": "text", "text": text}]))
    p = tmp_path / "agent-abc.jsonl"
    p.write_text("\n".join(lines) + "\n")
    return str(p)


def test_recent_activity_is_active(tmp_path):
    r = s.assess(write(tmp_path, 5, "Waiting on background work."), 20, NOW, [])
    assert r["status"] == "active"


def test_idle_and_waiting_is_stalled_and_flags_self_matching_loop(tmp_path):
    path = write(tmp_path, 720, "I'm waiting on my own background work.", [LOOP])
    r = s.assess(path, 20, NOW, [(4242, "/bin/zsh -c " + LOOP)])
    assert r["status"] == "stalled"
    assert r["idle_minutes"] == 720
    cmd = r["background_commands"][0]
    assert cmd["live_pids"] == [4242]
    assert cmd["self_matching_wait"] == "pgrep -f git commit"
    assert "status-check" in r["advice"]


def test_live_background_command_alone_is_stalled(tmp_path):
    path = write(tmp_path, 60, "Committing.", ["git commit -m x"])
    r = s.assess(path, 20, NOW, [(7, "git commit -m x")])
    assert r["status"] == "stalled"


def test_idle_without_background_work_is_idle(tmp_path):
    r = s.assess(write(tmp_path, 60, "All slices green."), 20, NOW, [])
    assert r["status"] == "idle"
    assert "git log" in r["advice"]


def test_cli_finds_transcript_by_agent_id_and_exit_codes(tmp_path, monkeypatch):
    cfg = tmp_path / "cfg"
    sub = cfg / "projects" / "proj" / "sess" / "subagents"
    sub.mkdir(parents=True)
    old = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=3))
    (sub / "agent-abc.jsonl").write_text(
        _line(old.isoformat(), [{"type": "text", "text": "Waiting on background work."}]) + "\n")
    env = dict(os.environ, CLAUDE_CONFIG_DIR=str(cfg))
    r = subprocess.run([sys.executable, SCRIPT, "--agent-id", "agent-abc"], capture_output=True,
                       text=True, env=env, timeout=20)
    assert r.returncode == 3, r.stdout + r.stderr
    assert json.loads(r.stdout)["status"] == "stalled"
    r = subprocess.run([sys.executable, SCRIPT, "--agent-id", "nope"], capture_output=True,
                       text=True, env=env, timeout=20)
    assert r.returncode == 2
