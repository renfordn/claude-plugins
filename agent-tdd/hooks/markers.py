"""Shared marker/regex contract for slice ids and review scopes."""
import re

ID = r"\d+[A-Za-z0-9]*"
SLICE_TITLE_RE = re.compile(r"^[\s#>*-]*Slice\s+(" + ID + r")\s*:", re.IGNORECASE)
SLICE_ID_MARKER_RE = re.compile(r"<!--\s*SLICE-ID:\s*(" + ID + r")\s*-->")
_PROSE_RE = re.compile(r"\bSlice\s+(" + ID + r")\b")
REVIEW_SCOPE_RE = re.compile(r"<!--\s*REVIEW-SCOPE:\s*slice=(" + ID + r")\s*-->")
_SCOPE_LIST = ID + r"(?:[ \t]*,[ \t]*" + ID + r")*"
# One review may cover several slices (`slice=2,3`); a report may carry several markers.
REVIEW_SCOPES_RE = re.compile(r"<!--\s*REVIEW-SCOPE:\s*slice=(" + _SCOPE_LIST + r")\s*-->")


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


def parse_review_scopes(text):
    """Every slice id named by REVIEW-SCOPE markers (lists and repeated markers), normalized, in order.
    Mirrors agent-isdd's isdd_markers.parse_review_scopes."""
    out = []
    for m in REVIEW_SCOPES_RE.finditer(text or ""):
        for raw in m.group(1).split(","):
            sid = normalize_slice_id(raw.strip())
            if sid and sid not in out:
                out.append(sid)
    return out


# Release 3 contract (R7/R9/R11): evidence phases and report outcome markers.
EVIDENCE_PHASES = ("red", "green", "integration", "start", "coverage", "bypass", "done")
OUTCOME_RE = re.compile(r"<!--\s*AGENT-TDD-OUTCOME:\s*([A-Za-z][A-Za-z-]*)\s*-->")
BLOCKED_RE = re.compile(
    r"<!--\s*AGENT-TDD-BLOCKED(?:\s*:\s*(?:reason\s*=\s*(?:\"([^\"]*)\"|'([^']*)'|([^\s>-][^>]*?)))?)?\s*-->")
# Printed by scripts/tdd_check.py, parsed by hooks/tdd_subagent_stop.py. Phases without a command
# (start, bypass, done) omit `exit=`.
EVIDENCE_LINE_RE = re.compile(
    r"TDD-EVIDENCE (?P<phase>" + "|".join(EVIDENCE_PHASES) + r") (?P<token>[0-9a-f]{8})"
    r"(?: exit=(?P<exit>-?\d+))? (?P<status>CONFIRMED|NOT CONFIRMED)")


def format_evidence_line(phase, token, code, confirmed, note=""):
    """The single printed evidence format (see references/evidence-log.md)."""
    status = "CONFIRMED" if confirmed else f"NOT CONFIRMED ({note})"
    exit_part = "" if code is None else f" exit={code}"
    return f"TDD-EVIDENCE {phase} {token}{exit_part} {status}"


def parse_outcome(text):
    """'coverage-only' etc. (lower-cased) from <!--AGENT-TDD-OUTCOME: ...-->, or None."""
    m = OUTCOME_RE.search(text or "")
    return m.group(1).lower() if m else None


def parse_blocked(text):
    """The reason from <!--AGENT-TDD-BLOCKED: reason="..."--> ("" when absent or empty), or None
    when there is no BLOCKED marker. Callers must test `is not None`."""
    m = BLOCKED_RE.search(text or "")
    if not m:
        return None
    return next((g for g in m.groups() if g is not None), "").strip()
