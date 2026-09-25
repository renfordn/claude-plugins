"""Slice 6: iCloud conflict copies (`<name> 2.md`) are ignored by the index build.

iCloud Drive writes a conflicting duplicate as `<name> <N>.md` (space + digits). Such a copy
carries the same frontmatter as its original, so indexing it would produce a duplicate record.
Names that merely contain a digit (`v2.md`, `fact-2.md`) are real entries and must be kept.
"""
import os

import pytest

import build_index
import nelly_memory

NESTED_SUBDIR = "file-folder-summary"


@pytest.fixture(autouse=True)
def isolated_base(tmp_path, monkeypatch):
    base = str(tmp_path / "agent-nelly-memory")
    monkeypatch.setattr(nelly_memory, "BASE", base)
    monkeypatch.setattr(build_index, "BASE", base)
    return tmp_path


def _write(dir_path, filename, slug, type_="project"):
    os.makedirs(dir_path, exist_ok=True)
    text = "\n".join([
        "---", f"name: {slug}", "description: A test entry.",
        "metadata:", f"  type: {type_}", "  last_referenced: 2026-09-25",
        "---", "", "Body text.",
    ])
    with open(os.path.join(dir_path, filename), "w", encoding="utf-8") as fh:
        fh.write(text)


def _entries_dir(cwd):
    return os.path.join(nelly_memory.memory_dir(cwd), "entries")


def test_flat_conflict_copy_is_not_indexed(tmp_path):
    cwd = str(tmp_path / "project")
    entries = _entries_dir(cwd)
    _write(entries, "fact.md", "fact")
    _write(entries, "fact 2.md", "fact")  # iCloud conflict copy: same frontmatter

    records = build_index.build_project_index(cwd)

    paths = sorted(r["file_path"] for r in records)
    assert paths == [os.path.join("entries", "fact.md")]
    assert [r["slug"] for r in records] == ["fact"]


def test_nested_conflict_copy_is_not_indexed(tmp_path):
    cwd = str(tmp_path / "project")
    entries = _entries_dir(cwd)
    nested = os.path.join(entries, NESTED_SUBDIR)
    _write(entries, "fact.md", "fact")
    _write(entries, "fact 2.md", "fact")
    _write(nested, "digest-a.md", "digest-a", type_="file-summary")
    _write(nested, "digest-a 2.md", "digest-a", type_="file-summary")

    records = build_index.build_project_index(cwd)

    paths = sorted(r["file_path"] for r in records)
    assert paths == sorted([
        os.path.join("entries", "fact.md"),
        os.path.join("entries", NESTED_SUBDIR, "digest-a.md"),
    ])
    assert sorted(r["slug"] for r in records) == ["digest-a", "fact"]


def test_conflict_copy_is_skipped_on_disk_rescan_of_index_json(tmp_path):
    """The persisted nelly-index.json must match the returned records (no conflict copy)."""
    import json
    cwd = str(tmp_path / "project")
    entries = _entries_dir(cwd)
    _write(entries, "fact.md", "fact")
    _write(entries, "fact 12.md", "fact")  # multi-digit suffix is still a conflict copy

    build_index.build_project_index(cwd)

    index_path = os.path.join(nelly_memory.memory_dir(cwd), build_index.INDEX_FILENAME)
    with open(index_path, encoding="utf-8") as fh:
        persisted = json.load(fh)
    assert [r["file_path"] for r in persisted] == [os.path.join("entries", "fact.md")]


def test_digit_bearing_names_without_space_are_not_skipped(tmp_path):
    cwd = str(tmp_path / "project")
    entries = _entries_dir(cwd)
    _write(entries, "v2.md", "v2")
    _write(entries, "fact-2.md", "fact-2")

    records = build_index.build_project_index(cwd)

    assert sorted(r["slug"] for r in records) == ["fact-2", "v2"]


@pytest.mark.parametrize("name,expected", [
    ("fact 2.md", True),
    ("digest-a 2.md", True),
    ("fact 12.md", True),
    ("fact.md", False),
    ("v2.md", False),
    ("fact-2.md", False),
])
def test_is_conflict_copy_public_helper(name, expected):
    assert hasattr(build_index, "is_conflict_copy"), \
        "build_index.is_conflict_copy(name) must be public (reused by research_digest scan)"
    assert build_index.is_conflict_copy(name) is expected


def test_research_digest_conflict_copy_is_not_indexed(tmp_path):
    cwd = str(tmp_path / "project")
    digests = os.path.join(_entries_dir(cwd), "research-digest")
    _write(digests, "digest-a.md", "digest-a", type_="research-digest")
    _write(digests, "digest-a 2.md", "digest-a", type_="research-digest")

    records = build_index.build_project_index(cwd)

    assert [r["file_path"] for r in records] == [
        os.path.join("entries", "research-digest", "digest-a.md")]
