"""Shared marker/regex contract for slice ids and review scopes."""
import re

ID = r"\d+[A-Za-z0-9]*"
SLICE_TITLE_RE = re.compile(r"^[\s#>*-]*Slice\s+(" + ID + r")\s*:", re.IGNORECASE)
SLICE_ID_MARKER_RE = re.compile(r"<!--\s*SLICE-ID:\s*(" + ID + r")\s*-->")
_PROSE_RE = re.compile(r"\bSlice\s+(" + ID + r")\b")
REVIEW_SCOPE_RE = re.compile(r"<!--\s*REVIEW-SCOPE:\s*slice=(" + ID + r")\s*-->")


def normalize_slice_id(n):
    """Canonical form for comparisons (parse_slice_id/parse_review_scope keep the raw case,
    pinned by test_contract_slice0; parse_slice_id_strict returns this form): letters upper-cased ('2f2' -> '2F2')."""
    return n.upper() if n else n


def _section_text(report, header):
    """Extract text under a **Header** section, up to the next **Header** or end."""
    pattern = re.compile(
        r"\*\*" + re.escape(header) + r"\*\*\s*(.*?)(?=\*\*[^*]|\Z)",
        re.DOTALL,
    )
    m = pattern.search(report)
    return m.group(1).strip() if m else ""


_PLAN_HEADING_RE = re.compile(r"^#+\s*Plan\s*$\s*(.*?)(?=^#+\s|\Z)", re.MULTILINE | re.DOTALL)


def _first_line(block, skip_comments=False):
    for ln in block.splitlines():
        st = ln.strip()
        if not st or (skip_comments and st.startswith("<!--")):
            continue
        return ln
    return None


def parse_slice_id_strict(text):
    """Slice id safe to key state on. An explicit <!--SLICE-ID: N--> marker wins. Otherwise
    the id comes ONLY from a 'Slice N:' title on the first line examined, then we stop: the
    first non-blank line of the **Plan** / '## Plan' section if present, else the first
    non-blank, non-HTML-comment line of the report. A later title line or a prose mention
    ("reusing Slice 1's helper") never yields an id. Returns None otherwise."""
    text = text or ""
    m = SLICE_ID_MARKER_RE.search(text)
    if m:
        return normalize_slice_id(m.group(1))
    plan = _section_text(text, "Plan")
    if not plan:
        h = _PLAN_HEADING_RE.search(text)
        plan = h.group(1).strip() if h else ""
    line = _first_line(plan) if plan else _first_line(text, skip_comments=True)
    t = SLICE_TITLE_RE.match(line) if line else None
    return normalize_slice_id(t.group(1)) if t else None


def parse_slice_id(text):
    """Display-only: marker, else the first bare 'Slice N' anywhere (prose fallback).
    Do NOT key state on this; use parse_slice_id_strict."""
    text = text or ""
    m = SLICE_ID_MARKER_RE.search(text) or _PROSE_RE.search(text)
    return m.group(1) if m else None


def scope_marker(n):
    return "<!--REVIEW-SCOPE: slice=%s-->" % n


def parse_review_scope(text):
    m = REVIEW_SCOPE_RE.search(text or "")
    return m.group(1) if m else None
