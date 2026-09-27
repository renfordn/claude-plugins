"""Shared test helper for focus-ux hooks/*.py's black-box test suite.

Every hook runs as a real subprocess in production (invoked via hooks.json), so tests spawn the
same subprocess rather than importing and monkeypatching each module -- this exercises the exact
code path production uses. Trimmed copy of agent-isdd/tests/hook_test_utils.py's run_hook(),
adapted for focus-ux's stdin-JSON hooks (there is no permission-decision hook family here).
"""
import json
import os
import subprocess
from pathlib import Path

HOOKS_DIR = str(Path(__file__).resolve().parent.parent / "hooks")


def run_hook(name, payload, env_extra=None, timeout=10):
    """Run hooks/<name> as a subprocess, feeding payload (a dict) as JSON on stdin.

    Returns (parsed_stdout_json_or_None, returncode).
    """
    script = os.path.join(HOOKS_DIR, name)
    env = dict(os.environ)
    if env_extra:
        env.update(env_extra)

    result = subprocess.run(
        ["python3", script],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
        timeout=timeout,
    )

    stdout = result.stdout.strip()
    if not stdout:
        return None, result.returncode
    try:
        data = json.loads(stdout)
    except (json.JSONDecodeError, ValueError):
        return None, result.returncode
    return data, result.returncode
