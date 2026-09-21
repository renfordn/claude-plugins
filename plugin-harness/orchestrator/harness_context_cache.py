"""HarnessContextCache: project-slug-keyed shared context cache.

Backs the standalone Tier-1 context path (handle_standalone_spawn) and
NellyBriefManager's cache_backend param with a JSON file that's independent of
workflow-state.json's existence, so plugin-harness's MCP service/telemetry
work with no `agent-isdd` SDD workflow ever having started. See design.md's
"Shared Context Cache" and "Data Contracts And Interfaces" sections.

One file per project slug (`<base_dir>/<project_slug>/context-cache.json`),
shared across all standalone callers for that project regardless of which
plugin calls it. Writes are atomic (write-temp-then-rename, matching
hook_state.py's save_workflow_state/FileStateStore pattern). Reads never
raise: a missing or malformed file behaves like an empty cache.
"""
import json
import os
import tempfile
import time

_this_dir = os.path.dirname(os.path.abspath(__file__))
_hooks_dir = os.path.join(os.path.dirname(_this_dir), "hooks")
if _hooks_dir not in os.sys.path:
    os.sys.path.insert(0, _hooks_dir)
from path_resolution import get_plugin_data_dir  # noqa: E402


class HarnessContextCache:
    """Get/set a small set of cached values (nelly brief, capability map, ...)
    for one project, TTL-gated, backed by a single JSON file.

    Args:
        project_slug: Identifies the project this cache instance is scoped to
            (e.g. hook_state.py's project_slug(cwd)).
        base_dir: Override for the cache root directory. Defaults to
            get_plugin_data_dir("plugin-harness"). Tests pass a tmpdir here;
            production code should omit it.
    """

    FILENAME = "context-cache.json"

    def __init__(self, project_slug: str, base_dir: str = None):
        self.project_slug = project_slug
        self.base_dir = base_dir or get_plugin_data_dir("plugin-harness")
        self.project_dir = os.path.join(self.base_dir, project_slug)
        self.path = os.path.join(self.project_dir, self.FILENAME)

    def _read_all(self) -> dict:
        """Load the full on-disk cache dict, tolerant of a missing or
        malformed file (never raises)."""
        try:
            with open(self.path, "r") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def get(self, key: str):
        """Return the cached value for key, or None if absent or expired."""
        entry = self._read_all().get(key)
        if not isinstance(entry, dict):
            return None
        expires_at = entry.get("expires_at")
        if expires_at is None or time.time() >= expires_at:
            return None
        return entry.get("value")

    def set(self, key: str, value, ttl_seconds: int) -> None:
        """Persist value under key with the given TTL (atomic write)."""
        os.makedirs(self.project_dir, exist_ok=True)
        data = self._read_all()
        data[key] = {"value": value, "expires_at": time.time() + ttl_seconds}

        fd, tmp_path = tempfile.mkstemp(
            dir=self.project_dir, prefix=f".{self.FILENAME}-", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w") as tmp_file:
                json.dump(data, tmp_file, indent=2)
            os.replace(tmp_path, self.path)
        except BaseException:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            raise
