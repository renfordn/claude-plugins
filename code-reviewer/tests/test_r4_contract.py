"""Release 4 slice 0 contract: agent models, description budget, report markers, findings schema,
headless model pass-through."""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import review_plan  # noqa: E402

# Always-loaded text before release 4 (2 skills + 2 agents): 2127 chars. Release 4 adds two skills
# and one agent; trimmed agent descriptions must make room so the total stays under this cap.
TOTAL_DESCRIPTION_CAP = 2450
MODELS = {"code-reviewer": ("opus", "high"), "finding-verifier": ("opus", "medium"),
          "bug-investigator": ("opus", "medium")}
MARKERS = ("<!--FEATURE-FINDER-REPORT-->", "<!--BUG-INVESTIGATION-REPORT-->",
           "<!--FINDING-RECHECK-REPORT-->", "<!--PRE-PUSH-REVIEW-->")


def _fm(path):
    return path.read_text().split("---", 2)[1]


def _desc(path):
    fm = _fm(path)
    m = re.search(r"^description:\s*(?:>-?|\|)?\s*\n((?:[ \t]+.*\n)+)", fm, re.M)
    if m:
        return " ".join(l.strip() for l in m.group(1).splitlines())
    return re.search(r"^description:\s*(.*)$", fm, re.M).group(1).strip().strip('"')


def _items():
    return sorted(ROOT.glob("skills/*/SKILL.md")) + sorted(ROOT.glob("agents/*.md"))


def test_agent_models_and_effort_are_explicit():
    for path in ROOT.glob("agents/*.md"):
        name = path.stem
        assert name in MODELS, f"{name}: add it to MODELS"
        model, effort = MODELS[name]
        fm = _fm(path)
        assert re.search(rf"^model:\s*{model}\s*$", fm, re.M), name
        assert re.search(rf"^effort:\s*{effort}\s*$", fm, re.M), name


def test_agent_descriptions_lean():
    for path in ROOT.glob("agents/*.md"):
        d = _desc(path)
        assert d.startswith("Use this agent when"), path.name
        assert "<example>" not in d, path.name


def test_total_description_budget():
    total = sum(len(_desc(p)) for p in _items())
    assert total <= TOTAL_DESCRIPTION_CAP, total


def test_every_agent_is_read_only_and_only_the_reviewer_ends_in_code_reviewer():
    for path in ROOT.glob("agents/*.md"):
        tools = re.search(r"^tools:\s*(.*)$", _fm(path), re.M).group(1)
        for banned in ("Edit", "Write", "NotebookEdit", "Agent"):
            assert banned not in [t.strip() for t in tools.split(",")], (path.name, banned)
        if path.stem != "code-reviewer":
            assert not path.stem.endswith("code-reviewer"), path.name


def test_interop_documents_release4_markers():
    text = (ROOT / "INTEROP.md").read_text()
    for m in MARKERS:
        assert m in text, m


def test_verifier_has_recheck_mode():
    text = (ROOT / "agents" / "finding-verifier.md").read_text()
    assert "<!--FINDING-RECHECK-REPORT-->" in text
    for outcome in ("resolved", "still-open", "partially-resolved", "needs-detailed-review"):
        assert outcome in text
    assert "hypothes" in text.lower()


def test_reviewer_reuses_finding_ids():
    text = (ROOT / "agents" / "code-reviewer.md").read_text()
    assert "reuse" in text.lower() and "findings.json" in text


def test_findings_resolution_and_id_validated():
    base = {"scope": "s", "level": "Standard", "followups": [], "findings": [{
        "id": "F1", "file": "a.py", "summary": "x", "failure_scenario": "y", "severity": "low",
        "decision": "flag", "category": "correctness", "workflow_action": "proceed",
        "confidence": "high", "evidence_tier": "tier-1", "resolution": "declined"}]}
    assert review_plan.validate(base) == []
    bad = json.loads(json.dumps(base))
    bad["findings"][0]["resolution"] = "ignored"
    assert any("resolution" in e for e in review_plan.validate(bad))
    bad = json.loads(json.dumps(base))
    bad["findings"][0]["id"] = "finding one"
    assert any(".id" in e for e in review_plan.validate(bad))


def test_skill_example_has_resolution_and_mode_pointers():
    text = (ROOT / "skills" / "code-reviewer" / "SKILL.md").read_text()
    assert '"resolution"' in text
    assert "references/recheck.md" in text and "references/pre-push.md" in text


def test_headless_passes_declared_model(tmp_path):
    fake = tmp_path / "claude"
    fake.write_text('#!/usr/bin/env bash\nprintf "%s\\n" "$@"\n')
    fake.chmod(0o755)
    env = {**os.environ, "PATH": f"{tmp_path}:{os.environ['PATH']}"}
    out = subprocess.run(["bash", str(ROOT / "scripts" / "review_headless.sh"), "--agent",
                          "finding-verifier", "brief"], capture_output=True, text=True, env=env)
    assert out.returncode == 0, out.stderr
    args = out.stdout.splitlines()
    assert "--model" in args and args[args.index("--model") + 1] == "opus"


def test_first_class_declares_hooks_present():
    data = json.loads((ROOT / ".claude-plugin" / "first-class.json").read_text())
    assert "hooks" not in data.get("declared_absent", [])


def test_contract_amendments_after_slice0_review():
    interop = (ROOT / "INTEROP.md").read_text()
    for needle in ("pre-push.json", "recheck.json", "unscoped review", "SubagentStop", "H1", "first line"):
        assert needle in interop, needle
    hooks = json.loads((ROOT / "hooks" / "hooks.json").read_text())["hooks"]
    assert any("pre_push_offer.py" in h["command"] for e in hooks.get("SubagentStop", []) for h in e["hooks"])
    verifier = (ROOT / "agents" / "finding-verifier.md").read_text()
    assert "Previous evidence:" in verifier and "```json" in verifier.split("Re-check", 1)[1]


def test_validate_rejects_duplicate_and_trailing_ids():
    f = {"file": "a.py", "summary": "x", "failure_scenario": "y", "severity": "low", "decision": "flag",
         "category": "correctness", "workflow_action": "proceed", "confidence": "high", "evidence_tier": "tier-1"}
    doc = {"scope": "s", "level": "Standard", "followups": [],
           "findings": [dict(f, id="F2"), dict(f, id="F2")]}
    assert any("duplicate" in e for e in review_plan.validate(doc))
    doc["findings"] = [dict(f, id="F1\n")]
    assert any(".id" in e for e in review_plan.validate(doc))


def test_headless_inherit_adds_no_model(tmp_path):
    root = tmp_path / "plugin"
    (root / "agents").mkdir(parents=True)
    (root / "scripts").mkdir()
    (root / "scripts" / "review_headless.sh").write_text((ROOT / "scripts" / "review_headless.sh").read_text())
    (root / "agents" / "x-agent.md").write_text("---\nname: x-agent\nmodel: inherit\n---\nbody\n")
    fake = tmp_path / "claude"
    fake.write_text('#!/usr/bin/env bash\nprintf "%s\\n" "$@"\n')
    fake.chmod(0o755)
    env = {**os.environ, "PATH": f"{tmp_path}:{os.environ['PATH']}"}
    out = subprocess.run(["bash", str(root / "scripts" / "review_headless.sh"), "--agent", "x-agent", "b"],
                         capture_output=True, text=True, env=env)
    assert out.returncode == 0, out.stderr
    assert "--model" not in out.stdout.splitlines()
