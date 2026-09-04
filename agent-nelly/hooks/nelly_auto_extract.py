#!/usr/bin/env python3
"""PostToolUse hook: scan Bash tool output for test-failure/exception signals
and auto-write a draft `inferred`-confidence `error-prevention` entry, so a
lesson isn't lost when the user never remembers to run `/nelly-memory
error-lesson` by hand.

This is a deliberate exception to the "nelly-orchestrator is the sole owner
of every entries/*.md write" convention documented in commands/nelly-memory.md
-- a hook is a plain deterministic script with no way to invoke the LLM
agent, so it writes directly via nelly_memory.py's own helpers (same ones
nelly-orchestrator itself uses) and then calls build_index.upsert_project_entry
to keep nelly-index.json in sync, same as nelly_index_update.py does for
Write/Edit/MultiEdit. `confidence: inferred` keeps the entry permanently
excluded from nelly_proactive_surface.py's surfacing gate until a human runs
`/nelly-memory confirm-lesson <name>` (or `review-inferred`) -- this hook
never marks anything `explicit` itself.

Fires on every Bash completion (see hooks/hooks.json's PostToolUse matcher),
so it must be fast, silent unless it actually writes something, and never
break the user's bash flow. The entire body runs under one broad
try/except -- any failure (missing payload fields, unwritable memory dir,
corrupt index) is swallowed and treated as a silent no-op, never a crash or
stderr spew.

Set env NELLY_GATE=off (or 0/false/disabled, case-insensitive) to disable
entirely, same convention as the other Nelly gate hooks.

Auto-confirmation of recurring inferred entries: every entry this hook (or
its sibling nelly_commit_extract.py) writes carries a `metadata.seen_count`
field, starting at 1. When a later Bash call re-detects the same slug (a
dedup hit in `_entry_exists`), instead of a silent no-op we now read the
existing entry, increment `seen_count`, and -- if the entry is still
`confidence: inferred` and the new count reaches PROMOTION_THRESHOLD --
flip it to `confidence: explicit` in place and append one `Action:
promoted` block to `CONSOLIDATION-LOG.md`. This is pure deterministic
bookkeeping (no LLM call), the same "hooks may write directly" exception
documented above for the initial write. `confidence: explicit` entries are
never touched by this logic again (no re-promotion, no demotion).

Positive-pattern capture (test-suite recovery): hooks are stateless per
call, so recognizing "this run is green, and an earlier run this session
wasn't" needs a small cross-call memory of its own -- a lightweight session
state file at `<tempdir>/nelly_session_<session_id>.json` (`<tempdir>` is
`tempfile.gettempdir()`, overridable via env `NELLY_SESSION_STATE_DIR` for
test isolation; `<session_id>` falls back to the parent pid when a hook
payload has no `session_id`, e.g. under manual testing), holding just
`{"saw_test_failure": true}`. Every Bash call that
detect_signal() classifies as a pytest/test failure sets that flag; every
call after that is checked with detect_recovery_signal() (a clean-run
detector reusing the same failure regexes as a negative filter, so a mixed
"1 failed, 2 passed" summary is never mistaken for a recovery). The first
recovery seen after the flag was set writes an `inferred`-confidence
`technique` entry (slug `test-recovery-<YYYY-MM-DD-HHMM>`) and clears the
flag, so a long green streak doesn't keep re-writing entries.
"""
import datetime
import json
import os
import re
import sys
import tempfile
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import nelly_memory  # noqa: E402
import build_index  # noqa: E402

_MAX_SLUG_WORDS = 8
_MAX_SLUG_LEN = 60
_MAX_DESCRIPTION_LEN = 140
_MAX_EXCERPT_LEN = 300

PROMOTION_THRESHOLD = 3

_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---", re.S)
_CONFIDENCE_LINE_RE = re.compile(r"^(?P<indent>[ \t]*)confidence:\s*(?P<value>\S+)\s*$", re.M)
_SEEN_COUNT_LINE_RE = re.compile(r"^(?P<indent>[ \t]*)seen_count:\s*(?P<value>\d+)\s*$", re.M)

_CONSOLIDATION_LOG_HEADER = (
    "# Consolidation Log\n\n"
    "Append-only history of consolidation-related actions taken against this "
    "project's memory store, including auto-promotions performed by the "
    "auto-extract hooks (hooks/nelly_auto_extract.py, "
    "hooks/nelly_commit_extract.py) when an inferred entry recurs across "
    "sessions. Never edit or remove a prior entry -- archived/superseded "
    "files remain fully readable, not deleted.\n\n"
    "## Log\n"
)

# --- pytest -----------------------------------------------------------------
_PYTEST_FAILED_RE = re.compile(r"^FAILED\s+(\S+)", re.M)
_PYTEST_FAILURES_HEADER_RE = re.compile(r"^=+\s*FAILURES\s*=+", re.M)
_PYTEST_COUNT_RE = re.compile(r"^\d+\s+failed\b", re.M)

# --- jest / mocha -------------------------------------------------------------
_JEST_FAIL_RE = re.compile(r"^FAIL\s+(\S+)", re.M)
_JEST_MARK_RE = re.compile(r"[✕✗]\s+(.+)")
_MOCHA_NUMBERED_RE = re.compile(r"^\s*\d+\)\s+(.+?):?\s*$", re.M)
_FAILING_COUNT_RE = re.compile(r"^\s*\d+\s+failing\b", re.M)

# --- uncaught exceptions / stack traces --------------------------------------
_GO_PANIC_RE = re.compile(r"^panic:\s*(.+)$", re.M)
_TRACEBACK_RE = re.compile(r"Traceback \(most recent call last\):")
_PY_EXC_RE = re.compile(r"^(\w+(?:Error|Exception)):\s*(.*)$", re.M)
_JS_STACK_AT_RE = re.compile(r"^\s*at\s+\S+.*\(.*:\d+:\d+\)", re.M)
_JS_EXC_RE = re.compile(r"\b(?:Uncaught\s+)?(\w*(?:Error|Exception)):\s*(.+)")

# --- generic fallback ---------------------------------------------------------
_GENERIC_ERROR_RE = re.compile(r"\b(error|exception|fatal|failed)\b", re.I)

# --- test-suite recovery (green run after a failure earlier this session) ---
_PYTEST_PASSED_RE = re.compile(r"^(\d+)\s+passed\b", re.M)
_JEST_SUMMARY_PASSED_RE = re.compile(r"^Tests:\s*(\d+)\s+passed,\s*\1\s+total\b", re.M)
_MOCHA_PASSING_RE = re.compile(r"^\s*(\d+)\s+passing\b", re.M)
_TEST_PATH_RE = re.compile(r"[\w./-]*(?:test|spec)[\w./-]*\.(?:py|js|jsx|ts|tsx)\b", re.I)

_SESSION_STATE_DIR = os.environ.get("NELLY_SESSION_STATE_DIR") or tempfile.gettempdir()


def _kebab(text):
    text = re.sub(r"[^A-Za-z0-9]+", "-", text or "").strip("-").lower()
    parts = [p for p in text.split("-") if p][:_MAX_SLUG_WORDS]
    return "-".join(parts)


def _make_slug(basis):
    kebab = _kebab(basis)
    slug = f"auto-{kebab}" if kebab else "auto-bash-error"
    return slug[:_MAX_SLUG_LEN].rstrip("-") or "auto-bash-error"


def detect_signal(stdout, stderr):
    """Scan combined stdout/stderr for a known failure signal.

    Returns (kind, slug_basis, description) on a match, or None for a clean
    run / unrecognized output -- callers must treat None as a silent no-op.
    Checked in priority order: pytest, jest/mocha, Go panic, Python
    traceback, JS uncaught exception, then a generic non-trivial stderr
    fallback.
    """
    text = f"{stdout}\n{stderr}"
    if not text.strip():
        return None

    m = _PYTEST_FAILED_RE.search(text)
    if m or _PYTEST_FAILURES_HEADER_RE.search(text) or _PYTEST_COUNT_RE.search(text):
        target = m.group(1) if m else "pytest"
        return ("pytest-failure", target, f"pytest failure: {target}")

    m = _JEST_FAIL_RE.search(text)
    mark = m or _JEST_MARK_RE.search(text) or _MOCHA_NUMBERED_RE.search(text)
    if mark or _FAILING_COUNT_RE.search(text):
        target = mark.group(1) if mark else "test"
        return ("test-failure", target, f"test failure: {target}")

    m = _GO_PANIC_RE.search(text)
    if m:
        return ("panic", m.group(1), f"panic: {m.group(1)}")

    if _TRACEBACK_RE.search(text):
        m = _PY_EXC_RE.search(text)
        if m:
            exc, msg = m.group(1), m.group(2).strip()
            return ("exception", f"{exc} {msg}", f"uncaught exception: {exc}: {msg[:80]}")
        return ("exception", "traceback", "uncaught exception (traceback)")

    if _JS_STACK_AT_RE.search(text):
        m = _JS_EXC_RE.search(text)
        if m:
            exc, msg = m.group(1), m.group(2).strip()
            return ("exception", f"{exc} {msg}", f"uncaught exception: {exc}: {msg[:80]}")
        return ("exception", "stack-trace", "uncaught exception (stack trace)")

    if stderr.strip() and _GENERIC_ERROR_RE.search(stderr):
        first_line = next((ln.strip() for ln in stderr.splitlines() if ln.strip()), "")
        if first_line:
            return ("command-error", first_line, f"command failed: {first_line[:80]}")

    return None


def detect_recovery_signal(stdout, stderr):
    """Scan combined stdout/stderr for an all-green test run.

    Returns (family, passing_count) on a match -- family is one of
    "pytest"/"jest"/"mocha" -- or None for empty output, a mixed
    pass/fail result, or output with no recognizable passing-count summary.
    Reuses detect_signal()'s own failure regexes as a negative filter first,
    so "1 failed, 2 passed in 0.05s" is never mistaken for a clean run.
    """
    text = f"{stdout}\n{stderr}"
    if not text.strip():
        return None

    if (
        _PYTEST_FAILED_RE.search(text)
        or _PYTEST_FAILURES_HEADER_RE.search(text)
        or _PYTEST_COUNT_RE.search(text)
        or _JEST_FAIL_RE.search(text)
        or _FAILING_COUNT_RE.search(text)
    ):
        return None

    m = _PYTEST_PASSED_RE.search(text)
    if m:
        return ("pytest", int(m.group(1)))

    m = _JEST_SUMMARY_PASSED_RE.search(text)
    if m:
        return ("jest", int(m.group(1)))

    m = _MOCHA_PASSING_RE.search(text)
    if m:
        return ("mocha", int(m.group(1)))

    return None


def _entry_exists(cwd, slug):
    """Duplicate check: prefer the pre-built nelly-index.json (cheap, one
    read) and fall back to scanning entries/*.md slugs directly when the
    index is missing or unreadable -- never treat a missing index as "no
    duplicates", since that would keep re-writing the same lesson every time
    the index happens to be stale/absent.
    """
    index_path = os.path.join(nelly_memory.memory_dir(cwd), "nelly-index.json")
    if os.path.isfile(index_path):
        try:
            with open(index_path, "r", encoding="utf-8") as fh:
                records = json.load(fh)
            return any(r.get("slug") == slug for r in records)
        except (OSError, ValueError):
            pass  # fall through to direct entries/ scan
    return slug in nelly_memory.list_entries(cwd)


def _write_entry(cwd, slug, description, kind, command, excerpt):
    nelly_memory.ensure_entries_dir(cwd)
    path = nelly_memory.entry_path(cwd, slug)

    cmd_excerpt = (command or "").strip()[:_MAX_EXCERPT_LEN]
    why_excerpt = (excerpt or "").strip()[:_MAX_EXCERPT_LEN]
    description = description[:_MAX_DESCRIPTION_LEN]

    body = (
        f"Failed approach: Ran `{cmd_excerpt}`.\n"
        f"Context: Detected automatically from Bash tool output ({kind}).\n"
        f"Why it failed: {why_excerpt}\n"
        "How to avoid: Not yet confirmed -- run `/nelly-memory "
        f"confirm-lesson {slug}` once verified, or `/nelly-memory "
        "list-inferred` to review.\n"
    )
    content = (
        "---\n"
        f"name: {slug}\n"
        f"description: {description}\n"
        "metadata:\n"
        "  type: error-prevention\n"
        f"  last_referenced: {date.today().isoformat()}\n"
        "  confidence: inferred\n"
        "  seen_count: 1\n"
        "---\n\n"
        f"{body}"
    )
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)

    nelly_memory.write_index_line(cwd, slug, description, "error-prevention", confidence="inferred")
    build_index.upsert_project_entry(cwd, path)


def _session_state_path(payload):
    session_id = payload.get("session_id") or f"ppid-{os.getppid()}"
    safe_id = re.sub(r"[^A-Za-z0-9_-]+", "-", str(session_id)).strip("-") or "unknown"
    return os.path.join(_SESSION_STATE_DIR, f"nelly_session_{safe_id}.json")


def _read_session_state(path):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict):
            return data
    except (OSError, ValueError):
        pass
    return {}


def _mark_session_test_failure(path):
    try:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"saw_test_failure": True}, fh)
    except OSError:
        pass


def _clear_session_test_failure(path):
    try:
        os.remove(path)
    except OSError:
        pass


def _make_recovery_slug():
    stamp = datetime.datetime.now().strftime("%Y-%m-%d-%H%M")
    return f"test-recovery-{stamp}"


def _tags_from_test_paths(command, stdout):
    text = f"{command}\n{stdout}"
    seen = set()
    paths = []
    for m in _TEST_PATH_RE.finditer(text):
        p = m.group(0)
        if p not in seen:
            seen.add(p)
            paths.append(p)

    tags = set()
    for p in paths:
        parts = p.split("/")
        tags.add(parts[0] if len(parts) > 1 and parts[0] else p)
    return sorted(tags)[:8]


def _write_recovery_entry(cwd, slug, family, count, tags, command):
    nelly_memory.ensure_entries_dir(cwd)
    path = nelly_memory.entry_path(cwd, slug)

    description = f"Test suite recovered — {count} passing"[:_MAX_DESCRIPTION_LEN]
    cmd_excerpt = (command or "").strip()[:_MAX_EXCERPT_LEN]
    tags_field = ", ".join(tags)

    body = (
        "Technique: Test suite recovered from a prior failure this session.\n"
        f"Result: {count} passing ({family}).\n"
        f"Command: `{cmd_excerpt}`\n"
        "Context: Detected automatically -- a failing test signal was seen "
        "earlier in this session, followed by a clean, all-passing run.\n"
    )
    content = (
        "---\n"
        f"name: {slug}\n"
        f"description: {description}\n"
        "metadata:\n"
        "  type: technique\n"
        f"  last_referenced: {date.today().isoformat()}\n"
        "  confidence: inferred\n"
        "  seen_count: 1\n"
        f"  family: {family}\n"
        f"  passing_count: {count}\n"
        f"tags: [{tags_field}]\n"
        "---\n\n"
        f"{body}"
    )
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)

    nelly_memory.write_index_line(cwd, slug, description, "technique", confidence="inferred")
    build_index.upsert_project_entry(cwd, path)


def _append_promotion_log(cwd, slug, seen_count):
    d = nelly_memory.memory_dir(cwd)
    log_path = os.path.join(d, "CONSOLIDATION-LOG.md")
    if not os.path.exists(log_path):
        with open(log_path, "w", encoding="utf-8") as fh:
            fh.write(_CONSOLIDATION_LOG_HEADER)
    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    block = (
        f"\n### {timestamp}\n"
        f"- Action: promoted\n"
        f"- Entry: {slug}\n"
        f"- Reason: inferred entry re-triggered {seen_count} times -- "
        f"auto-promoted confidence: inferred -> explicit\n"
        f"- Trigger: auto-confirmation threshold ({PROMOTION_THRESHOLD}+ occurrences, "
        f"hooks/nelly_auto_extract.py)\n"
    )
    with open(log_path, "a", encoding="utf-8") as fh:
        fh.write(block)


def _bump_seen_count_and_maybe_promote(cwd, slug):
    """Called on a dedup hit (the slug already has an entry on disk).

    Reads the existing entries/<slug>.md, increments its
    `metadata.seen_count` (treating a missing field as 1, since the write
    that created the entry counts as the first occurrence), and -- only when
    the entry is still `confidence: inferred` and the new count reaches
    PROMOTION_THRESHOLD -- flips it to `confidence: explicit` in place and
    appends one promotion block to CONSOLIDATION-LOG.md. An already-`explicit`
    entry still gets its `seen_count` bumped (harmless bookkeeping) but is
    never re-promoted or demoted.

    Returns (new_seen_count, promoted: bool), or None if the entry file is
    missing/unparseable (e.g. the index was stale) -- callers must treat
    None as a silent no-op, same convention as detect_signal().
    """
    path = nelly_memory.entry_path(cwd, slug)
    try:
        with open(path, "r", encoding="utf-8") as fh:
            text = fh.read()
    except OSError:
        return None

    fm_match = _FRONTMATTER_RE.search(text)
    if not fm_match:
        return None
    block = fm_match.group(1)

    seen_m = _SEEN_COUNT_LINE_RE.search(block)
    current = int(seen_m.group("value")) if seen_m else 1
    new_count = current + 1

    if seen_m:
        new_block = _SEEN_COUNT_LINE_RE.sub(
            lambda m: f"{m.group('indent')}seen_count: {new_count}", block, count=1
        )
    else:
        conf_m = _CONFIDENCE_LINE_RE.search(block)
        if conf_m:
            indent = conf_m.group("indent")
            new_block = block[: conf_m.end()] + f"\n{indent}seen_count: {new_count}" + block[conf_m.end():]
        else:
            new_block = block + f"\n  seen_count: {new_count}"

    confidence_m = _CONFIDENCE_LINE_RE.search(new_block)
    confidence = confidence_m.group("value") if confidence_m else None
    promoted = confidence == "inferred" and new_count >= PROMOTION_THRESHOLD
    if promoted:
        new_block = _CONFIDENCE_LINE_RE.sub(
            lambda m: f"{m.group('indent')}confidence: explicit", new_block, count=1
        )

    new_text = text[: fm_match.start(1)] + new_block + text[fm_match.end(1):]
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(new_text)

    build_index.upsert_project_entry(cwd, path)
    if promoted:
        _append_promotion_log(cwd, slug, new_count)

    return new_count, promoted


def _run():
    if os.environ.get("NELLY_GATE", "").lower() in ("off", "0", "false", "disabled"):
        return

    payload = json.load(sys.stdin)
    if payload.get("tool_name") != "Bash":
        return

    tool_response = payload.get("tool_response") or {}
    stdout = tool_response.get("stdout")
    stderr = tool_response.get("stderr")
    stdout = stdout if isinstance(stdout, str) else ""
    stderr = stderr if isinstance(stderr, str) else ""

    cwd = payload.get("cwd") or os.getcwd()
    command = (payload.get("tool_input") or {}).get("command", "")
    state_path = _session_state_path(payload)

    if _read_session_state(state_path).get("saw_test_failure"):
        recovery = detect_recovery_signal(stdout, stderr)
        if recovery:
            family, count = recovery
            slug = _make_recovery_slug()
            if _entry_exists(cwd, slug):
                result = _bump_seen_count_and_maybe_promote(cwd, slug)
                if result and result[1]:
                    print(f"[nelly] promoted to explicit: {slug} (seen {result[0]}x)")
            else:
                tags = _tags_from_test_paths(command, stdout)
                _write_recovery_entry(cwd, slug, family, count, tags, command)
                print(f"[nelly] technique saved: {slug} (test suite recovered)")
            _clear_session_test_failure(state_path)
            return

    signal = detect_signal(stdout, stderr)
    if not signal:
        return
    kind, slug_basis, description = signal

    if kind in ("pytest-failure", "test-failure"):
        _mark_session_test_failure(state_path)

    slug = _make_slug(slug_basis)
    if _entry_exists(cwd, slug):
        result = _bump_seen_count_and_maybe_promote(cwd, slug)
        if result and result[1]:
            print(f"[nelly] promoted to explicit: {slug} (seen {result[0]}x)")
        return

    _write_entry(cwd, slug, description, kind, command, slug_basis)
    print(f"[nelly] inferred lesson saved: {slug}")


def main():
    try:
        _run()
    except Exception:
        pass  # never break the user's bash flow
    sys.exit(0)


if __name__ == "__main__":
    main()
