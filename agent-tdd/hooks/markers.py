"""Shared marker/regex contract for slice ids and review scopes."""
import re

ID = r"\d+[A-Za-z]*"
SLICE_TITLE_RE = re.compile(r"^[\s#>*-]*Slice\s+(" + ID + r")\s*:", re.IGNORECASE)
_MARKER_RE = re.compile(r"<!--\s*SLICE-ID:\s*(" + ID + r")\s*-->")
_PROSE_RE = re.compile(r"\bSlice\s+(" + ID + r")\b")
REVIEW_SCOPE_RE = re.compile(r"<!--\s*REVIEW-SCOPE:\s*slice=(" + ID + r")\s*-->")


def parse_slice_id(text):
    """Explicit <!--SLICE-ID: N--> marker wins; else the first bare 'Slice N'."""
    text = text or ""
    m = _MARKER_RE.search(text) or _PROSE_RE.search(text)
    return m.group(1) if m else None


def scope_marker(n):
    return "<!--REVIEW-SCOPE: slice=%s-->" % n


def parse_review_scope(text):
    m = REVIEW_SCOPE_RE.search(text or "")
    return m.group(1) if m else None
