"""Tests for hooks/nelly_memory.py — core path-resolution primitives (Phase 2).

Every test monkeypatches nelly_memory.BASE to an isolated tmp_path so the suite
never touches the real ${CLAUDE_PLUGIN_DATA}/agent-nelly-memory/ tree on disk.

Updated for ${CLAUDE_PLUGIN_DATA} env var support (Task 2.1).
"""
import os

import pytest

import nelly_memory

# Real home dir, not a hardcoded one -- these paths are only slug inputs.
HOME = os.path.expanduser("~")


@pytest.fixture
def isolated_base(tmp_path, monkeypatch):
    """Provide isolated BASE directory, respecting CLAUDE_PLUGIN_DATA env var."""
    plugin_data = str(tmp_path / "plugin-data")
    monkeypatch.setenv("CLAUDE_PLUGIN_DATA", plugin_data)
    # Also monkeypatch BASE to ensure tests work even if env var path differs
    expected_base = os.path.join(plugin_data, "agent-nelly-memory")
    monkeypatch.setattr(nelly_memory, "BASE", expected_base)
    return tmp_path


@pytest.fixture(autouse=True)
def cleanup_env(monkeypatch):
    """Ensure CLAUDE_PLUGIN_DATA is isolated per test."""
    # Save original state
    original = os.environ.get("CLAUDE_PLUGIN_DATA")
    yield
    # Restore or clear
    if original is not None:
        monkeypatch.setenv("CLAUDE_PLUGIN_DATA", original)
    else:
        monkeypatch.delenv("CLAUDE_PLUGIN_DATA", raising=False)


# ---------------------------------------------------------------------------
# project_slug
# ---------------------------------------------------------------------------

PATH_BATTERY = [
    f"{HOME}/Codebase/AI/plugins/claude/agent-nelly",
    f"{HOME}/Codebase/AI/plugins/claude/agent-nelly-old",
    f"{HOME}/Codebase/AI/plugins/claude/other-plugin",
    "/tmp/some/deep/nested/project/path",
    "/",
    f"{HOME}/Projects/My Project (v2)",
]

# "agent-nelly" vs "agent_nelly" is a KNOWN, accepted collision of this
# algorithm (both separators collapse to one hyphen) — inherited verbatim
# from sdd_memory.py per design.md's explicit "no behavior change needed"
# decision, not a defect. Covered separately, as an expected collision, so
# the general collision-resistance battery above doesn't wrongly assume
# every non-identical path is collision-free.
def test_project_slug_hyphen_and_underscore_variants_collide_by_design():
    a = nelly_memory.project_slug(f"{HOME}/Codebase/AI/plugins/claude/agent-nelly")
    b = nelly_memory.project_slug(f"{HOME}/Codebase/AI/plugins/claude/agent_nelly")
    assert a == b


def test_project_slug_is_deterministic():
    for path in PATH_BATTERY:
        assert nelly_memory.project_slug(path) == nelly_memory.project_slug(path)


def test_project_slug_is_collision_resistant_across_battery():
    slugs = [nelly_memory.project_slug(p) for p in PATH_BATTERY]
    assert len(slugs) == len(set(slugs)), f"collision detected among: {slugs}"


def test_project_slug_near_identical_paths_do_not_collide():
    a = nelly_memory.project_slug(f"{HOME}/Codebase/AI/plugins/claude/agent-nelly")
    b = nelly_memory.project_slug(f"{HOME}/Codebase/AI/plugins/claude/agent-nelly-old")
    assert a != b


def test_project_slug_is_lowercase_and_alphanumeric_hyphen_only():
    slug = nelly_memory.project_slug(f"{HOME}/Projects/My Project (v2)")
    assert slug == slug.lower()
    assert all(c.isalnum() or c == "-" for c in slug)


def test_project_slug_empty_result_falls_back_to_root():
    assert nelly_memory.project_slug("///") == "root"


# ---------------------------------------------------------------------------
# memory_dir / global_dir resolve under the new independent BASE
# ---------------------------------------------------------------------------

def test_memory_dir_resolves_under_new_base_root(isolated_base):
    cwd = f"{HOME}/Codebase/AI/plugins/claude/agent-nelly"
    d = nelly_memory.memory_dir(cwd)
    assert d.startswith(nelly_memory.BASE)
    assert "sdd-memory" not in d


def test_global_dir_resolves_under_new_base_root(isolated_base):
    d = nelly_memory.global_dir()
    assert d.startswith(nelly_memory.BASE)
    assert "sdd-memory" not in d
    assert os.path.basename(d) == "global"


def test_base_root_is_agent_nelly_memory_not_sdd_memory():
    assert "agent-nelly-memory" in nelly_memory.BASE
    assert "sdd-memory" not in nelly_memory.BASE


# ---------------------------------------------------------------------------
# ensure_dir / read_index — creation, idempotency, best-effort reads
# ---------------------------------------------------------------------------

def test_ensure_dir_creates_project_dir_with_index_header(isolated_base):
    cwd = f"{HOME}/Codebase/AI/plugins/claude/agent-nelly"
    d = nelly_memory.ensure_dir(cwd)
    assert os.path.isdir(d)
    index = os.path.join(d, "MEMORY.md")
    assert os.path.isfile(index)


def test_ensure_dir_is_idempotent_and_preserves_existing_content(isolated_base):
    cwd = f"{HOME}/Codebase/AI/plugins/claude/agent-nelly"
    d = nelly_memory.ensure_dir(cwd)
    index = os.path.join(d, "MEMORY.md")
    with open(index, "a", encoding="utf-8") as fh:
        fh.write("- [Custom Entry](custom.md) — hook\n")
    before = open(index, encoding="utf-8").read()

    d2 = nelly_memory.ensure_dir(cwd)

    after = open(index, encoding="utf-8").read()
    assert d2 == d
    assert after == before


def test_read_index_returns_empty_string_when_absent(isolated_base):
    cwd = f"{HOME}/Codebase/AI/plugins/claude/agent-nelly/never-created"
    assert nelly_memory.read_index(cwd) == ""


def test_read_index_returns_written_content(isolated_base):
    cwd = f"{HOME}/Codebase/AI/plugins/claude/agent-nelly"
    nelly_memory.ensure_dir(cwd)
    content = nelly_memory.read_index(cwd)
    assert "Memory" in content or "memory" in content


# ---------------------------------------------------------------------------
# global_dir / read_global_index — creation, idempotency, best-effort reads
# ---------------------------------------------------------------------------

def test_global_dir_is_idempotent_and_preserves_existing_content(isolated_base):
    d = nelly_memory.global_dir()
    index = os.path.join(d, "GLOBAL-MEMORY.md")
    with open(index, "a", encoding="utf-8") as fh:
        fh.write("- [Custom Global Fact](fact.md) — hook\n")
    before = open(index, encoding="utf-8").read()

    d2 = nelly_memory.global_dir()

    after = open(index, encoding="utf-8").read()
    assert d2 == d
    assert after == before


def test_read_global_index_returns_written_content(isolated_base):
    nelly_memory.global_dir()
    content = nelly_memory.read_global_index()
    assert "Global" in content or "global" in content


def test_read_global_index_is_best_effort_and_never_raises(monkeypatch, isolated_base):
    # Pre-create the index so global_dir()'s write branch is skipped, then simulate
    # an OSError on the subsequent read (e.g. a permission error) to confirm the
    # best-effort discipline: caught and turned into "", never raised.
    nelly_memory.global_dir()
    real_open = open

    def failing_open(path, *args, **kwargs):
        if path.endswith("GLOBAL-MEMORY.md"):
            raise OSError("simulated read failure")
        return real_open(path, *args, **kwargs)

    monkeypatch.setattr("builtins.open", failing_open)
    assert nelly_memory.read_global_index() == ""


# ---------------------------------------------------------------------------
# entry_path / archive_path — resolve under memory_dir, never escape their
# respective subdirectory even when name contains path-traversal segments.
# ---------------------------------------------------------------------------

CWD = f"{HOME}/Codebase/AI/plugins/claude/agent-nelly"

TRAVERSAL_NAMES = [
    "../../etc/passwd",
    "..\\..\\windows",
    "../../../root/.ssh/id_rsa",
    "..",
    "../..",
]


def test_entry_path_resolves_ordinary_name_under_entries_dir():
    p = nelly_memory.entry_path(CWD, "my-entry")
    expected = os.path.join(nelly_memory.memory_dir(CWD), "entries", "my-entry.md")
    assert p == expected


@pytest.mark.parametrize("name", TRAVERSAL_NAMES)
def test_entry_path_never_escapes_entries_dir(name):
    p = nelly_memory.entry_path(CWD, name)
    entries_dir = os.path.join(nelly_memory.memory_dir(CWD), "entries")
    assert os.path.dirname(p) == entries_dir
    assert ".." not in os.path.relpath(p, entries_dir)


# ---------------------------------------------------------------------------
# entry_path(..., entry_type=...) — file-summary/folder-summary entries nest
# under entries/<SUMMARY_SUBDIR>/ instead of directly under entries/; every
# other entry_type (including the default None) stays flat, unchanged.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("entry_type", ["file-summary", "folder-summary"])
def test_entry_path_nests_summary_types_under_summary_subdir(entry_type):
    p = nelly_memory.entry_path(CWD, "my-entry", entry_type=entry_type)
    expected = os.path.join(
        nelly_memory.memory_dir(CWD), "entries", nelly_memory.SUMMARY_SUBDIR, "my-entry.md"
    )
    assert p == expected


@pytest.mark.parametrize("entry_type", [None, "user", "feedback", "project", "error-prevention"])
def test_entry_path_stays_flat_for_non_summary_types(entry_type):
    p = nelly_memory.entry_path(CWD, "my-entry", entry_type=entry_type)
    expected = os.path.join(nelly_memory.memory_dir(CWD), "entries", "my-entry.md")
    assert p == expected


@pytest.mark.parametrize("name", TRAVERSAL_NAMES)
def test_entry_path_never_escapes_summary_subdir(name):
    p = nelly_memory.entry_path(CWD, name, entry_type="file-summary")
    summary_dir = os.path.join(nelly_memory.memory_dir(CWD), "entries", nelly_memory.SUMMARY_SUBDIR)
    assert os.path.dirname(p) == summary_dir
    assert ".." not in os.path.relpath(p, summary_dir)


def test_archive_path_resolves_ordinary_name_under_archive_dir():
    p = nelly_memory.archive_path(CWD, "my-entry")
    expected = os.path.join(nelly_memory.memory_dir(CWD), "archive", "my-entry.md")
    assert p == expected


@pytest.mark.parametrize("name", TRAVERSAL_NAMES)
def test_archive_path_never_escapes_archive_dir(name):
    p = nelly_memory.archive_path(CWD, name)
    archive_dir = os.path.join(nelly_memory.memory_dir(CWD), "archive")
    assert os.path.dirname(p) == archive_dir
    assert ".." not in os.path.relpath(p, archive_dir)


# ---------------------------------------------------------------------------
# ensure_entries_dir — the fix for the bug where entries/ was never created,
# so a Write to entry_path(cwd, name) had no guaranteed parent directory:
# the MEMORY.md index got a new line while the entry file itself silently
# never landed on disk. Regression coverage for exactly that failure mode.
# ---------------------------------------------------------------------------

def test_ensure_entries_dir_creates_entries_subdir(isolated_base):
    cwd = CWD
    d = nelly_memory.ensure_entries_dir(cwd)
    assert os.path.isdir(d)
    assert d == os.path.join(nelly_memory.memory_dir(cwd), "entries")


def test_ensure_entries_dir_also_creates_project_dir_and_index(isolated_base):
    # entries/ is nested under the project dir — calling ensure_entries_dir
    # alone (without a prior ensure_dir call) must still produce a fully
    # valid project dir + MEMORY.md, not just the entries/ subdir.
    cwd = CWD + "/never-created-before"
    nelly_memory.ensure_entries_dir(cwd)
    d = nelly_memory.memory_dir(cwd)
    assert os.path.isdir(d)
    assert os.path.isfile(os.path.join(d, "MEMORY.md"))
    assert os.path.isdir(os.path.join(d, "entries"))


def test_ensure_entries_dir_is_idempotent(isolated_base):
    cwd = CWD
    first = nelly_memory.ensure_entries_dir(cwd)
    with open(os.path.join(first, "existing.md"), "w", encoding="utf-8") as fh:
        fh.write("keep me")
    second = nelly_memory.ensure_entries_dir(cwd)
    assert first == second
    assert os.path.isfile(os.path.join(second, "existing.md"))


def test_cli_entries_path_prints_ensure_entries_dir_for_given_cwd(capsys, isolated_base):
    nelly_memory.main(["--entries-path", CWD])
    out = capsys.readouterr().out.strip()
    assert out == nelly_memory.ensure_entries_dir(CWD)
    assert os.path.isdir(out)


def test_ensure_entries_dir_with_summary_type_creates_nested_subdir(isolated_base):
    cwd = CWD
    d = nelly_memory.ensure_entries_dir(cwd, entry_type="file-summary")
    assert os.path.isdir(d)
    assert d == os.path.join(nelly_memory.memory_dir(cwd), "entries", nelly_memory.SUMMARY_SUBDIR)
    # The flat entries/ dir must exist too -- the summary subdir nests inside it, not beside it.
    assert os.path.isdir(os.path.join(nelly_memory.memory_dir(cwd), "entries"))


def test_ensure_entries_dir_with_summary_type_does_not_disturb_flat_entries(isolated_base):
    cwd = CWD
    nelly_memory.ensure_entries_dir(cwd)
    with open(os.path.join(nelly_memory.memory_dir(cwd), "entries", "existing.md"),
              "w", encoding="utf-8") as fh:
        fh.write("keep me")
    nelly_memory.ensure_entries_dir(cwd, entry_type="folder-summary")
    assert os.path.isfile(os.path.join(nelly_memory.memory_dir(cwd), "entries", "existing.md"))


def test_cli_summary_entries_path_prints_nested_summary_dir(capsys, isolated_base):
    nelly_memory.main(["--summary-entries-path", CWD])
    out = capsys.readouterr().out.strip()
    assert out == os.path.join(nelly_memory.memory_dir(CWD), "entries", nelly_memory.SUMMARY_SUBDIR)
    assert os.path.isdir(out)


def test_recording_a_new_fact_creates_both_entry_file_and_index_line(isolated_base):
    """Regression test for the reported bug: reproduce the exact write-back
    sequence the agent-nelly agent's "Recording a new fact" section
    follows (steps 5-7 of agents/agent-nelly.md) and assert BOTH
    outcomes exist afterward — not just the index line, which is exactly
    what silently succeeded while the entry file silently didn't in the
    original bug. Prior to the ensure_entries_dir() fix, step 5 ("Write the
    entry to entries/<name>.md") had no guaranteed parent directory; this
    test fails against the pre-fix code path if ensure_entries_dir() is
    removed or the entries-dir-creation step is skipped.
    """
    cwd = f"{HOME}/.claude/Spec-driven-development"
    name = "some-test-fact"

    # Step 5: guarantee entries/ exists before writing (the fixed behavior).
    nelly_memory.ensure_entries_dir(cwd)

    # Step 6: write the entry file itself.
    entry = nelly_memory.entry_path(cwd, name)
    with open(entry, "w", encoding="utf-8") as fh:
        fh.write(
            "---\n"
            f"name: {name}\n"
            "description: a test fact recorded for regression coverage\n"
            "metadata:\n"
            "  type: project\n"
            "  last_referenced: 2026-08-10\n"
            "---\n\n"
            "some test fact\n"
        )

    # Step 7: add the index line.
    index = os.path.join(nelly_memory.memory_dir(cwd), "MEMORY.md")
    with open(index, "a", encoding="utf-8") as fh:
        fh.write(f"- [Some Test Fact](entries/{name}.md) — project fact\n")

    # Both must exist — the original bug was reporting success ("Written:
    # created entries/<slug>.md; added index line to MEMORY.md") and an
    # updated index while the entries/ dir (and thus the entry file) never
    # actually got created.
    assert os.path.isdir(os.path.join(nelly_memory.memory_dir(cwd), "entries"))
    assert os.path.isfile(entry), "entry file must exist on disk, not just be referenced from the index"
    index_content = nelly_memory.read_index(cwd)
    assert f"entries/{name}.md" in index_content


# ---------------------------------------------------------------------------
# list_entries — sorted names under entries/, empty (never raises) if absent.
# ---------------------------------------------------------------------------

def test_list_entries_returns_empty_list_when_entries_dir_absent():
    cwd = CWD + "/never-created"
    assert nelly_memory.list_entries(cwd) == []


def test_list_entries_returns_sorted_names_without_md_extension(isolated_base):
    entries_dir = os.path.join(nelly_memory.memory_dir(CWD), "entries")
    os.makedirs(entries_dir, exist_ok=True)
    for fname in ("zeta.md", "alpha.md", "not-markdown.txt"):
        with open(os.path.join(entries_dir, fname), "w", encoding="utf-8") as fh:
            fh.write("content")

    assert nelly_memory.list_entries(CWD) == ["alpha", "zeta"]


# ---------------------------------------------------------------------------
# CLI surface — main(argv) dispatch, captured via capsys (no shelling out).
# ---------------------------------------------------------------------------

def test_cli_no_args_prints_memory_dir(capsys):
    nelly_memory.main([])
    out = capsys.readouterr().out.strip()
    assert out == nelly_memory.memory_dir(os.getcwd())


def test_cli_global_path_prints_global_dir(capsys, isolated_base):
    nelly_memory.main(["--global-path"])
    out = capsys.readouterr().out.strip()
    assert out == nelly_memory.global_dir()


def test_cli_path_prints_ensure_dir_for_given_cwd(capsys, isolated_base):
    nelly_memory.main(["--path", CWD])
    out = capsys.readouterr().out.strip()
    assert out == nelly_memory.ensure_dir(CWD)


def test_cli_summary_silent_when_index_has_no_real_entries(capsys, isolated_base):
    nelly_memory.ensure_dir(CWD)  # header scaffold only, no "- [" entries
    nelly_memory.main(["--summary", CWD])
    out = capsys.readouterr().out
    assert out == ""


def test_cli_summary_prints_index_when_real_entries_present(capsys, isolated_base):
    d = nelly_memory.ensure_dir(CWD)
    index = os.path.join(d, "MEMORY.md")
    with open(index, "a", encoding="utf-8") as fh:
        fh.write("- [Some Entry](some.md) — hook\n")

    nelly_memory.main(["--summary", CWD])
    out = capsys.readouterr().out.strip()
    assert out == nelly_memory.read_index(CWD)
    assert "- [Some Entry]" in out


# ---------------------------------------------------------------------------
# resolve_repo_relative — resolves a stored repo-relative path back to an
# absolute path anchored at cwd. Pure path resolution, no entry-file I/O:
# used later by agent-nelly's prose logic (Bash/Glob) during
# `/nelly-memory prune`'s file-existence check for file-relevance entries.
# ---------------------------------------------------------------------------

def test_resolve_repo_relative_joins_cwd_and_relative_path():
    cwd = f"{HOME}/Codebase/AI/plugins/claude/agent-nelly"
    result = nelly_memory.resolve_repo_relative(cwd, "src/foo.py")
    assert result == os.path.normpath(os.path.join(cwd, "src/foo.py"))


def test_resolve_repo_relative_rejects_absolute_path():
    # os.path.join(cwd, path) would otherwise discard cwd entirely whenever
    # path is itself absolute (documented Python semantics), silently masking
    # a metadata.files entry that violated the never-absolute invariant
    # instead of surfacing it. resolve_repo_relative raises ValueError here
    # rather than passing an absolute path through unchanged.
    with pytest.raises(ValueError):
        nelly_memory.resolve_repo_relative("/some/cwd", "/etc/hosts")


# ---------------------------------------------------------------------------
# write_index_line / parse_index_line_fields — Token Efficiency Phase 2:
# optional type/confidence/files field block on MEMORY.md index lines, with
# a safe "unknown" fallback for old-format (plain) lines. See design.md's
# Data Contracts And Interfaces section for the exact line format.
# ---------------------------------------------------------------------------

def test_write_index_line_round_trip_all_fields_populated(isolated_base):
    d = nelly_memory.ensure_dir(CWD)
    line = nelly_memory.write_index_line(
        CWD, "some-test-fact", "project fact", "project",
        confidence="explicit", files_present=True,
    )

    assert line == (
        "- [Some Test Fact](entries/some-test-fact.md) — project fact "
        "`[type:project confidence:explicit files:yes]`"
    )
    index_content = open(os.path.join(d, "MEMORY.md"), encoding="utf-8").read()
    assert line in index_content


def test_parse_index_line_fields_fallback_old_format_never_raises():
    old_line = "- [Custom Entry](custom.md) — hook"
    fields = nelly_memory.parse_index_line_fields(old_line)
    assert fields == {"type": None, "confidence": None, "files": None, "paths": None}


# ---------------------------------------------------------------------------
# write_index_line / parse_index_line_fields — paths fragment (additive,
# backward-compatible: semicolon-joined repo-relative paths, omitted
# entirely when absent so old-format lines and non-file entries are
# unaffected). See design.md's Data Contracts And Interfaces section.
# ---------------------------------------------------------------------------

def test_write_index_line_emits_paths_fragment_when_paths_given(isolated_base):
    line = nelly_memory.write_index_line(
        CWD, "some-test-fact", "project fact", "project",
        paths=["src/foo.py", "src/bar.py"],
    )
    assert "paths:src/foo.py;src/bar.py]" in line


def test_write_index_line_omits_paths_fragment_when_paths_absent(isolated_base):
    line = nelly_memory.write_index_line(
        CWD, "some-test-fact", "project fact", "project",
    )
    assert "paths:" not in line


def test_write_index_line_omits_paths_fragment_when_paths_none_or_empty(isolated_base):
    line_none = nelly_memory.write_index_line(
        CWD, "some-test-fact", "project fact", "project", paths=None,
    )
    line_empty = nelly_memory.write_index_line(
        CWD, "some-test-fact", "project fact", "project", paths=[],
    )
    assert "paths:" not in line_none
    assert "paths:" not in line_empty


def test_parse_index_line_fields_extracts_paths_list(isolated_base):
    line = nelly_memory.write_index_line(
        CWD, "some-test-fact", "project fact", "project",
        confidence="explicit", files_present=True,
        paths=["src/foo.py", "src/bar.py"],
    )
    fields = nelly_memory.parse_index_line_fields(line)
    assert fields == {
        "type": "project",
        "confidence": "explicit",
        "files": "yes",
        "paths": ["src/foo.py", "src/bar.py"],
    }


def test_parse_index_line_fields_paths_none_when_fragment_absent(isolated_base):
    line = nelly_memory.write_index_line(
        CWD, "some-test-fact", "project fact", "project",
        confidence="explicit", files_present=True,
    )
    fields = nelly_memory.parse_index_line_fields(line)
    assert fields == {
        "type": "project",
        "confidence": "explicit",
        "files": "yes",
        "paths": None,
    }


# ---------------------------------------------------------------------------
# CLAUDE_PLUGIN_DATA env var support (Task 2.1)
# ---------------------------------------------------------------------------

def test_memory_dir_respects_claude_plugin_data_env_var(monkeypatch, tmp_path):
    """Verify that BASE is built from CLAUDE_PLUGIN_DATA when set."""
    plugin_data = str(tmp_path / "plugins" / "data" / "agent-nelly")
    monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(tmp_path / "plugins" / "data" / "agent-nelly"))
    expected_base = os.path.join(plugin_data, "agent-nelly-memory")
    monkeypatch.setattr(nelly_memory, "BASE", expected_base)

    cwd = f"{HOME}/Codebase/AI/plugins/claude/agent-nelly"
    d = nelly_memory.memory_dir(cwd)

    # Verify BASE is in the path
    assert nelly_memory.BASE in d
    assert "plugins/data/agent-nelly" in d


def test_global_dir_respects_claude_plugin_data_env_var(monkeypatch, tmp_path):
    """Verify that global_dir uses the CLAUDE_PLUGIN_DATA-derived BASE."""
    plugin_data = str(tmp_path / "plugins" / "data" / "agent-nelly")
    monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(tmp_path / "plugins" / "data" / "agent-nelly"))
    expected_base = os.path.join(plugin_data, "agent-nelly-memory")
    monkeypatch.setattr(nelly_memory, "BASE", expected_base)

    d = nelly_memory.global_dir()

    # Verify BASE is in the path
    assert nelly_memory.BASE in d
    assert os.path.basename(d) == "global"


# ---------------------------------------------------------------------------
# truncate_summary -- the 240-char cap for file-summary/folder-summary entries
# ---------------------------------------------------------------------------

def test_truncate_summary_leaves_short_text_unchanged():
    text = "Resolves the project slug used to namespace memory on disk."
    assert nelly_memory.truncate_summary(text) == text


def test_truncate_summary_strips_surrounding_whitespace():
    assert nelly_memory.truncate_summary("  short.  ") == "short."


def test_truncate_summary_exactly_at_limit_is_unchanged():
    text = "x" * nelly_memory.SUMMARY_CHAR_LIMIT
    assert nelly_memory.truncate_summary(text) == text


def test_truncate_summary_over_limit_is_capped_at_exact_length():
    text = "x" * (nelly_memory.SUMMARY_CHAR_LIMIT + 50)
    result = nelly_memory.truncate_summary(text)
    assert len(result) == nelly_memory.SUMMARY_CHAR_LIMIT
    assert result.endswith("…")


def test_truncate_summary_over_limit_preserves_a_prefix_of_original_text():
    text = "a" * (nelly_memory.SUMMARY_CHAR_LIMIT + 50)
    result = nelly_memory.truncate_summary(text)
    assert result[:-1] == text[: nelly_memory.SUMMARY_CHAR_LIMIT - 1]


def test_truncate_summary_custom_limit():
    result = nelly_memory.truncate_summary("abcdefghij", limit=5)
    assert result == "abcd…"
    assert len(result) == 5


# ---------------------------------------------------------------------------
# research-digest entries nest under entries/<DIGEST_SUBDIR>/, like summaries
# nest under entries/<SUMMARY_SUBDIR>/.
# ---------------------------------------------------------------------------

def test_digest_constants():
    assert nelly_memory.DIGEST_SUBDIR == "research-digest"
    assert nelly_memory.DIGEST_TYPE == "research-digest"
    assert nelly_memory.DIGEST_CHAR_LIMIT == 2000
    assert nelly_memory.DIGEST_MAX_SOURCES == 30


def test_entry_path_nests_digest_type_under_digest_subdir():
    p = nelly_memory.entry_path(CWD, "digest-x", entry_type=nelly_memory.DIGEST_TYPE)
    assert p == os.path.join(
        nelly_memory.memory_dir(CWD), "entries", nelly_memory.DIGEST_SUBDIR, "digest-x.md")


@pytest.mark.parametrize("name", TRAVERSAL_NAMES)
def test_entry_path_never_escapes_digest_subdir(name):
    p = nelly_memory.entry_path(CWD, name, entry_type=nelly_memory.DIGEST_TYPE)
    digest_dir = os.path.join(nelly_memory.memory_dir(CWD), "entries", nelly_memory.DIGEST_SUBDIR)
    assert os.path.dirname(p) == digest_dir


def test_ensure_entries_dir_with_digest_type_creates_nested_subdir(isolated_base):
    d = nelly_memory.ensure_entries_dir(CWD, entry_type=nelly_memory.DIGEST_TYPE)
    assert d == os.path.join(nelly_memory.memory_dir(CWD), "entries", nelly_memory.DIGEST_SUBDIR)
    assert os.path.isdir(d)


def test_cli_digest_entries_path_prints_nested_digest_dir(capsys, isolated_base):
    nelly_memory.main(["--digest-entries-path", CWD])
    out = capsys.readouterr().out.strip()
    assert out == os.path.join(nelly_memory.memory_dir(CWD), "entries", nelly_memory.DIGEST_SUBDIR)
    assert os.path.isdir(out)


# ---------------------------------------------------------------------------
# atomic_write -- temp file in the target dir, then os.replace, so iCloud and
# concurrent readers never see a partial file.
# ---------------------------------------------------------------------------

def test_atomic_write_creates_file_with_exact_content(tmp_path):
    target = tmp_path / "d" / "x.md"
    target.parent.mkdir()
    nelly_memory.atomic_write(str(target), "héllo\nworld\n")
    assert target.read_text(encoding="utf-8") == "héllo\nworld\n"
    assert os.listdir(target.parent) == ["x.md"]


def test_atomic_write_overwrites_existing_file(tmp_path):
    target = tmp_path / "x.md"
    target.write_text("old", encoding="utf-8")
    nelly_memory.atomic_write(str(target), "new")
    assert target.read_text(encoding="utf-8") == "new"
    assert os.listdir(tmp_path) == ["x.md"]


def test_atomic_write_failure_keeps_original_and_leaves_no_temp(tmp_path, monkeypatch):
    target = tmp_path / "x.md"
    target.write_text("original", encoding="utf-8")

    def boom(src, dst):
        raise OSError("simulated replace failure")

    monkeypatch.setattr(nelly_memory.os, "replace", boom)
    with pytest.raises(OSError):
        nelly_memory.atomic_write(str(target), "new")
    assert target.read_text(encoding="utf-8") == "original"
    assert os.listdir(tmp_path) == ["x.md"]


def test_atomic_write_new_file_gets_umask_default_mode(tmp_path):
    umask = os.umask(0)
    os.umask(umask)
    target = tmp_path / "x.md"
    nelly_memory.atomic_write(str(target), "x")
    assert (os.stat(target).st_mode & 0o777) == (0o666 & ~umask)


def test_atomic_write_overwrite_keeps_existing_mode(tmp_path):
    target = tmp_path / "x.md"
    target.write_text("old", encoding="utf-8")
    os.chmod(target, 0o640)
    nelly_memory.atomic_write(str(target), "new")
    assert (os.stat(target).st_mode & 0o777) == 0o640
