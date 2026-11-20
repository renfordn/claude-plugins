"""The one place that edits Agent Nelly memory-entry frontmatter lines (freshness hook, evidence CLI).

Operates on a list of lines (with or without line endings; new lines copy the neighbouring line's
ending) so every line it does not touch stays byte-identical. Keys are edited only inside the
`metadata:` block, at the block's child indent: the indent of its first non-blank, non-comment line.
"""
import hashlib
import re

_YAML_AMBIGUOUS = {"true", "false", "yes", "no", "on", "off", "y", "n", "null", "~"}
_META_RE = re.compile(r"^metadata:[ \t]*(#.*)?\r?\n?$")
_PLAIN_RE = re.compile(r"[A-Za-z0-9_./@+=~-]+")
_ITEM_RE = re.compile(r"^[ \t]*-(?:[ \t]|\r?\n?$)")


def quote(value):
    """Plain scalar when safe (only [A-Za-z0-9_./@+=~-]), else double-quoted, escaping backslash and
    quote, so build_index's inline-list parser round-trips it."""
    value = str(value)
    if _PLAIN_RE.fullmatch(value):
        return value
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def unquote(value):
    """Strip whitespace and one pair of matching surrounding quotes from a frontmatter scalar; inside
    double quotes an escaped backslash or quote is unescaped (the inverse of quote/quote_always)."""
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
        q = value[0]
        value = value[1:-1]
        if q == '"':
            value = re.sub(r'\\(["\\])', r"\1", value)
    return value


def read_scalar(block, key):
    """The unquoted first-line value of top-level `key:` in a frontmatter block, or None."""
    m = re.search(r"^" + re.escape(key) + r":[ \t]*(\S.*)$", block, re.M)
    return unquote(m.group(1)) if m else None


def reject_placeholder(flag, value):
    """Raise ValueError when `value` is still `<placeholder>` text (callers turn it into their exit)."""
    v = (value or "").strip()
    if v.startswith("<") and v.endswith(">"):
        raise ValueError(f"{flag} is still the placeholder text {v!r}; supply the real value")


def quote_always(value):
    """Always double-quoted (backslash and quote escaped): valid YAML for any one-line text, and
    build_index._scalar unquotes it."""
    return '"' + str(value).replace("\\", "\\\\").replace('"', '\\"') + '"'


def name_scalar(slug):
    """A kebab slug as a YAML scalar: plain, unless YAML would read it as a bool, null or number."""
    s = str(slug)
    return quote_always(s) if s.lower() in _YAML_AMBIGUOUS or s.replace("-", "").isdigit() else s


def content_digest(text):
    """SHA-1 of an entry's `description:` line and its body (the text after the frontmatter): what
    a reader has to rewrite when a recorded fact stops being true."""
    m = re.match(r"^---\r?\n(.*?)\r?\n---[ \t]*\r?\n?(.*)$", text, re.S)
    if not m:
        return hashlib.sha1(text.encode("utf-8")).hexdigest()
    desc = re.search(r"^description:[ \t]*(.*)$", m.group(1), re.M)
    payload = (desc.group(1).strip() if desc else "") + "\n" + m.group(2).strip()
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def flow_list(items):
    return "[" + ", ".join(quote(i) for i in items) + "]"


def _indent(line):
    return len(line.expandtabs()) - len(line.expandtabs().lstrip())


def _skippable(line):
    """Blank or comment-only line."""
    s = line.strip()
    return not s or s.startswith("#")


def _eol(line):
    return "\r\n" if line.endswith("\r\n") else "\n" if line.endswith("\n") else ""


def key_extent(lines, key, start=0, end=None, indent=None):
    """(first, end_exclusive, indent_str) of `key` and its continuation, or None. The continuation is
    every following line indented deeper than the key, plus same-indent `- ` items when the key has
    no inline value; blank and comment lines are included only when a continuation follows them.
    `indent` (an int) restricts the match to keys at exactly that indent."""
    end = len(lines) if end is None else end
    key_re = re.compile(r"^([ \t]*)" + re.escape(key) + r":(.*)$")
    for i in range(start, end):
        m = key_re.match(lines[i].rstrip("\r\n"))
        if not m:
            continue
        ci = _indent(lines[i])
        if indent is not None and ci != indent:
            continue
        inline = bool(m.group(2).strip()) and not m.group(2).strip().startswith("#")
        last = i
        for j in range(i + 1, end):
            line = lines[j]
            if _skippable(line):
                continue
            ind = _indent(line)
            if ind > ci or (ind == ci and not inline and _ITEM_RE.match(line)):
                last = j
            else:
                break
        return i, last + 1, m.group(1)
    return None


def _metadata_span(lines):
    """(meta_index, last_content_index, child_indent_str) or None. The block runs to the next
    non-comment line at column 0; trailing blank/comment lines are not part of its content."""
    meta = next((i for i, ln in enumerate(lines) if _META_RE.match(ln)), None)
    if meta is None:
        return None
    last = meta
    for i in range(meta + 1, len(lines)):
        line = lines[i]
        if not line.strip():
            continue
        if line[0] in " \t":
            last = i  # indented content or comment
        elif not line.startswith("#"):
            break
    first = next((i for i in range(meta + 1, last + 1) if not _skippable(lines[i])), None)
    indent = lines[first][:len(lines[first]) - len(lines[first].lstrip())] if first is not None else "  "
    return meta, last, indent


def set_key(lines, key, value, anchor=None):
    """Set `key: value` inside `metadata:` in place (value None removes the key). An existing key is
    replaced across its whole extent; a new one goes after the `anchor` key's extent, or at the end
    of the block when no anchor is given. Raises ValueError when there is no `metadata:` block or the
    anchor key is absent."""
    span = _metadata_span(lines)
    if span is None:
        raise ValueError("frontmatter has no metadata: block")
    meta, last, indent = span
    ci = len(indent.expandtabs())
    ext = key_extent(lines, key, meta + 1, last + 1, ci)
    if ext:
        s, e, ind = ext
        ref = lines[e - 1]
        lines[s:e] = [] if value is None else [f"{ind}{key}: {value}{_eol(ref)}"]
        return
    if value is None:
        return
    if anchor is not None:
        a = key_extent(lines, anchor, meta + 1, last + 1, ci)
        if not a:
            raise ValueError(f"no '{anchor}' key to anchor '{key}'")
        at = a[1]
    else:
        at = last + 1
    lines.insert(at, f"{indent}{key}: {value}{_eol(lines[at - 1])}")
