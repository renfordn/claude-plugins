"""Shared path helper: which project memory dir and feature dir a state-file path belongs to."""
import os

STATE_SUFFIXES = ("workflow-state.md", "requirements/requirements.md", "design/design.md",
                  "tasks/tasks.md", "recap/recap.md", "direct-mode-state.json")


def _norm(path):
    return (path or "").replace("\\", "/")


def is_state_path(path):
    """True when `path` ends in one of the six feature state files (suffix check, no I/O)."""
    norm = _norm(path)
    return any(norm == s or norm.endswith("/" + s) for s in STATE_SUFFIXES)


def feature_dir_from_path(path):
    """(memory_dir, feature_dir) for <memory>/spec/<feature>/<state file>, else None."""
    norm = _norm(path)
    for suffix in STATE_SUFFIXES:
        if norm.endswith("/" + suffix):
            feature_dir = norm[: -len(suffix) - 1]
            spec_dir = os.path.dirname(feature_dir)
            if os.path.basename(spec_dir) == "spec":
                return os.path.dirname(spec_dir), feature_dir
            return None
    return None
