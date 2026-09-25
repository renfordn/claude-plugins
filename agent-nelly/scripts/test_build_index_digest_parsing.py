"""Slice 5 review follow-ups: digest frontmatter parsing tolerates quoting, zero-indent lists,
and hash-before-path items; non-digest records stay minimal; a mixed store indexes each entry
exactly once."""
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


def _digest_block(sources_lines, topic="T", updated="2026-09-25T15:40:00Z"):
    return "\n".join(["name: digest-x", "description: d", "type: research-digest",
                      f"topic: {topic}", "sources:", *sources_lines, f"updated: {updated}"])


def test_quoted_digest_scalars_are_unquoted():
    block = _digest_block(['  - path: "a.py"', "    hash: 'abc'"],
                          topic='"Quoted topic"', updated='"2026-09-25T15:40:00Z"')
    rec = build_index._parse_frontmatter_block(block)
    assert rec["topic"] == "Quoted topic"
    assert rec["updated"] == "2026-09-25T15:40:00Z"
    assert rec["sources"] == [{"path": "a.py", "hash": "abc"}]


def test_zero_indent_sources_list_is_parsed():
    block = _digest_block(["- path: a.py", "  hash: h1", "- path: b.py", "  hash: h2"])
    rec = build_index._parse_frontmatter_block(block)
    assert rec["sources"] == [{"path": "a.py", "hash": "h1"}, {"path": "b.py", "hash": "h2"}]


def test_hash_before_path_items_are_parsed():
    block = _digest_block(["  - hash: h1", "    path: a.py", "  - hash: h2", "    path: b.py"])
    rec = build_index._parse_frontmatter_block(block)
    assert rec["sources"] == [{"path": "a.py", "hash": "h1"}, {"path": "b.py", "hash": "h2"}]


def test_non_digest_records_carry_no_digest_keys():
    block = "name: f\ndescription: d\nmetadata:\n  type: project\n"
    rec = build_index._parse_frontmatter_block(block)
    assert not {"topic", "sources", "updated"} & set(rec)


def test_mixed_store_indexes_each_entry_exactly_once(tmp_path):
    cwd = str(tmp_path / "project")
    flat = nelly_memory.ensure_entries_dir(cwd)
    summ = nelly_memory.ensure_entries_dir(cwd, entry_type="file-summary")
    dig = nelly_memory.ensure_entries_dir(cwd, entry_type=nelly_memory.DIGEST_TYPE)
    with open(os.path.join(flat, "fact.md"), "w") as fh:
        fh.write("---\nname: fact\ndescription: d\nmetadata:\n  type: project\n---\n")
    with open(os.path.join(summ, "file-summary-a.md"), "w") as fh:
        fh.write("---\nname: file-summary-a\ndescription: d\nmetadata:\n  type: file-summary\n"
                 "  files: [a.py]\n---\n")
    with open(os.path.join(dig, "digest-x.md"), "w") as fh:
        fh.write("---\n" + _digest_block(["  - path: a.py", "    hash: h1"]) + "\n---\nBody\n")

    records = build_index.build_project_index(cwd)

    assert sorted(r["slug"] for r in records) == ["digest-x", "fact", "file-summary-a"]
    by_slug = {r["slug"]: r for r in records}
    assert by_slug["digest-x"]["file_path"] == os.path.join("entries", "research-digest", "digest-x.md")
    assert by_slug["file-summary-a"]["file_path"] == os.path.join(
        "entries", nelly_memory.SUMMARY_SUBDIR, "file-summary-a.md")


# ---------------------------------------------------------------------------
# Slice 6 review follow-ups
# ---------------------------------------------------------------------------

def test_list_item_starting_with_other_key_starts_new_item():
    block = _digest_block(["  - path: a.py", "    hash: h1",
                           "  - note: x", "    path: b.py", "    hash: h2"])
    rec = build_index._parse_frontmatter_block(block)
    assert rec["sources"] == [{"path": "a.py", "hash": "h1"}, {"path": "b.py", "hash": "h2"}]


def test_empty_topic_and_updated_do_not_capture_next_line():
    block = "\n".join(["name: digest-x", "description: d", "type: research-digest",
                       "topic:", "updated:", "sources:", "  - path: a.py", "    hash: h1"])
    rec = build_index._parse_frontmatter_block(block)
    assert rec["topic"] is None
    assert rec["updated"] is None
    assert rec["sources"] == [{"path": "a.py", "hash": "h1"}]


def test_blank_line_inside_sources_block_keeps_later_items():
    block = _digest_block(["  - path: a.py", "    hash: h1", "",
                           "  - path: b.py", "    hash: h2"])
    rec = build_index._parse_frontmatter_block(block)
    assert rec["sources"] == [{"path": "a.py", "hash": "h1"}, {"path": "b.py", "hash": "h2"}]


def test_upsert_of_conflict_copy_does_not_add_a_record(tmp_path):
    cwd = str(tmp_path / "project")
    entries = nelly_memory.ensure_entries_dir(cwd)
    body = "---\nname: fact\ndescription: d\nmetadata:\n  type: project\n---\n"
    for fname in ("fact.md", "fact 2.md"):
        with open(os.path.join(entries, fname), "w") as fh:
            fh.write(body)
    build_index.build_project_index(cwd)

    records = build_index.upsert_project_entry(cwd, os.path.join(entries, "fact 2.md"))

    assert [r["file_path"] for r in records] == [os.path.join("entries", "fact.md")]


def test_upsert_of_conflict_copy_removes_its_stale_index_record(tmp_path):
    import json
    cwd = str(tmp_path / "project")
    entries = nelly_memory.ensure_entries_dir(cwd)
    body = "---\nname: fact\ndescription: d\nmetadata:\n  type: project\n---\n"
    for fname in ("fact.md", "fact 2.md"):
        with open(os.path.join(entries, fname), "w") as fh:
            fh.write(body)
    build_index.build_project_index(cwd)
    index_path = os.path.join(nelly_memory.memory_dir(cwd), build_index.INDEX_FILENAME)
    with open(index_path) as fh:
        records = json.load(fh)
    records.append(dict(records[0], file_path=os.path.join("entries", "fact 2.md")))
    with open(index_path, "w") as fh:
        json.dump(records, fh)

    build_index.upsert_project_entry(cwd, os.path.join(entries, "fact 2.md"))

    with open(index_path) as fh:
        assert [r["file_path"] for r in json.load(fh)] == [os.path.join("entries", "fact.md")]
