"""continue-protocol.md describes the implemented resume behavior (baseline diff, carried-forward
research labels, resume_context injection, rollback_pending)."""
import sys
from pathlib import Path

HOOKS = Path(__file__).resolve().parent.parent / "hooks"
sys.path.insert(0, str(HOOKS))
import resume_context  # noqa: E402

DOC = (Path(__file__).resolve().parent.parent / "skills" / "spec-driven-development"
       / "references" / "continue-protocol.md")
TEXT = DOC.read_text(encoding="utf-8")
LOW = TEXT.lower()


def test_registry_triggers_stay_in_first_five_lines():
    head = "\n".join(TEXT.splitlines()[:5])
    assert "Read by" in head
    assert "continue" in head and "Rollback Request Check" in head


def test_baseline_diff_documented():
    for t in ("baseline", "branch_changed", "head_moved", "files_changed", "incomplete"):
        assert t in TEXT, t


def test_carried_forward_labels_documented():
    for t in ("still-applicable", "needs-recheck", "unknown", "research/cache.md"):
        assert t in TEXT, t


def test_resume_context_injection_documented():
    for t in ("resume_context", "UserPromptSubmit", "additionalContext", "intent_hash_repro",
              "fail"):
        assert t in TEXT, t


def test_rollback_pending_documented():
    assert "rollback_pending" in TEXT
    assert "/isdd-rewind" in TEXT


def test_original_steps_kept():
    for t in ("workflow-manager", "nelly_brief_cache", "Do not restart from Requirements"):
        assert t in TEXT, t


def test_doc_tied_to_resume_context_code():
    out = resume_context.format_context(
        {"files_changed": ["a"]},
        {"still_applicable": [{"path": "x"}], "needs_recheck": [{"path": "y"}],
         "unknown": [{"path": "z"}]},
        None, None, "slug")
    assert "SDD resume context" in out and "SDD resume context" in TEXT
    for label in ("still-applicable", "needs-recheck", "unknown"):
        assert "research %s:" % label in out
        assert label in TEXT
    assert "%ds is the hook's total budget" % int(resume_context.TOTAL_BUDGET_S) in TEXT
    unk = [ln for ln in TEXT.splitlines() if ln.lstrip().startswith("- `unknown`")][0]
    assert "Treat as needs-recheck" in unk


def test_incomplete_and_intent_clearing_documented():
    assert "git failure" in TEXT and "no changes" in TEXT
    assert "clean now" in TEXT
    assert "remove" in TEXT and "intent_hash_repro" in TEXT
    assert "min(1.5s" in TEXT and "0.5s" in TEXT
