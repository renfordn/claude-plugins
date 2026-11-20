"""Release 5 slice 0 (R16/R17): evidence and stale keys on non-digest index records.
Present only when the entry's frontmatter has them; entries without them keep the exact
pre-release record shape. conflicts/ and .nelly.lock are never indexed."""
import json
import os

import pytest

import build_index
import nelly_memory

_BASE_KEYS = {"slug", "type", "confidence", "description", "tags", "seen_count",
              "files", "folder", "git_hash"}
_EVIDENCE_KEYS = {"sources", "symbols", "revision", "verified", "basis", "unknowns",
                  "stale", "stale_since", "stale_paths"}


@pytest.fixture(autouse=True)
def isolated_base(tmp_path, monkeypatch):
    base = str(tmp_path / "agent-nelly-memory")
    monkeypatch.setattr(nelly_memory, "BASE", base)
    monkeypatch.setattr(build_index, "BASE", base)
    return tmp_path


def _evidence_block(stale="true"):
    # Evidence/stale keys live under `metadata:` (entry template convention), with `sources:`
    # in the research-digest list shape, indented one level deeper.
    return "\n".join([
        "name: tech-x",
        "description: a technique",
        "metadata:",
        "  type: technique",
        "  confidence: inferred",
        "  sources:",
        "    - path: scripts/a.py",
        "      hash: h1",
        "    - path: hooks/b.py",
        "      hash: h2",
        "  symbols: [do_thing, Helper.run]",
        "  revision: 4b337cf",
        "  verified: 2026-11-20T10:00:00Z",
        "  basis: read-code",
        "  unknowns: behavior on Windows",
        f"  stale: {stale}",
        "  stale_since: 2026-11-21T09:00:00Z",
        "  stale_paths: [scripts/a.py, hooks/b.py]",
        "  last_referenced: 2026-11-20",
    ])


def _expected_evidence():
    return {
        "sources": [{"path": "scripts/a.py", "hash": "h1"}, {"path": "hooks/b.py", "hash": "h2"}],
        "symbols": ["do_thing", "Helper.run"],
        "revision": "4b337cf",
        "verified": "2026-11-20T10:00:00Z",
        "basis": "read-code",
        "unknowns": "behavior on Windows",
        "stale": True,
        "stale_since": "2026-11-21T09:00:00Z",
        "stale_paths": ["scripts/a.py", "hooks/b.py"],
    }


def test_technique_record_carries_evidence_and_stale_keys():
    rec = build_index._parse_frontmatter_block(_evidence_block())
    assert rec["type"] == "technique"
    for key, value in _expected_evidence().items():
        assert key in rec, f"missing index key {key!r}"
        assert rec[key] == value, key
    assert rec["stale"] is True


def test_stale_false_is_bool_false():
    rec = build_index._parse_frontmatter_block(_evidence_block(stale="false"))
    assert "stale" in rec
    assert rec["stale"] is False


def test_only_present_evidence_keys_are_added():
    block = "\n".join(["name: tech-y", "description: d", "metadata:", "  type: technique",
                       "  revision: abc123", "  stale: true"])
    rec = build_index._parse_frontmatter_block(block)
    assert rec.get("revision") == "abc123"
    assert rec.get("stale") is True
    assert set(rec) & _EVIDENCE_KEYS == {"revision", "stale"}


def test_entry_without_evidence_keeps_exact_legacy_shape():
    block = "name: f\ndescription: d\nmetadata:\n  type: technique\n  tags: [a]\n"
    rec = build_index._parse_frontmatter_block(block)
    assert set(rec) == _BASE_KEYS
    assert rec["tags"] == ["a"]


def _seed(cwd):
    entries = nelly_memory.ensure_entries_dir(cwd)
    with open(os.path.join(entries, "tech-x.md"), "w") as fh:
        fh.write("---\n" + _evidence_block() + "\n---\nBody\n")
    with open(os.path.join(entries, "plain.md"), "w") as fh:
        fh.write("---\nname: plain\ndescription: d\nmetadata:\n  type: project\n---\n")
    return entries


def test_full_build_writes_evidence_keys_into_index(tmp_path):
    cwd = str(tmp_path / "project")
    _seed(cwd)
    build_index.build_project_index(cwd)
    with open(os.path.join(nelly_memory.memory_dir(cwd), build_index.INDEX_FILENAME)) as fh:
        by_slug = {r["slug"]: r for r in json.load(fh)}
    for key, value in _expected_evidence().items():
        assert by_slug["tech-x"].get(key) == value, key
    assert set(by_slug["plain"]) == _BASE_KEYS | {"file_path", "mtime"}


def test_upsert_writes_evidence_keys_into_index(tmp_path):
    cwd = str(tmp_path / "project")
    entries = _seed(cwd)
    records = build_index.upsert_project_entry(cwd, os.path.join(entries, "tech-x.md"))
    rec = next(r for r in records if r["slug"] == "tech-x")
    for key, value in _expected_evidence().items():
        assert rec.get(key) == value, key


def _sidecar_text():
    return "---\nname: tech-x\ndescription: loser\nmetadata:\n  type: technique\n---\n"


def test_conflicts_dir_and_lock_file_are_never_indexed_on_full_build(tmp_path):
    """Regression guard (passes without the slice-0 fix; full build never descended there)."""
    cwd = str(tmp_path / "project")
    entries = _seed(cwd)
    d = nelly_memory.memory_dir(cwd)
    for conflicts in (os.path.join(d, "conflicts"), os.path.join(entries, "conflicts")):
        os.makedirs(conflicts, exist_ok=True)
        with open(os.path.join(conflicts, "tech-x.20261120T100000.123.md"), "w") as fh:
            fh.write(_sidecar_text())
    open(os.path.join(d, ".nelly.lock"), "w").close()
    open(os.path.join(entries, ".nelly.lock"), "w").close()

    records = build_index.build_project_index(cwd)

    assert sorted(r["file_path"] for r in records) == [
        os.path.join("entries", "plain.md"), os.path.join("entries", "tech-x.md")]


def test_upsert_of_conflict_sidecar_does_not_add_a_record(tmp_path):
    cwd = str(tmp_path / "project")
    _seed(cwd)
    build_index.build_project_index(cwd)
    d = nelly_memory.memory_dir(cwd)
    sidecar = os.path.join(d, "conflicts", "tech-x.20261120T100000.123.md")
    os.makedirs(os.path.dirname(sidecar), exist_ok=True)
    with open(sidecar, "w") as fh:
        fh.write(_sidecar_text())

    records = build_index.upsert_project_entry(cwd, sidecar)

    assert sorted(r["file_path"] for r in records) == [
        os.path.join("entries", "plain.md"), os.path.join("entries", "tech-x.md")]
    tech = next(r for r in records if r["slug"] == "tech-x")
    assert tech["description"] == "a technique"


def test_upsert_of_lock_file_does_not_touch_records(tmp_path):
    cwd = str(tmp_path / "project")
    _seed(cwd)
    before = build_index.build_project_index(cwd)
    lock = os.path.join(nelly_memory.memory_dir(cwd), ".nelly.lock")
    open(lock, "w").close()

    records = build_index.upsert_project_entry(cwd, lock)

    assert sorted(r["file_path"] for r in records) == sorted(r["file_path"] for r in before)


def _fm(*lines):
    return "\n".join(["name: t", "description: d", "metadata:", "  type: technique", *lines])


def test_f2_flow_style_sources():
    rec = build_index._parse_frontmatter_block(
        _fm("  sources: [{path: a.py, hash: h1}, {path: 'b c.py', hash: h2}]"))
    assert rec["sources"] == [{"path": "a.py", "hash": "h1"}, {"path": "b c.py", "hash": "h2"}]


def test_f2_block_list_symbols_stale_paths_tags_files():
    rec = build_index._parse_frontmatter_block(_fm(
        "  symbols:", "    - do_thing", "    - Helper.run",
        "  stale_paths:", "    - a.py", "  tags:", "    - x", "    - y",
        "  files:", "    - f.py", "  revision: r1"))
    assert rec["symbols"] == ["do_thing", "Helper.run"]
    assert rec["stale_paths"] == ["a.py"]
    assert rec["tags"] == ["x", "y"]
    assert rec["files"] == ["f.py"]
    assert rec["revision"] == "r1"


def test_f2_quote_aware_inline_list_and_blank_scalar():
    rec = build_index._parse_frontmatter_block(_fm('  symbols: ["a, b", c]', "  revision:   "))
    assert rec["symbols"] == ["a, b", "c"]
    assert "revision" not in rec
