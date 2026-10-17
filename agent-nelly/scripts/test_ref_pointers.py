"""Reference-pointer registry: each moved section leaves a one-line stub in agent-nelly.md that
points at a references/ file. Later slices append a tuple to REGISTRY."""
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
AGENT_PATH = ROOT / "agents" / "agent-nelly.md"
REFS = ROOT / "references"
POINTER = "${CLAUDE_PLUGIN_ROOT}/references/"

# (reference filename, [trigger strings], stub heading in agent-nelly.md[, [extra headings sharing the file]])
REGISTRY = [
    ("nelly-research-digest.md",
     ["research digest", "research digest lookup"],
     "### Research Digest Cache"),
    ("nelly-file-summary-cache.md",
     ["file summary lookup", "file summaries", "folder summaries"],
     "### File & Folder Summary Cache"),
    ("nelly-handoff-surfacing.md",
     ["handoff surfacing"],
     "### Handoff surfacing (narrower mode, restricted entry types)"),
    ("nelly-aside-spinoff.md",
     ["aside spinoff"],
     "### Aside-spinoff context bundle"),
    ("nelly-record-batch.md",
     ["new facts"],
     "### Recording new facts (batch)"),
    ("nelly-promotion-writeback.md",
     ["judgment lands in Bucket 1"],
     "### Promotion write-back (Bucket 1 only)"),
    ("nelly-error-lessons.md",
     ["error lesson", "confirm error lesson", "discard", "list inferred", "contradicts an entry"],
     "### Recording an error lesson",
     ["### Supersession write-back",
      "### Confirming an inferred error lesson",
      "### Discarding an inferred error lesson",
      "### Listing inferred error lessons",
      "### Automatic (best-effort) inferred-lesson detection"]),
    ("nelly-consolidated-memories.md",
     ["weekly-cleanup"],
     "## Consolidated memories (weekly cleanup output)"),
]
IDS = [r[0] for r in REGISTRY]
_NORM = [(r + ([],))[:4] if len(r) == 3 else r for r in REGISTRY]


def _agent():
    return AGENT_PATH.read_text(encoding="utf-8")


def _stub_lines(name):
    return [l for l in _agent().splitlines() if f"{POINTER}{name}" in l]


@pytest.mark.parametrize("name,triggers,heading,extra", _NORM, ids=IDS)
def test_reference_file_exists(name, triggers, heading, extra):
    assert (REFS / name).is_file(), f"missing {REFS / name}"


@pytest.mark.parametrize("name,triggers,heading,extra", _NORM, ids=IDS)
def test_exactly_one_stub_names_reference(name, triggers, heading, extra):
    n = 1 + len(extra)
    assert _agent().count(f"{POINTER}{name}") == n
    assert len(_stub_lines(name)) == n
    lines = _agent().splitlines()
    for h in [heading] + list(extra):
        assert h in lines, f"{h!r} missing"
        nxt = [l for l in lines[lines.index(h) + 1:] if l.strip()][0]
        assert f"{POINTER}{name}" in nxt, f"stub not directly under {h!r}"


@pytest.mark.parametrize("name,triggers,heading,extra", _NORM, ids=IDS)
def test_stub_heading_present(name, triggers, heading, extra):
    for h in [heading] + list(extra):
        assert h in _agent().splitlines()


@pytest.mark.parametrize("name,triggers,heading,extra", _NORM, ids=IDS)
def test_reference_opens_with_read_by_and_within_line_budget(name, triggers, heading, extra):
    lines = (REFS / name).read_text(encoding="utf-8").splitlines()
    assert "Read by" in "\n".join(lines[:5])
    assert len(lines) <= 400


@pytest.mark.parametrize("name,triggers,heading,extra", _NORM, ids=IDS)
def test_triggers_in_stub_and_reference_header(name, triggers, heading, extra):
    stubs = _stub_lines(name)
    assert len(stubs) == 1 + len(extra)
    header = "\n".join((REFS / name).read_text(encoding="utf-8").splitlines()[:5])
    joined = "\n".join(stubs)
    for t in triggers:
        assert t in joined, f"{t!r} not in stub(s)"
        assert t in header, f"{t!r} not in reference header"


# heading -> distinctive line that must stay inline (guards against over-moving)
KEEP_INLINE = [
    ("## Brief assembly contract",
     "This is your default, most-frequent job: given a caller's `cwd` and a"),
    ("## Intent alignment",
     "Compare the stored `Intent` (if any) against the caller's stated task"),
    ("## Relevant entries (on-request proactive surfacing)",
     "Only run this when the caller explicitly passed the surface-relevant-memory"),
    ("### Recording a new fact",
     "When the caller passes `new fact`, write it as a new entry before running"),
    ("### Promotion judgment",
     "Run this judgment on every entry you read or write during a brief-assembly"),
    ("## Explicit exclusions",
     "This agent grew out of `memory-orchestrator`, a capability of the old single"),
]


@pytest.mark.parametrize("heading,marker", KEEP_INLINE, ids=[k[0] for k in KEEP_INLINE])
def test_kept_sections_stay_inline(heading, marker):
    text = _agent()
    assert heading in text.splitlines(), f"{heading!r} missing from agent-nelly.md"
    assert marker in text, f"marker under {heading!r} no longer inline"


def test_inferred_lesson_safety_rule_stays_inline():
    rule = "inferred lessons are never auto-`explicit`; only `confirm error lesson` promotes an entry to `explicit`"
    assert rule in _agent(), "safety rule must stay inline as a literal sentence"


def test_agent_file_size_gate():
    size = len(AGENT_PATH.read_bytes())
    assert size <= 35800, f"agent-nelly.md is {size} bytes (> 35800)"


def test_new_nelly_references_within_line_budget():
    new = [REFS / r[0] for r in REGISTRY]
    for f in new:
        assert f.is_file(), f"missing {f}"
        assert len(f.read_text(encoding="utf-8").splitlines()) <= 400, f"{f.name} > 400 lines"


# every heading moved to references in slices 13-16 must still resolve as an exact line
MOVED_HEADINGS = sorted({h for r in REGISTRY for h in [r[2]] + list(r[3] if len(r) > 3 else [])})


@pytest.mark.parametrize("heading", MOVED_HEADINGS)
def test_moved_headings_still_resolve(heading):
    assert heading in _agent().splitlines()


def test_safety_rule_is_a_complete_sentence_and_no_double_blank_lines():
    text = _agent()
    assert "promotes an entry to `explicit`.\n" in text
    assert "\n\n\n" not in text.split("### Recording an error lesson", 1)[1].split("### Supersession", 1)[0]


def test_auto_detection_stub_has_the_original_trigger_condition():
    lines = _agent().splitlines()
    h = "### Automatic (best-effort) inferred-lesson detection"
    stub = [l for l in lines[lines.index(h) + 1:] if l.strip()][0]
    assert "assembling a brief" in stub
    assert "error-prevention" in stub and "task description" in stub
