"""Release 4 docs: agent-isdd must not mistake R4 reports for slice reviews."""
from pathlib import Path

DOC = (Path(__file__).resolve().parents[1] / "references" / "interop-reviewers.md").read_text()


def test_recheck_is_not_a_slice_review():
    assert "`<!--FINDING-RECHECK-REPORT-->` is not a slice review and is never recorded in the `reviewed` map" in DOC


def test_declined_prepush_fix_is_not_a_fallback_or_followup():
    flat = " ".join(DOC.split())
    assert "(`pre-push.json` status `declined`)" in flat and "`resolution: declined`" in flat
    assert ("neither is ever a Review Fallback, `decision: accept` or a `deferred-defect` "
            "follow-up") in flat


def test_prepush_counts_as_unscoped_review():
    assert "The pre-push review (`<!--PRE-PUSH-REVIEW-->`) counts as an unscoped review" in DOC
