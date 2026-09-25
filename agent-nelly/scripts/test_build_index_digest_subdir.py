"""Slice 5 (nelly-research-digest-cache): digest entries nested under
entries/research-digest/ survive a full index rescan and carry
topic/sources/updated on their index record.

The subdir and type literals are hardcoded ("research-digest") rather than
imported from nelly_memory so these tests fail on the behavior, not on an
ImportError, while the DIGEST_SUBDIR constant does not yet exist.
"""
import os

import pytest

import build_index
import nelly_memory

DIGEST_SUBDIR = "research-digest"
DIGEST_TYPE = "research-digest"
NAME = "digest-index-rescan-0123456789ab"
HASH_A = "a" * 40
HASH_B = "b" * 40
SOURCES = [
    {"path": "agent-nelly/scripts/build_index.py", "hash": HASH_A},
    {"path": "agent-nelly/hooks/nelly_memory.py", "hash": HASH_B},
]
UPDATED = "2026-09-25T15:40:00Z"
TOPIC = "How the nelly index rescan walks entries subdirs"


@pytest.fixture(autouse=True)
def isolated_base(tmp_path, monkeypatch):
    base = str(tmp_path / "agent-nelly-memory")
    monkeypatch.setattr(nelly_memory, "BASE", base)
    monkeypatch.setattr(build_index, "BASE", base)
    return tmp_path


def _write_digest(cwd, name=NAME):
    """Write a digest per design.md's data contract directly under
    <memory_dir>/entries/research-digest/ (no Slice 3 helper used)."""
    d = os.path.join(nelly_memory.memory_dir(cwd), "entries", DIGEST_SUBDIR)
    os.makedirs(d, exist_ok=True)
    lines = [
        "---",
        f"name: {name}",
        f"description: {TOPIC}",
        f"type: {DIGEST_TYPE}",
        f"topic: {TOPIC}",
        "sources:",
    ]
    for s in SOURCES:
        lines += [f"  - path: {s['path']}", f"    hash: {s['hash']}"]
    lines += [f"updated: {UPDATED}", "---", "Summary body of the research."]
    path = os.path.join(d, f"{name}.md")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    return path


def _assert_digest_record(rec):
    assert rec["slug"] == NAME
    assert rec["type"] == DIGEST_TYPE
    assert rec["topic"] == TOPIC
    assert rec["updated"] == UPDATED
    assert rec["sources"] == SOURCES  # exact list, file order preserved
    assert rec["file_path"] == os.path.join("entries", DIGEST_SUBDIR, f"{NAME}.md")


def test_build_project_index_includes_nested_digest_with_digest_fields(tmp_path):
    cwd = str(tmp_path / "project")
    _write_digest(cwd)

    records = build_index.build_project_index(cwd)

    assert [r["slug"] for r in records] == [NAME]
    _assert_digest_record(records[0])


def test_upsert_nested_digest_yields_same_record_as_full_rescan(tmp_path):
    cwd = str(tmp_path / "project")
    path = _write_digest(cwd)

    upserted = build_index.upsert_project_entry(cwd, path)
    assert len(upserted) == 1
    _assert_digest_record(upserted[0])

    rescanned = build_index.build_project_index(cwd)
    assert len(rescanned) == 1
    _assert_digest_record(rescanned[0])
    assert upserted[0] == rescanned[0]


def test_digest_survives_full_rescan_after_upsert(tmp_path):
    """The upsert path already works via relpath; the full rescan must not
    drop the digest record the upsert put in the index."""
    cwd = str(tmp_path / "project")
    path = _write_digest(cwd)
    build_index.upsert_project_entry(cwd, path)

    records = build_index.build_project_index(cwd)

    assert NAME in [r["slug"] for r in records]
