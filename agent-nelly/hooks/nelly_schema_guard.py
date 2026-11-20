#!/usr/bin/env python3
"""PreToolUse Write|Edit|MultiEdit: deny memory-entry frontmatter that breaks the evidence/schema rules (R16).

Contract: INTEROP.md "Source evidence, staleness, capture and safe writes". For a target under
a memory store's entries/ (project entries; global entries live inline in GLOBAL-MEMORY.md, which
the guard skips, as it does MEMORY.md, index json, and research-digest, which nelly_digest_guard.py
owns) the post-edit content is computed (Write
content; Edit/MultiEdit applied to the current file) and denied when:

  - `sources` is present without `revision`, `verified` (YYYY-MM-DD) and `basis`
    (observed|inferred|unknown);
  - a `sources`/`files`/`stale_paths` path is absolute, contains a `..` segment or starts with `~`;
  - frontmatter `name` != the file stem;
  - `confidence` is missing on an error-prevention/technique entry;
  - the write adds or changes `stale`, `stale_since` or `stale_paths` (written only by
    nelly_freshness.py, cleared only by `scripts/nelly_evidence.py refresh`).

For an existing file only violations that are new relative to the current content count (a
body-only edit of a legacy non-conforming entry is allowed), except that evidence completeness is
re-checked whenever `sources` is added or changed; the stale-field rule is unchanged. A new file
is checked against every rule. An Edit whose target does not exist is treated as a Write of
new_string. Entries without `sources` (legacy) need no evidence. Everything else fails open: unparseable
frontmatter, non-memory paths, bad payloads, NELLY_GATE=off (or 0/false/disabled). The guard
never emits "allow".
"""
import json
import os
import re
import sys

_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---", re.S)
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_BASIS = ("observed", "inferred", "unknown")
_NEEDS_CONFIDENCE = ("error-prevention", "technique")
_NON_ENTRY_NAMES = ("MEMORY.md", "GLOBAL-MEMORY.md")


def _emit_deny(reason):
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse", "permissionDecision": "deny",
        "permissionDecisionReason": "Agent Nelly schema guard: " + reason}}))
    sys.exit(0)


def no_decision():
    sys.exit(0)


def _read(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return None


def _apply_edits(text, edits):
    """Apply [(old, new, replace_all)] in order; None when an old_string isn't found."""
    for old, new, replace_all in edits:
        if not old and text == "":
            text = new  # Edit creating a missing/empty file
            continue
        if not old or old not in text:
            return None
        text = text.replace(old, new) if replace_all else text.replace(old, new, 1)
    return text


def _post_edit_content(tool, tool_input, path):
    if tool == "Write":
        content = tool_input.get("content")
        return content if isinstance(content, str) else None
    current = _read(path)
    if current is None:
        current = ""  # missing target: an empty old_string creates it (a Write of new_string)
    if tool == "Edit":
        edits = [(tool_input.get("old_string"), tool_input.get("new_string", ""),
                  bool(tool_input.get("replace_all")))]
    else:
        raw = tool_input.get("edits")
        if not isinstance(raw, list):
            return None
        edits = [(e.get("old_string"), e.get("new_string", ""), bool(e.get("replace_all")))
                 for e in raw if isinstance(e, dict)]
    return _apply_edits(current, edits)


_CWD = None  # the payload cwd, set by main(); deny commands use its git toplevel as --cwd


def _cmd(sub, slug):
    """Runnable nelly_evidence.py command for deny text: absolute path, data-dir env prefix, quoted
    args (CLAUDE_PLUGIN_ROOT/DATA are unset in the model's Bash). Falls back to the plain name."""
    try:
        import nelly_pending
        import shared_slug
        repo = shared_slug.repo_root(_CWD) if _CWD else "<repo root>"
        extra = (["--type", "<type>", "--description", "<description>", "--body", "<body>",
                  "--paths", "<path>", "--basis", "observed"] if sub == "record" else ["--paths", "<path>"])
        return nelly_pending._cmd("scripts/nelly_evidence.py", sub, "--cwd", repo,
                                  "--slug", slug, *extra)
    except Exception:
        return f"scripts/nelly_evidence.py {sub}"


def _stale_fields(bi, block):
    rec = bi.parse_evidence(block)
    return tuple((k, rec.get(k)) for k in ("stale", "stale_since", "stale_paths", "stale_digest"))


def violations(bi, block, stem, exists=False):
    """{key: message} of name/confidence/path/evidence-completeness violations in one block.
    `exists`: the entry file already exists, so `record` (which only creates) is not prescribed."""
    out = {}
    name_m = bi._NAME_RE.search(block)
    if name_m and bi._scalar(name_m.group(1)) != stem:
        out[("name",)] = (f"frontmatter name '{bi._scalar(name_m.group(1))}' must equal the file name "
                          f"'{stem}'. Fix the name or the file name.")
    type_m = bi._TYPE_RE.search(block)
    entry_type = type_m.group(1).strip() if type_m else None
    if entry_type in _NEEDS_CONFIDENCE and not bi._CONFIDENCE_RE.search(block):
        out[("confidence",)] = f"a {entry_type} entry requires metadata.confidence (explicit or inferred)."
    rec = bi.parse_evidence(block)
    if "sources" in rec:
        for field, bad in (("revision", not rec.get("revision")),
                           ("verified", not _DATE_RE.match(rec.get("verified") or "")),
                           ("basis", rec.get("basis") not in _BASIS)):
            if bad:
                fix = (f"Add the missing field(s) in this same edit, or once the sources are verified "
                       f"run `{_cmd('refresh', stem)}`." if exists
                       else f"Fill evidence with `{_cmd('record', stem)}`.")
                out[("missing", field)] = (
                    f"`sources` is present, so {field} must also be set under metadata "
                    f"(verified: YYYY-MM-DD; basis: observed|inferred|unknown). {fix}")
    paths = [s["path"] for s in rec.get("sources", [])]
    paths += bi._inline_list(block, "files") or []
    paths += rec.get("stale_paths") or []
    for p in paths:
        if not bi.is_repo_relative(p):
            out[("path", p)] = (f"path '{p}' in sources/files/stale_paths must be repo-relative: no "
                                f"leading '/', '~', or '..' segments.")
    return out


def check(bi, block, stem, old_block):
    """Return a denial reason or None."""
    new_v = violations(bi, block, stem, exists=old_block is not None)
    if old_block is None:
        if new_v:
            return next(iter(new_v.values()))
    else:
        old_v = violations(bi, old_block, stem)
        old_rec, new_rec = bi.parse_evidence(old_block), bi.parse_evidence(block)
        sources_changed = old_rec.get("sources") != new_rec.get("sources")
        for key, msg in new_v.items():
            if key not in old_v or (sources_changed and key[0] == "missing"):
                return msg
    old = _stale_fields(bi, old_block) if old_block is not None else _stale_fields(bi, "")
    if _stale_fields(bi, block) != old:
        return ("stale, stale_since, stale_paths and stale_digest are written only by the freshness hook and "
                f"cleared only by `{_cmd('refresh', stem)}`; do not add, change or remove them by hand.")
    return None


def main():
    if os.environ.get("NELLY_GATE", "").lower() in ("off", "0", "false", "disabled"):
        no_decision()
    try:
        payload = json.load(sys.stdin)
        tool = payload.get("tool_name")
        if tool not in ("Write", "Edit", "MultiEdit"):
            no_decision()
        tool_input = payload.get("tool_input") or {}
        file_path = tool_input.get("file_path") or tool_input.get("path") or ""
        if not file_path or not file_path.endswith(".md"):
            no_decision()
        cwd = payload.get("cwd") or os.getcwd()
        global _CWD
        _CWD = cwd
        norm = os.path.normpath(file_path if os.path.isabs(file_path) else os.path.join(cwd, file_path))

        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from nelly_memory import BASE, LOCAL_BASE, DIGEST_SUBDIR
        if not any(norm.startswith(os.path.normpath(b) + os.sep) for b in (BASE, LOCAL_BASE)):
            no_decision()  # cheap prefix check: nothing below runs for non-memory paths
        if (os.path.basename(norm) in _NON_ENTRY_NAMES
                or os.sep + "entries" + os.sep not in norm
                or os.sep + os.path.join("entries", DIGEST_SUBDIR) + os.sep in norm):
            no_decision()

        new_text = _post_edit_content(tool, tool_input, norm)
        if new_text is None:
            no_decision()
        m = _FRONTMATTER_RE.search(new_text) if new_text.startswith("---\n") else None
        if not m:
            no_decision()

        sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
        import build_index as bi
        block = m.group(1)
        type_m = bi._TYPE_RE.search(block)
        if type_m and type_m.group(1).strip() == "research-digest":
            no_decision()

        old_text = _read(norm)
        old_m = _FRONTMATTER_RE.search(old_text) if old_text and old_text.startswith("---\n") else None
        reason = check(bi, block, os.path.basename(norm)[:-3], old_m.group(1) if old_m else None)
    except SystemExit:
        raise
    except Exception:
        no_decision()  # fail open
    if reason:
        _emit_deny(reason)
    no_decision()


if __name__ == "__main__":
    main()
