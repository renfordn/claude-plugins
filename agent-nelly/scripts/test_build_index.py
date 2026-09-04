"""Tests for scripts/build_index.py -- the pre-index JSON builder that lets
nelly-orchestrator match relevance from one nelly-index.json read instead of
opening every entries/*.md file.
"""
import json
import os

import pytest

import build_index
import nelly_memory


@pytest.fixture(autouse=True)
def isolated_base(tmp_path, monkeypatch):
    base = str(tmp_path / "agent-nelly-memory")
    monkeypatch.setattr(nelly_memory, "BASE", base)
    monkeypatch.setattr(build_index, "BASE", base)
    return tmp_path


def _write_entry(cwd, name, type_="project", description="A test fact.",
                  confidence=None, tags=None, seen_count=None):
    entries_dir = nelly_memory.ensure_entries_dir(cwd)
    lines = ["---", f"name: {name}", f"description: {description}",
             "metadata:", f"  type: {type_}", "  last_referenced: 2026-08-16"]
    if confidence is not None:
        lines.append(f"  confidence: {confidence}")
    if seen_count is not None:
        lines.append(f"  seen_count: {seen_count}")
    if tags is not None:
        lines.append(f"  tags: [{', '.join(tags)}]")
    lines += ["---", "", "Body text."]
    path = os.path.join(entries_dir, f"{name}.md")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    return path


# ---------------------------------------------------------------------------
# _parse_frontmatter_block
# ---------------------------------------------------------------------------

def test_parse_frontmatter_block_basic_fields():
    block = (
        "name: some-fact\n"
        "description: A one-line summary.\n"
        "metadata:\n"
        "  type: project\n"
        "  last_referenced: 2026-08-16\n"
    )
    record = build_index._parse_frontmatter_block(block)
    assert record["slug"] == "some-fact"
    assert record["type"] == "project"
    assert record["confidence"] is None
    assert record["description"] == "A one-line summary."
    assert record["tags"] == []


def test_parse_frontmatter_block_confidence_and_tags():
    block = (
        "name: some-lesson\n"
        "description: A lesson.\n"
        "metadata:\n"
        "  type: error-prevention\n"
        "  confidence: explicit\n"
        "  tags: [python, subprocess]\n"
    )
    record = build_index._parse_frontmatter_block(block)
    assert record["confidence"] == "explicit"
    assert record["tags"] == ["python", "subprocess"]


def test_parse_frontmatter_block_description_first_line_only():
    block = (
        "name: multi\n"
        "description: First line here.\n"
        "metadata:\n"
        "  type: project\n"
    )
    record = build_index._parse_frontmatter_block(block)
    assert record["description"] == "First line here."


def test_parse_frontmatter_block_no_name_returns_none():
    block = "description: orphaned\nmetadata:\n  type: project\n"
    assert build_index._parse_frontmatter_block(block) is None


def test_parse_frontmatter_block_seen_count_present():
    block = (
        "name: some-lesson\n"
        "description: A lesson.\n"
        "metadata:\n"
        "  type: error-prevention\n"
        "  confidence: inferred\n"
        "  seen_count: 2\n"
    )
    record = build_index._parse_frontmatter_block(block)
    assert record["seen_count"] == 2


def test_parse_frontmatter_block_seen_count_absent_is_none():
    block = (
        "name: some-fact\n"
        "description: A one-line summary.\n"
        "metadata:\n"
        "  type: project\n"
    )
    record = build_index._parse_frontmatter_block(block)
    assert record["seen_count"] is None


# ---------------------------------------------------------------------------
# build_project_index (full rescan)
# ---------------------------------------------------------------------------

def test_build_project_index_empty_store_writes_empty_list(tmp_path):
    cwd = str(tmp_path / "project")
    records = build_index.build_project_index(cwd)
    assert records == []
    index_path = os.path.join(nelly_memory.memory_dir(cwd), build_index.INDEX_FILENAME)
    assert json.loads(open(index_path).read()) == []


def test_build_project_index_scans_all_entries(tmp_path):
    cwd = str(tmp_path / "project")
    _write_entry(cwd, "fact-a", description="Fact A.")
    _write_entry(cwd, "fact-b", type_="error-prevention", confidence="explicit",
                 description="Fact B.")

    records = build_index.build_project_index(cwd)

    slugs = {r["slug"] for r in records}
    assert slugs == {"fact-a", "fact-b"}
    by_slug = {r["slug"]: r for r in records}
    assert by_slug["fact-a"]["file_path"] == os.path.join("entries", "fact-a.md")
    assert by_slug["fact-b"]["confidence"] == "explicit"
    assert isinstance(by_slug["fact-a"]["mtime"], float)
    assert by_slug["fact-a"]["seen_count"] is None


def test_build_project_index_includes_seen_count(tmp_path):
    cwd = str(tmp_path / "project")
    _write_entry(cwd, "auto-fact", type_="error-prevention", confidence="inferred",
                 seen_count=2)

    records = build_index.build_project_index(cwd)

    assert records[0]["seen_count"] == 2


def test_build_project_index_sorted_by_slug(tmp_path):
    cwd = str(tmp_path / "project")
    _write_entry(cwd, "zzz-last")
    _write_entry(cwd, "aaa-first")

    records = build_index.build_project_index(cwd)

    assert [r["slug"] for r in records] == ["aaa-first", "zzz-last"]


# ---------------------------------------------------------------------------
# upsert_project_entry (lightweight, single-file)
# ---------------------------------------------------------------------------

def test_upsert_project_entry_adds_new_entry_without_full_rescan(tmp_path):
    cwd = str(tmp_path / "project")
    build_index.build_project_index(cwd)  # establishes an empty index first
    entry_path = _write_entry(cwd, "new-fact", description="Brand new.")

    records = build_index.upsert_project_entry(cwd, entry_path)

    assert [r["slug"] for r in records] == ["new-fact"]


def test_upsert_project_entry_updates_existing_record(tmp_path):
    cwd = str(tmp_path / "project")
    entry_path = _write_entry(cwd, "changeable", description="Original.")
    build_index.build_project_index(cwd)

    _write_entry(cwd, "changeable", description="Updated.")
    records = build_index.upsert_project_entry(cwd, entry_path)

    assert len(records) == 1
    assert records[0]["description"] == "Updated."


def test_upsert_project_entry_preserves_other_records(tmp_path):
    cwd = str(tmp_path / "project")
    _write_entry(cwd, "other-fact", description="Untouched.")
    entry_path = _write_entry(cwd, "target-fact", description="Original.")
    build_index.build_project_index(cwd)

    _write_entry(cwd, "target-fact", description="Changed.")
    records = build_index.upsert_project_entry(cwd, entry_path)

    slugs = {r["slug"] for r in records}
    assert slugs == {"other-fact", "target-fact"}


def test_upsert_project_entry_drops_record_when_file_deleted(tmp_path):
    cwd = str(tmp_path / "project")
    entry_path = _write_entry(cwd, "to-delete", description="Will vanish.")
    build_index.build_project_index(cwd)

    os.remove(entry_path)
    records = build_index.upsert_project_entry(cwd, entry_path)

    assert records == []


# ---------------------------------------------------------------------------
# build_global_index
# ---------------------------------------------------------------------------

def test_build_global_index_empty_when_no_entries():
    records = build_index.build_global_index()
    assert records == []


def test_build_global_index_parses_multiple_inline_blocks():
    d = nelly_memory.global_dir()
    source = os.path.join(d, "GLOBAL-MEMORY.md")
    with open(source, "a", encoding="utf-8") as fh:
        fh.write(
            "\n---\n"
            "name: global-fact-one\n"
            "description: First global fact.\n"
            "metadata:\n"
            "  type: reference\n"
            "  last_referenced: 2026-08-16\n"
            "---\n\nBody one.\n\n"
            "---\n"
            "name: global-fact-two\n"
            "description: Second global fact.\n"
            "metadata:\n"
            "  type: user\n"
            "  last_referenced: 2026-08-16\n"
            "---\n\nBody two.\n"
        )

    records = build_index.build_global_index()

    slugs = {r["slug"] for r in records}
    assert slugs == {"global-fact-one", "global-fact-two"}
    assert all(r["file_path"] == "GLOBAL-MEMORY.md" for r in records)


# ---------------------------------------------------------------------------
# build_all / iter_project_dirs
# ---------------------------------------------------------------------------

def test_build_all_covers_every_project_dir_and_global(tmp_path):
    cwd_a = str(tmp_path / "project-a")
    cwd_b = str(tmp_path / "project-b")
    _write_entry(cwd_a, "fact-in-a")
    _write_entry(cwd_b, "fact-in-b")

    build_index.build_all()

    index_a = os.path.join(nelly_memory.memory_dir(cwd_a), build_index.INDEX_FILENAME)
    index_b = os.path.join(nelly_memory.memory_dir(cwd_b), build_index.INDEX_FILENAME)
    global_index = os.path.join(nelly_memory.global_dir(), build_index.INDEX_FILENAME)
    assert os.path.isfile(index_a)
    assert os.path.isfile(index_b)
    assert os.path.isfile(global_index)


def test_iter_project_dirs_skips_global_and_hidden(tmp_path):
    base = tmp_path / "agent-nelly-memory"
    (base / "global").mkdir(parents=True)
    (base / "real-project").mkdir(parents=True)
    (base / ".DS_Store").touch()
    build_index.BASE = str(base)

    dirs = [os.path.basename(p) for p in build_index.iter_project_dirs()]

    assert dirs == ["real-project"]
