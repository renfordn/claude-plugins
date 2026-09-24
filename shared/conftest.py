"""Give every test a real CLAUDE_PLUGIN_DATA -- plugin code no longer guesses one.

Set at import (before test modules load) because some hook modules resolve their data dir
at import time. Points at a throwaway temp dir shaped like the real
~/.claude/plugins/data/<plugin>/, never the user's real plugin data.
"""
import os
import tempfile

if not os.environ.get("CLAUDE_PLUGIN_DATA"):
    _plugin = os.path.basename(os.path.dirname(os.path.abspath(__file__)))
    _data = os.path.join(tempfile.mkdtemp(prefix="plugins-data-test-"), _plugin)
    os.makedirs(_data)
    os.environ["CLAUDE_PLUGIN_DATA"] = _data

# A developer's real shared_memory_root option must never leak into tests; tests that exercise
# it set CLAUDE_PLUGIN_OPTION_SHARED_MEMORY_ROOT themselves (in a subprocess or reloaded module).
os.environ.pop("CLAUDE_PLUGIN_OPTION_SHARED_MEMORY_ROOT", None)
