"""Release 5 contract (slice 0): agent models, description budget, hook registration and
timeouts, new hook stubs, INTEROP/template evidence contract, SessionStart call sites."""
import io
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

import nelly_memory
import nelly_session_start

ROOT = Path(__file__).resolve().parent.parent
HOOKS = ROOT / "hooks"
NEW_HOOKS = ("nelly_stop_capture.py", "nelly_schema_guard.py", "nelly_delete_guard.py",
             "nelly_freshness.py", "nelly_pending.py")
DESCRIPTION_CAP = 2200  # total of the 4 agent descriptions (0.6.7: 3298; 0.7.0: 2076)


def _front(path):
    return yaml.safe_load(path.read_text().split("---")[1])


@pytest.mark.parametrize("agent,model,effort", [
    ("agent-nelly", "opus", "medium"),
    ("nelly-maintenance", "opus", "medium"),
    ("nelly-planning-agent", "sonnet", "low"),
    ("nelly-research-agent", "haiku", "low"),
])
def test_agent_model_and_effort_are_explicit(agent, model, effort):
    fm = _front(ROOT / "agents" / f"{agent}.md")
    assert fm["model"] == model and fm["effort"] == effort


def test_agent_description_budget():
    total = sum(len(_front(p)["description"]) for p in (ROOT / "agents").glob("*.md"))
    assert total <= DESCRIPTION_CAP, total


def _hook_entries():
    data = json.loads((HOOKS / "hooks.json").read_text())["hooks"]
    for event, groups in data.items():
        for group in groups:
            for h in group["hooks"]:
                yield event, group.get("matcher"), h


def test_every_hook_has_a_timeout():
    for event, _, h in _hook_entries():
        assert h.get("timeout") == (10 if event == "SessionStart" else 5), (event, h["command"])


def test_new_hooks_registered():
    cmds = {(e, m, os.path.basename(h["command"].split('/hooks/')[-1].strip('"')))
            for e, m, h in _hook_entries()}
    assert ("Stop", None, "nelly_stop_capture.py") in cmds
    assert ("PreToolUse", "Write|Edit|MultiEdit", "nelly_schema_guard.py") in cmds
    assert ("PreToolUse", "Bash", "nelly_delete_guard.py") in cmds


def test_registered_hook_files_exist():
    for _, _, h in _hook_entries():
        name = h["command"].split("/hooks/")[-1].strip('"')
        assert (HOOKS / name).is_file(), name


@pytest.mark.parametrize("name", NEW_HOOKS)
def test_new_hook_is_silent_and_fails_open_on_empty_payload(name):
    r = subprocess.run([sys.executable, str(HOOKS / name)], input="{}", capture_output=True,
                       text=True, timeout=10)
    assert r.returncode == 0 and r.stdout.strip() == ""


def test_interop_documents_release5_contract():
    text = (ROOT / "INTEROP.md").read_text()
    assert "## Source evidence, staleness, capture and safe writes" in text
    for needle in ("`sources`", "`revision`", "`verified`", "`basis`", "`unknowns`", "`stale`",
                   "`stale_paths`", "`stale_since`", "pending-findings/", "conflicts/",
                   ".nelly.lock", "NELLY_CAPTURE=off", "scripts/nelly_store.py",
                   "observed | inferred | unknown"):
        assert needle in text, needle


def test_template_has_evidence_block():
    text = (ROOT / "references" / "nelly-entry.template.md").read_text()
    for key in ("sources:", "symbols:", "revision:", "verified:", "basis:", "unknowns:",
                "stale:", "stale_since:", "stale_paths:"):
        assert key in text, key


@pytest.fixture
def base(tmp_path, monkeypatch):
    monkeypatch.setattr(nelly_memory, "BASE", str(tmp_path / "mem"))
    monkeypatch.setattr(nelly_memory, "LOCAL_BASE", str(tmp_path / "mem"))
    return tmp_path


def _start(monkeypatch, capsys, cwd):
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": cwd})))
    try:
        nelly_session_start.main()
    except SystemExit:
        pass
    return json.loads(capsys.readouterr().out)["hookSpecificOutput"]["additionalContext"]


def test_session_start_includes_freshness_and_pending_lines(base, monkeypatch, capsys):
    import nelly_freshness
    import nelly_pending
    monkeypatch.setattr(nelly_freshness, "scan", lambda cwd, budget=1.5: ["STALE-LINE"])
    monkeypatch.setattr(nelly_pending, "session_hint", lambda cwd: ["PENDING-LINE"])
    ctx = _start(monkeypatch, capsys, str(base / "proj"))
    assert "STALE-LINE" in ctx and "PENDING-LINE" in ctx


def test_session_start_survives_freshness_failure(base, monkeypatch, capsys):
    import nelly_freshness

    def boom(cwd, budget=1.5):
        raise RuntimeError("x")
    monkeypatch.setattr(nelly_freshness, "scan", boom)
    assert "Agent Nelly memory" in _start(monkeypatch, capsys, str(base / "proj"))


def test_session_start_reports_conflict_count(base, monkeypatch, capsys):
    cwd = str(base / "proj")
    conflicts = Path(nelly_memory.memory_dir(cwd)) / "conflicts"
    conflicts.mkdir(parents=True)
    (conflicts / "a.20261120T000000.1.md").write_text("x")
    (conflicts / "b.20261120T000000.2.md").write_text("y")
    assert "2 memory conflicts in conflicts/" in _start(monkeypatch, capsys, cwd)
