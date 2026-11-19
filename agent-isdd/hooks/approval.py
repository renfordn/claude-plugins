#!/usr/bin/env python3
"""approval hook: PostToolUse ExitPlanMode. On a real approval during the Design phase it records
`Implementation Requested: Yes` and `Approval Pending: yes` (no hash: design.md is persisted after
ExitPlanMode). freeze(spec_dir) later records the `Approval Hash` over requirements.md + design.md
at the first agent-TDD spawn (security-relevant gate input: verify() detects scope edits made
after approval). design_spec_gate (PreToolUse) calls freeze() -- a deliberate state write from a
PreToolUse hook; the CLI below is the recovery path after a mismatch:
  approval.py refreeze <spec_dir>   clear + re-freeze the hash from current requirements/design
  approval.py approve <spec_dir>    set Implementation Requested: Yes + Approval Pending: yes No active workflow or any failure: exit 0, no output (fail open).

approval_hash(requirements_text, design_text) -- the parameter slots keep the contract stub's
positional order; callers pass requirements.md then design.md text.
"""
import contextlib
import hashlib
import json
import os
import re
import sys
import tempfile

try:
    import fcntl
except ImportError:
    fcntl = None

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
if __name__ == "__main__" and len(sys.argv) > 1 and not os.environ.get("CLAUDE_PLUGIN_DATA"):
    # CLI use: the sdd_state import below would traceback without it; fail with the clear message.
    from path_resolution import PluginDataDirUnavailable, get_plugin_data_dir
    try:
        get_plugin_data_dir("agent-isdd")
    except PluginDataDirUnavailable as _e:
        print(str(_e), file=sys.stderr)
        sys.exit(1)
from sdd_state import active_state_file, match_field, parse_state, update_json  # noqa: E402


def _norm(text):
    return (text or "").replace("\r\n", "\n").replace("\r", "\n")


def approval_hash(requirements_text, design_text):
    """Deterministic sha256 hex over both texts (line endings normalised, length-framed so the
    boundary between them is unambiguous)."""
    h = hashlib.sha256()
    for part in (_norm(requirements_text), _norm(design_text)):
        data = part.encode("utf-8")
        h.update(str(len(data)).encode("ascii") + b":" + data + b"\n")
    return h.hexdigest()


def _yes(v):
    return str(v).strip().lower() in ("yes", "true")


_HEX64 = re.compile(r"^[0-9a-f]{64}$")


def _hash_or_blank(v):
    """Lowercased value when it is exactly 64 hex chars, else '' (placeholders such as 'None'
    or template text count as no hash)."""
    v = str(v or "").strip().lower()
    return v if _HEX64.match(v) else ""


def verify(fields, requirements_text, design_text, json_fields=None):
    """ok | pending | missing | mismatch | legacy.
    legacy: neither the md fields nor the json mirror carry an approval hash and no approval is
    pending (approved before hashing existed). pending: approval recorded but hash not yet frozen.
    mismatch: recorded hash differs from current content, md/json hashes disagree, or the json has
    a hash the md lost. missing: Approval Hash field present but blank (nothing else recorded)."""
    fields = fields if isinstance(fields, dict) else {}
    jf = json_fields if isinstance(json_fields, dict) else {}
    md_hash = _hash_or_blank(fields.get("approval hash"))
    js_hash = _hash_or_blank(jf.get("approval_hash"))
    if not md_hash and not js_hash:
        if _yes(fields.get("approval pending", "")) or _yes(jf.get("approval_pending", "")):
            return "pending"
        return "missing" if "approval hash" in fields else "legacy"
    if js_hash and (not md_hash or md_hash != js_hash):
        return "mismatch"
    return "ok" if md_hash == approval_hash(requirements_text, design_text) else "mismatch"


def _read(path):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return ""


def _set_fields(text, updates):
    """Replace (first occurrence) or append `- Key: value` lines; later duplicates are dropped."""
    seen = set()
    out = []
    for line in text.splitlines():
        m = match_field(line)
        key = m[0] if m else None
        if key in updates:
            if key in seen:
                continue
            seen.add(key)
            label = re.match(r"^\s*[-*]?\s*([A-Za-z][A-Za-z /]+?):", line).group(1)
            out.append("- %s: %s" % (label, updates[key]))
        else:
            out.append(line)
    for key, val in updates.items():
        if key not in seen:
            out.append("- %s: %s" % (key.title(), val))
    return "\n".join(out) + "\n"


@contextlib.contextmanager
def _locked(path):
    lock = None
    try:
        if fcntl is not None:
            lock = open(path + ".lock", "a")
            fcntl.flock(lock, fcntl.LOCK_EX)
        yield
    finally:
        if lock is not None:
            lock.close()


def _atomic_write(path, text):
    """Locked (same `<path>.lock` flock as update_json), mode-preserving atomic replace."""
    with _locked(path):
        try:
            mode = os.stat(path).st_mode & 0o777
        except OSError:
            mode = 0o644
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), prefix=".wsmd.")
        try:
            os.fchmod(fd, mode)
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(text)
            os.replace(tmp, path)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise


def _record(state_md, md_updates, json_updates):
    _atomic_write(state_md, _set_fields(_read(state_md), md_updates))
    json_path = os.path.join(os.path.dirname(state_md), "workflow-state.json")
    if os.path.isfile(json_path):
        update_json(json_path, lambda d: dict(d, **json_updates))


def _approved(response):
    """True when an ExitPlanMode tool_response is present and shows no error/rejection."""
    if not response:
        return False
    if isinstance(response, dict):
        if response.get("is_error") or response.get("isError") or response.get("error"):
            return False
        return True
    text = str(response).lower()
    return not any(w in text for w in (
        "error", "reject", "denied", "doesn't want to proceed", "did not approve", "not approved"))


def _current_state(spec_dir):
    return os.path.join(spec_dir, "workflow-state.md")


def evaluate(payload):
    """PostToolUse ExitPlanMode: on a real approval during Design, record Implementation Requested
    and Approval Pending (no hash yet -- design.md is persisted after approval; freeze() hashes it
    at the first agent-TDD spawn). Returns None."""
    if payload.get("tool_name") != "ExitPlanMode" or not _approved(payload.get("tool_response")):
        return None
    state_md = active_state_file(payload.get("cwd") or os.getcwd())
    if not state_md:
        return None
    if parse_state(state_md).get("current phase", "").strip().lower() != "design":
        return None
    _record(state_md, {"implementation requested": "Yes", "approval pending": "yes"},
            {"implementation_requested": "Yes", "approval_pending": "yes"})
    return None


def freeze(spec_dir):
    """Record Approval Hash over requirements.md + design.md and clear Approval Pending. Returns
    the hash, or None (nothing written) when either artifact is missing/empty. An already-recorded
    hash is never overwritten: it is returned unchanged."""
    state_md = _current_state(spec_dir)
    if not os.path.isfile(state_md):
        return None
    existing = _hash_or_blank(parse_state(state_md).get("approval hash"))
    if existing:
        return existing
    req = _read(os.path.join(spec_dir, "requirements", "requirements.md"))
    design = _read(os.path.join(spec_dir, "design", "design.md"))
    if not req.strip() or not design.strip():
        return None
    digest = approval_hash(req, design)
    _record(state_md, {"approval hash": digest, "approval pending": "no"},
            {"approval_hash": digest, "approval_pending": "no"})
    return digest


def refreeze(spec_dir):
    """Clear the recorded hash (md + json) and re-freeze from the current artifacts. Returns the
    new hash, or None (nothing changed) when state or either artifact is missing/empty."""
    state_md = _current_state(spec_dir)
    if not os.path.isfile(state_md):
        return None
    req = _read(os.path.join(spec_dir, "requirements", "requirements.md"))
    design = _read(os.path.join(spec_dir, "design", "design.md"))
    if not req.strip() or not design.strip():
        return None
    digest = approval_hash(req, design)
    _record(state_md, {"approval hash": digest, "approval pending": "no"},
            {"approval_hash": digest, "approval_pending": "no"})
    return digest


def approve(spec_dir):
    """Record Implementation Requested: Yes + Approval Pending: yes (plan-mode-unavailable
    fallback). Returns True, or False when the workflow state file is missing."""
    state_md = _current_state(spec_dir)
    if not os.path.isfile(state_md):
        return False
    _record(state_md, {"implementation requested": "Yes", "approval pending": "yes"},
            {"implementation_requested": "Yes", "approval_pending": "yes"})
    return True


def _cli(argv):
    from path_resolution import PluginDataDirUnavailable, get_plugin_data_dir
    if len(argv) != 2 or argv[0] not in ("refreeze", "approve"):
        print("usage: approval.py refreeze|approve <spec_dir>", file=sys.stderr)
        return 2
    try:
        get_plugin_data_dir("agent-isdd")
    except PluginDataDirUnavailable as e:
        print(str(e), file=sys.stderr)
        return 1
    cmd, spec_dir = argv
    if cmd == "refreeze":
        digest = refreeze(spec_dir)
        if digest is None:
            print("refreeze failed: workflow-state.md, requirements/requirements.md or "
                  "design/design.md is missing or empty in %s" % spec_dir, file=sys.stderr)
            return 1
        print(digest)
        return 0
    if not approve(spec_dir):
        print("approve failed: no workflow-state.md in %s" % spec_dir, file=sys.stderr)
        return 1
    print("Implementation Requested: Yes; Approval Pending: yes")
    return 0


def main():
    if len(sys.argv) > 1:
        sys.exit(_cli(sys.argv[1:]))
    try:
        payload = json.load(sys.stdin)
    except (ValueError, OSError):
        payload = {}
    try:
        evaluate(payload if isinstance(payload, dict) else {})
    except Exception:
        pass
    sys.exit(0)


if __name__ == "__main__":
    main()
