"""Skill/command content that runs sdd_memory.py by hand must pass the plugin env through.

sdd_memory.py raises PluginDataDirUnavailable at import when CLAUDE_PLUGIN_DATA is unset, and
only hook subprocesses get it automatically, so every hand-run call needs the prefix.
"""

import re
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
CALL = re.compile(r'python3 "\$\{CLAUDE_PLUGIN_ROOT\}/hooks/sdd_memory\.py"')
PREFIX = (
    'CLAUDE_PLUGIN_DATA="${CLAUDE_PLUGIN_DATA}" '
    'CLAUDE_PLUGIN_OPTION_SHARED_MEMORY_ROOT="${user_config.shared_memory_root}" '
)


def _hand_run_calls():
    for md in sorted(PLUGIN_ROOT.glob("**/*.md")):
        if "tests" in md.parts:
            continue
        for lineno, line in enumerate(md.read_text().splitlines(), 1):
            for match in CALL.finditer(line):
                yield md.relative_to(PLUGIN_ROOT), lineno, line, match.start()


def test_every_hand_run_sdd_memory_call_passes_plugin_env():
    missing = [
        f"{path}:{lineno}: {line.strip()}"
        for path, lineno, line, start in _hand_run_calls()
        if not line[:start].endswith(PREFIX)
    ]
    assert not missing, "sdd_memory.py run without the env prefix:\n" + "\n".join(missing)
