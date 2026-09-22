"""
Pins the Slice 2 rename requirement: the mechanical text-only reference
sweep (plugin-orchestrator -> plugin-harness) across the monorepo's
documentation, INTEROP contracts, and non-structural code/test files.

This test is expected to FAIL until the mechanical sweep is performed. It
intentionally excludes:
  - historical CHANGELOG.md entries (explicit carve-out, per requirements.md's
    EARS Event-driven line and design.md's Rename Plan)
  - files that are gitignored / not tracked by git (e.g. .claude/settings.local.json)
  - Slice 1's already-completed structural files (covered by
    test_plugin_harness_rename.py)
  - the sweep's own self-referential files: this test and its sibling
    verification test necessarily contain the literal old-name string, and a
    few plugin-harness test docstrings pin an SDD slice named after the
    rename itself (see SELF_REFERENTIAL_EXCEPTION_FILES)

The former PLUGIN_ORCHESTRATOR_TELEMETRY one-release compatibility fallback
(hook_telemetry.py) has since been removed, so it is no longer an exception
here.
"""
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


# Files whose old-name hits are the rename effort naming itself, not a
# leftover reference: this sweep test and its sibling verification test
# necessarily contain the literal string they grep for, and several
# plugin-harness test docstrings pin an SDD slice titled "Plugin-Orchestrator
# -> Plugin-Harness Rework" -- the slice's own name, not the old plugin path.
SELF_REFERENTIAL_EXCEPTION_FILES = {
    "shared/test_plugin_harness_rename.py",
    "shared/test_plugin_harness_rename_sweep.py",
    "shared/test_rename_verification.py",
    "plugin-harness/tests/test_harness_context_cache.py",
    "plugin-harness/tests/test_spawn_context.py",
    "plugin-harness/tests/test_standalone_spawn.py",
}


def _tracked_files_with_old_name():
    """Return tracked (git ls-files) paths containing the old plugin name,
    excluding CHANGELOG.md files anywhere in the repo and the sweep's own
    self-referential files (see SELF_REFERENTIAL_EXCEPTION_FILES)."""
    result = subprocess.run(
        ["git", "grep", "-l", "-i", "-e", "plugin-orchestrator", "-e", "plugin_orchestrator"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode not in (0, 1):
        raise RuntimeError(f"git grep failed: {result.stderr}")
    files = [line for line in result.stdout.splitlines() if line]
    return [
        f
        for f in files
        if Path(f).name != "CHANGELOG.md"
        and f not in SELF_REFERENTIAL_EXCEPTION_FILES
    ]


def test_no_tracked_non_changelog_file_references_old_plugin_name():
    remaining = _tracked_files_with_old_name()
    assert remaining == [], (
        "Expected zero tracked files (excluding CHANGELOG.md) to reference "
        f"the old 'plugin-orchestrator'/'plugin_orchestrator' name after the "
        f"mechanical sweep. Remaining: {remaining}"
    )
