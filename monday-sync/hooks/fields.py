"""Shared workflow-state.md field parser (stdlib only; used by planner and the hooks)."""
import os
import re

_FIELD = re.compile(r"^\s*[-*]\s*([A-Za-z][A-Za-z /]+?):\s*(.*\S)?\s*$")
_CONTINUATION = re.compile(r"^\s{2,}(\S.*)$")


def parse_fields(text):
    """`- Field: value` lines as {lowercased field: value}; first occurrence wins; indented
    continuation lines join the previous field (same semantics as agent-isdd plan_board.py)."""
    fields = {}
    current = None
    for line in text.splitlines():
        m = _FIELD.match(line)
        if m:
            key = m.group(1).strip().lower()
            current = key if key not in fields else None
            if current:
                fields[current] = (m.group(2) or "").strip()
            continue
        cont = _CONTINUATION.match(line)
        if cont and current:
            fields[current] = (fields[current] + " " + cont.group(1).strip()).strip()
        else:
            current = None
    return fields



STATE_FILE = "workflow-state.md"


def read_fields(feature_dir):
    """parse_fields of <feature_dir>/workflow-state.md; {} when it can't be read."""
    try:
        with open(os.path.join(feature_dir, STATE_FILE), "r", encoding="utf-8") as fh:
            return parse_fields(fh.read())
    except OSError:
        return {}


def feature_title(feature_dir, fields=None):
    """The feature's Title, else its folder name."""
    fields = read_fields(feature_dir) if fields is None else fields
    return fields.get("title") or os.path.basename(os.path.normpath(feature_dir))
