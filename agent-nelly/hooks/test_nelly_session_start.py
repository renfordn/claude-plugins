"""Tests for hooks/nelly_session_start.py — the SessionStart hook (Phase 5).

Isolated the same way test_nelly_memory.py is: monkeypatch nelly_memory.BASE to a
tmp dir (nelly_session_start imports memory_dir/read_index/read_global_index/
list_entries directly from nelly_memory, but those functions still resolve
nelly_memory.BASE at call time, so the monkeypatch is honored). main() is
invoked in-process (not via subprocess) so capsys can capture stdout and the
JSON payload is fed through a monkeypatched sys.stdin — simpler and more
reliable than spinning up a subprocess with an env-overridden HOME per test.
"""
import io
import json
import os
import time

import pytest

import nelly_memory
import nelly_session_start


@pytest.fixture(autouse=True)
def isolated_base(tmp_path, monkeypatch):
    monkeypatch.setattr(nelly_memory, "BASE", str(tmp_path / "agent-nelly-memory"))
    return tmp_path


CWD = "/Users/jay.nelson/Codebase/AI/plugins/claude/agent-nelly"


def _run(monkeypatch, capsys, cwd=CWD):
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": cwd})))
    with pytest.raises(SystemExit) as exc:
        nelly_session_start.main()
    assert exc.value.code == 0
    out = capsys.readouterr().out
    payload = json.loads(out)
    return payload["hookSpecificOutput"]["additionalContext"]


# ---------------------------------------------------------------------------
# 1. Always announce the project's memory root.
# ---------------------------------------------------------------------------

def test_announces_memory_root(monkeypatch, capsys):
    ctx = _run(monkeypatch, capsys)
    assert nelly_memory.memory_dir(CWD) in ctx


def test_output_is_valid_hook_json(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": CWD})))
    with pytest.raises(SystemExit):
        nelly_session_start.main()
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert payload["hookSpecificOutput"]["hookEventName"] == "SessionStart"


# ---------------------------------------------------------------------------
# 3. Intent surfacing — verbatim when present, explicit placeholder when not.
# ---------------------------------------------------------------------------

def test_intent_placeholder_when_absent(monkeypatch, capsys):
    nelly_memory.ensure_dir(CWD)  # header scaffold only, no Intent line
    ctx = _run(monkeypatch, capsys)
    assert "Intent: not yet captured" in ctx


def test_intent_surfaced_verbatim_when_present(monkeypatch, capsys):
    d = nelly_memory.ensure_dir(CWD)
    index = os.path.join(d, "MEMORY.md")
    with open(index, "a", encoding="utf-8") as fh:
        fh.write("Intent: build the widget frobnicator\n")
    ctx = _run(monkeypatch, capsys)
    assert "Intent: build the widget frobnicator" in ctx


# ---------------------------------------------------------------------------
# 4. Durable-entries surfacing — only speak up if real entries exist.
# ---------------------------------------------------------------------------

def test_no_entries_section_when_no_entries_exist(monkeypatch, capsys):
    ctx = _run(monkeypatch, capsys)
    assert "Durable entries" not in ctx


def test_entries_surfaced_when_present(monkeypatch, capsys):
    entries_dir = os.path.join(nelly_memory.memory_dir(CWD), "entries")
    os.makedirs(entries_dir, exist_ok=True)
    with open(os.path.join(entries_dir, "alpha.md"), "w", encoding="utf-8") as fh:
        fh.write("content")
    ctx = _run(monkeypatch, capsys)
    assert "alpha" in ctx


def test_entries_surfaced_when_typed_file_relevance_and_error_prevention(monkeypatch, capsys):
    """Regression fixture (v2 Phase 12): condensed entries list must still
    render correctly when `entries/` contains the two new v2 entry types
    (`file-relevance`, `error-prevention`). Per design.md's Validation
    Strategy, this hook "only reads filenames via `list_entries()`, never
    `metadata.type`" — this test proves that empirically rather than
    assuming it, per this repo's 0.1.4 write-back bug precedent.
    """
    entries_dir = os.path.join(nelly_memory.memory_dir(CWD), "entries")
    os.makedirs(entries_dir, exist_ok=True)
    with open(os.path.join(entries_dir, "widget-config-location.md"), "w", encoding="utf-8") as fh:
        fh.write(
            "---\n"
            "name: widget-config-location\n"
            "description: where the widget frobnicator's config lives\n"
            "metadata:\n"
            "  type: file-relevance\n"
            "  last_referenced: 2026-08-10\n"
            "  files: [src/widget/config.py]\n"
            "---\n\n"
            "Why these files: config.py defines the frobnicator's tunables.\n"
            "What the fact is: defaults live in DEFAULT_CONFIG at the top of the file.\n"
        )
    with open(os.path.join(entries_dir, "avoid-double-init.md"), "w", encoding="utf-8") as fh:
        fh.write(
            "---\n"
            "name: avoid-double-init\n"
            "description: do not call widget.init() twice in the same process\n"
            "metadata:\n"
            "  type: error-prevention\n"
            "  last_referenced: 2026-08-10\n"
            "  confidence: explicit\n"
            "---\n\n"
            "Failed approach: called widget.init() in both setup() and main().\n"
            "Context: any script that imports the widget module directly.\n"
            "Why it failed: the second init() call reset global state mid-run.\n"
            "How to avoid: call init() exactly once, in main() only.\n"
        )
    ctx = _run(monkeypatch, capsys)
    assert "widget-config-location" in ctx
    assert "avoid-double-init" in ctx


# ---------------------------------------------------------------------------
# 4b. Index-based brief (nelly-index.json) — pure data, zero-LLM-cost.
# ---------------------------------------------------------------------------

def _write_index(cwd, records):
    d = nelly_memory.memory_dir(cwd)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "nelly-index.json"), "w", encoding="utf-8") as fh:
        json.dump(records, fh)


def _record(slug, type_=None, confidence=None, description="", mtime=None):
    return {
        "slug": slug,
        "type": type_,
        "confidence": confidence,
        "description": description,
        "tags": [],
        "file_path": f"entries/{slug}.md",
        "mtime": mtime if mtime is not None else time.time(),
    }


def test_brief_rendered_when_index_present(monkeypatch, capsys):
    _write_index(CWD, [
        _record("alpha", type_="technique", description="how to do the thing", mtime=100),
        _record("beta", type_="error-prevention", confidence="explicit", description="avoid the bug", mtime=200),
    ])
    ctx = _run(monkeypatch, capsys)
    assert "[nelly] Project memory: 2 entries (1 error-prevention, 1 technique)" in ctx
    assert "Recent: beta — avoid the bug" in ctx
    assert "        alpha — how to do the thing" in ctx
    assert "Run /nelly-memory view for full context." in ctx
    assert "Durable entries" not in ctx


def test_brief_no_op_falls_back_when_index_empty(monkeypatch, capsys):
    _write_index(CWD, [])
    entries_dir = os.path.join(nelly_memory.memory_dir(CWD), "entries")
    os.makedirs(entries_dir, exist_ok=True)
    with open(os.path.join(entries_dir, "alpha.md"), "w", encoding="utf-8") as fh:
        fh.write("content")
    ctx = _run(monkeypatch, capsys)
    assert "[nelly] Project memory" not in ctx
    assert "Durable entries (1): alpha" in ctx


def test_brief_no_op_falls_back_when_index_missing(monkeypatch, capsys):
    entries_dir = os.path.join(nelly_memory.memory_dir(CWD), "entries")
    os.makedirs(entries_dir, exist_ok=True)
    with open(os.path.join(entries_dir, "alpha.md"), "w", encoding="utf-8") as fh:
        fh.write("content")
    ctx = _run(monkeypatch, capsys)
    assert "[nelly] Project memory" not in ctx
    assert "Durable entries (1): alpha" in ctx


def test_brief_silent_when_index_and_entries_both_absent(monkeypatch, capsys):
    ctx = _run(monkeypatch, capsys)
    assert "[nelly] Project memory" not in ctx
    assert "Durable entries" not in ctx


def test_brief_orders_explicit_error_prevention_first(monkeypatch, capsys):
    _write_index(CWD, [
        _record("newest-technique", type_="technique", description="a recent technique", mtime=500),
        _record("older-explicit-ep", type_="error-prevention", confidence="explicit",
                 description="an older but explicit lesson", mtime=100),
        _record("inferred-ep", type_="error-prevention", confidence="inferred",
                 description="an unconfirmed lesson", mtime=600),
    ])
    ctx = _run(monkeypatch, capsys)
    lines = ctx.splitlines()
    recent_line = next(l for l in lines if l.startswith("Recent:"))
    assert "older-explicit-ep" in recent_line
    # explicit error-prevention sorts ahead of the newer, non-explicit entries
    idx_explicit = next(i for i, l in enumerate(lines) if "older-explicit-ep" in l)
    idx_inferred = next(i for i, l in enumerate(lines) if "inferred-ep" in l)
    idx_technique = next(i for i, l in enumerate(lines) if "newest-technique" in l)
    assert idx_explicit < idx_inferred
    assert idx_explicit < idx_technique


def test_brief_caps_at_five_entries(monkeypatch, capsys):
    _write_index(CWD, [
        _record(f"slug-{i}", type_="technique", description=f"desc {i}", mtime=float(i))
        for i in range(8)
    ])
    ctx = _run(monkeypatch, capsys)
    assert "[nelly] Project memory: 8 entries (0 error-prevention, 8 technique)" in ctx
    recent_count = sum(1 for line in ctx.splitlines() if line.startswith("Recent:") or line.startswith("        "))
    assert recent_count == 5


def test_brief_truncates_long_descriptions(monkeypatch, capsys):
    long_desc = "x" * 120
    _write_index(CWD, [_record("alpha", type_="technique", description=long_desc, mtime=1)])
    ctx = _run(monkeypatch, capsys)
    assert ("x" * 60) in ctx
    assert ("x" * 61) not in ctx


# ---------------------------------------------------------------------------
# 4c. Hotspot surfacing (hotspots.json, written by nelly_hotspot_tracker.py).
# ---------------------------------------------------------------------------

def _write_hotspots(cwd, files):
    d = nelly_memory.memory_dir(cwd)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "hotspots.json"), "w", encoding="utf-8") as fh:
        json.dump({"files": files, "updated_at": "2026-08-16T10:30:00"}, fh)


def test_no_hotspots_line_when_hotspots_file_absent(monkeypatch, capsys):
    ctx = _run(monkeypatch, capsys)
    assert "Hot files" not in ctx


def test_hotspots_surfaced_top_three_by_count(monkeypatch, capsys, tmp_path):
    real_file = tmp_path / "real.py"
    real_file.write_text("x")
    _write_hotspots(CWD, {
        str(real_file): {"count": 12, "last_seen": "2026-08-16T10:00:00"},
    })
    ctx = _run(monkeypatch, capsys)
    assert f"Hot files: {real_file} (12 edits)" in ctx


def test_hotspots_excludes_files_with_one_edit(monkeypatch, capsys, tmp_path):
    real_file = tmp_path / "real.py"
    real_file.write_text("x")
    _write_hotspots(CWD, {
        str(real_file): {"count": 1, "last_seen": "2026-08-16T10:00:00"},
    })
    ctx = _run(monkeypatch, capsys)
    assert "Hot files" not in ctx


def test_hotspots_excludes_missing_files(monkeypatch, capsys, tmp_path):
    missing = tmp_path / "gone.py"
    _write_hotspots(CWD, {
        str(missing): {"count": 5, "last_seen": "2026-08-16T10:00:00"},
    })
    ctx = _run(monkeypatch, capsys)
    assert "Hot files" not in ctx


def test_hotspots_caps_at_three_sorted_by_count_desc(monkeypatch, capsys, tmp_path):
    files = {}
    for i in range(5):
        f = tmp_path / f"file-{i}.py"
        f.write_text("x")
        files[str(f)] = {"count": i + 2, "last_seen": "2026-08-16T10:00:00"}
    _write_hotspots(CWD, files)
    ctx = _run(monkeypatch, capsys)
    line = next(l for l in ctx.splitlines() if l.startswith("Hot files:"))
    assert str(tmp_path / "file-4.py") in line
    assert str(tmp_path / "file-3.py") in line
    assert str(tmp_path / "file-2.py") in line
    assert str(tmp_path / "file-1.py") not in line
    assert str(tmp_path / "file-0.py") not in line


def test_hotspots_malformed_file_is_silent_fallback(monkeypatch, capsys):
    d = nelly_memory.memory_dir(CWD)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "hotspots.json"), "w", encoding="utf-8") as fh:
        fh.write("not json")
    ctx = _run(monkeypatch, capsys)
    assert "Hot files" not in ctx


# ---------------------------------------------------------------------------
# 5. Global condensed index — name: description one-liners only, never bodies.
# ---------------------------------------------------------------------------

def test_no_global_section_when_global_empty(monkeypatch, capsys):
    ctx = _run(monkeypatch, capsys)
    assert "Global" not in ctx


def test_global_condensed_entries_surfaced(monkeypatch, capsys):
    d = nelly_memory.global_dir()
    index = os.path.join(d, "GLOBAL-MEMORY.md")
    with open(index, "a", encoding="utf-8") as fh:
        fh.write(
            "\n---\n"
            "name: some-fact\n"
            "description: a durable cross-project fact\n"
            "---\n"
            "\nFull entry body with lots of detail that must NOT be surfaced.\n"
        )
    ctx = _run(monkeypatch, capsys)
    assert "some-fact: a durable cross-project fact" in ctx
    assert "lots of detail that must NOT be surfaced" not in ctx


# ---------------------------------------------------------------------------
# 6. Negative test — no workflow/session-lifecycle logic present.
# ---------------------------------------------------------------------------

def test_no_workflow_lifecycle_terms_in_output(monkeypatch, capsys):
    d = nelly_memory.ensure_dir(CWD)
    index = os.path.join(d, "MEMORY.md")
    with open(index, "a", encoding="utf-8") as fh:
        fh.write("Intent: build the widget frobnicator\n")
    entries_dir = os.path.join(nelly_memory.memory_dir(CWD), "entries")
    os.makedirs(entries_dir, exist_ok=True)
    with open(os.path.join(entries_dir, "alpha.md"), "w", encoding="utf-8") as fh:
        fh.write("content")
    nelly_memory.global_dir()

    ctx = _run(monkeypatch, capsys)
    # Exclude the memory-root path line: pytest's own tmp_path can embed the
    # test's function name (e.g. ".../test_no_workflow_lifecycle_ter0/...")
    # which would otherwise produce a false positive unrelated to the hook's
    # actual behavior.
    body = "\n".join(
        line for line in ctx.splitlines() if not line.startswith("Agent Nelly memory for this project:")
    )
    lowered = body.lower()
    for forbidden in ("workflow", "snapshot", "interrupted"):
        assert forbidden not in lowered
    # "phase" would only appear if RED/GREEN/REFACTOR-style workflow state
    # scanning were accidentally ported in.
    assert "phase" not in lowered


# ---------------------------------------------------------------------------
# Empty-project baseline — minimal, error-free announce-only output.
# ---------------------------------------------------------------------------

def test_empty_project_minimal_output_no_errors(monkeypatch, capsys):
    ctx = _run(monkeypatch, capsys)
    assert nelly_memory.memory_dir(CWD) in ctx
    assert "Intent: not yet captured" in ctx
    assert "Durable entries" not in ctx
    assert "Global" not in ctx


# ---------------------------------------------------------------------------
# Global-only-populated project — global section present, others minimal/absent.
# ---------------------------------------------------------------------------

def test_global_only_populated_project(monkeypatch, capsys):
    d = nelly_memory.global_dir()
    index = os.path.join(d, "GLOBAL-MEMORY.md")
    with open(index, "a", encoding="utf-8") as fh:
        fh.write("\n---\nname: g-fact\ndescription: global only fact\n---\n")

    ctx = _run(monkeypatch, capsys)
    assert "g-fact: global only fact" in ctx
    assert "Intent: not yet captured" in ctx
    assert "Durable entries" not in ctx
