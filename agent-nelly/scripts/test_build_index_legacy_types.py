"""Slice 1 (R9): legacy `file_summary`/`folder_summary` entries on disk are indexed as
`file-summary`/`folder-summary`, so lookup_by_path() returns them. Files on disk are not
rewritten; normalization happens at index-build time.
"""
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


def _write_legacy_entry(cwd, name, type_, files=None, folder=None, nested=False):
    """Write an entry whose frontmatter carries `type_` verbatim. `nested=True` places it under
    entries/<SUMMARY_SUBDIR>/ (created via the hyphenated type, since ensure_entries_dir does not
    nest underscore types)."""
    entries_dir = nelly_memory.ensure_entries_dir(
        cwd, entry_type="file-summary" if nested else None)
    lines = ["---", f"name: {name}", "description: A legacy summary.",
             "metadata:", f"  type: {type_}", "  last_referenced: 2026-08-16"]
    if files is not None:
        lines.append(f"  files: [{', '.join(files)}]")
    if folder is not None:
        lines.append(f"  folder: {folder}")
    lines += ["---", "", "Body text."]
    path = os.path.join(entries_dir, f"{name}.md")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    return path


@pytest.mark.parametrize("nested", [False, True], ids=["flat", "nested"])
def test_legacy_file_summary_is_returned_by_lookup_by_path(tmp_path, nested):
    cwd = str(tmp_path / "project")
    path = _write_legacy_entry(cwd, "legacy-file-a", "file_summary",
                               files=["src/a.py"], nested=nested)
    if nested:
        assert os.path.dirname(path).endswith(
            os.path.join("entries", nelly_memory.SUMMARY_SUBDIR))
    build_index.build_project_index(cwd)

    result = build_index.lookup_by_path(cwd, "src/a.py")

    assert result["file"] is not None
    assert result["file"]["slug"] == "legacy-file-a"
    assert result["file"]["type"] == "file-summary"


def test_legacy_folder_summary_is_returned_by_lookup_by_path(tmp_path):
    cwd = str(tmp_path / "project")
    _write_legacy_entry(cwd, "legacy-folder-src", "folder_summary", folder="src")
    build_index.build_project_index(cwd)

    result = build_index.lookup_by_path(cwd, "src/x.py")

    assert [r["slug"] for r in result["folders"]] == ["legacy-folder-src"]
    assert result["folders"][0]["type"] == "folder-summary"


def test_legacy_types_normalized_in_index_records(tmp_path):
    cwd = str(tmp_path / "project")
    _write_legacy_entry(cwd, "legacy-file-a", "file_summary", files=["src/a.py"])
    _write_legacy_entry(cwd, "legacy-folder-src", "folder_summary", folder="src")

    records = build_index.build_project_index(cwd)

    types = {r["slug"]: r["type"] for r in records}
    assert types == {"legacy-file-a": "file-summary", "legacy-folder-src": "folder-summary"}


def test_legacy_entry_file_on_disk_is_not_rewritten(tmp_path):
    cwd = str(tmp_path / "project")
    path = _write_legacy_entry(cwd, "legacy-file-a", "file_summary", files=["src/a.py"])
    with open(path, encoding="utf-8") as fh:
        before = fh.read()

    build_index.build_project_index(cwd)

    with open(path, encoding="utf-8") as fh:
        assert fh.read() == before


@pytest.mark.parametrize("type_", ["project", "error-prevention", "file-summary"])
def test_non_legacy_types_pass_through_unchanged(tmp_path, type_):
    cwd = str(tmp_path / "project")
    _write_legacy_entry(cwd, "some-entry", type_)

    records = build_index.build_project_index(cwd)

    assert [r["type"] for r in records] == [type_]
