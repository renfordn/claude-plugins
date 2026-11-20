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
