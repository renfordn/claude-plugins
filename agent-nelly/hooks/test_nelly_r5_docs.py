import os

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")


def _read(*p):
    with open(os.path.join(ROOT, *p), encoding="utf-8") as f:
        return f.read()


def test_staleness_uses_deterministic_flags():
    s = _read("references", "nelly-staleness.md")
    for k in ("stale: true", "nelly_freshness", "--drop-paths", "nelly_evidence.py", "never delete",
              "repo-root-relative", "WITHOUT `sources`", "schema_guard"):
        assert k in s, k
    assert "(referenced file heavily changed)" not in s


def test_maintenance_rules():
    s = _read("agents", "nelly-maintenance.md")
    for k in ("deterministic `stale` flags", "--drop-paths", "Never hand-edit", "Resolving conflict sidecars"):
        assert k in s, k


def test_agent_nelly_brief_rules():
    s = _read("agents", "agent-nelly.md")
    for k in ("(stale: recheck <paths>)", "`basis`", "`unknowns`", "nelly_evidence.py", "nelly_pending.py", "pending-findings hint"):
        assert k in s, k


def test_interop_and_template():
    s = _read("INTEROP.md")
    for k in ("--drop-paths", "repo root (git toplevel", "nelly_pending.py add", "5 plugin data dir unavailable"):
        assert k in s, k
    t = _read("references", "nelly-entry.template.md")
    assert "--drop-paths" in t and "git toplevel" in t
    assert "relative to the project's `cwd`" not in t


# --- slice 2E: every documented script invocation is complete and parses ---

import re  # noqa: E402
import shlex  # noqa: E402
import sys  # noqa: E402

sys.path.insert(0, os.path.join(ROOT, "hooks"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import nelly_evidence  # noqa: E402
import nelly_pending  # noqa: E402

_DOCS = [("INTEROP.md",), ("references", "nelly-staleness.md"), ("references", "nelly-entry.template.md"),
         ("agents", "nelly-maintenance.md"), ("agents", "agent-nelly.md")]
_SUBS = r"(?:record|refresh|stale|add|list|resolve)"
_INVOKE = re.compile(r"(nelly_evidence|nelly_pending)\.py\"?\s+(" + _SUBS + r"\b[^`\n]*)")


def _invocations(text):
    out = []
    for m in _INVOKE.finditer(text):
        tail = m.group(2).rstrip(" .,;:)")
        out.append((m.group(1), shlex.split(tail)))
    return out


def test_every_documented_invocation_parses_with_cwd_and_slug():
    seen = 0
    for parts in _DOCS:
        text = _read(*parts)
        calls = _invocations(text)
        if calls:
            assert "env prefix" in text, f"{parts}: invocations must say to use the SessionStart env prefix"
        for script, argv in calls:
            parser = (nelly_evidence._parser() if script == "nelly_evidence" else nelly_pending._parser())
            try:
                ns = parser.parse_args(argv)
            except SystemExit:
                raise AssertionError(f"{parts}: does not parse: {script}.py {' '.join(argv)}")
            if argv[0] in ("record", "refresh", "add", "resolve", "list", "stale"):
                assert "--cwd" in argv, f"{parts}: missing --cwd: {argv}"
            if argv[0] in ("record", "refresh"):
                assert "--slug" in argv, f"{parts}: missing --slug: {argv}"
            seen += 1
    assert seen >= 8


def test_staleness_docs_say_recheck_rewrite_then_refresh():
    for parts in (("references", "nelly-staleness.md"), ("agents", "nelly-maintenance.md"), ("INTEROP.md",)):
        t = _read(*parts)
        assert "--confirm-unchanged" in t, parts


def test_file_move_lists_r5_bash_uses_and_never_overwrites():
    t = _read("references", "nelly-file-move.md")
    assert "nelly_evidence.py" in t and "nelly_pending.py" in t and "mv -n" in t


def test_agent_nelly_new_fact_uses_record_and_pending_for_code_facts():
    t = _read("agents", "agent-nelly.md").split("### Recording a new fact", 1)[1].split("### Recording new facts", 1)[0]
    for k in ("nelly_evidence.py", "nelly_pending.py", "file-relevance", "project"):
        assert k in t, k


def test_new_fact_step_2_does_not_rely_on_the_sessionstart_line():
    t = _read("agents", "agent-nelly.md").split("### Recording a new fact", 1)[1].split("### Recording new facts", 1)[0]
    assert 'CLAUDE_PLUGIN_DATA="${CLAUDE_PLUGIN_DATA}" python3 "${CLAUDE_PLUGIN_ROOT}/scripts/nelly_evidence.py" record' in t
    assert "Stop hook" in t
