"""hooks/feature_paths.py -- map a state-file path to (memory_dir, feature_dir)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hooks"))

import feature_paths  # noqa: E402
import plan_board  # noqa: E402

FEATURE = "/m/proj/spec/2026-01-01-f"


def test_each_state_file_maps_to_memory_and_feature_dir():
    for rel in ("workflow-state.md", "requirements/requirements.md", "design/design.md",
                "tasks/tasks.md", "recap/recap.md"):
        assert feature_paths.feature_dir_from_path(f"{FEATURE}/{rel}") == ("/m/proj", FEATURE), rel


def test_other_paths_and_non_spec_layouts_are_none():
    for p in (f"{FEATURE}/notes.md", f"{FEATURE}/requirements/requirements.md.bak",
              f"{FEATURE}/research/cache.md", "/x/feature/workflow-state.md", ""):
        assert feature_paths.feature_dir_from_path(p) is None, p


def test_is_state_path_is_a_pure_suffix_check():
    assert feature_paths.is_state_path("/anywhere/tasks/tasks.md")
    assert feature_paths.is_state_path("C:\\a\\recap\\recap.md")
    assert not feature_paths.is_state_path("/anywhere/app.py")


def test_memory_dir_for_state_unchanged():
    assert plan_board.memory_dir_for_state(f"{FEATURE}/workflow-state.md") == "/m/proj"
