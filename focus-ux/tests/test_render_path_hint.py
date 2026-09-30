"""hooks/render_path_hint.py -- SessionStart hook that tells the model where
scripts/render_inline.py lives.

The Focus output style used to say `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/render_inline.py"`.
That variable was reported to reach the model unexpanded (not reproduced in this repo) (output-style text is not
substituted) and it is unset in the Bash tool's shell, so the model could not resolve the path.
The hook computes the absolute path from its own location instead.
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from focus_ux_hook_test_utils import run_hook  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
HOOK = ROOT / "hooks" / "render_path_hint.py"
PAYLOAD = {"session_id": "s", "hook_event_name": "SessionStart", "source": "startup"}


def test_prints_session_start_context_naming_the_real_script():
    out, rc = run_hook("render_path_hint.py", PAYLOAD)
    assert rc == 0
    spec = out["hookSpecificOutput"]
    assert spec["hookEventName"] == "SessionStart"
    ctx = spec["additionalContext"]
    script = ROOT / "scripts" / "render_inline.py"
    assert script.is_file()
    assert str(script) in ctx
    assert ctx.startswith("focus-ux render script:")
    assert len(ctx) < 400  # rides in every session's context; keep it to one line


def test_path_comes_from_the_hook_location_not_the_environment():
    out, rc = run_hook(
        "render_path_hint.py", PAYLOAD,
        env_extra={"CLAUDE_PLUGIN_ROOT": "/nonexistent/elsewhere", "CLAUDE_PLUGIN_DATA": ""},
    )
    assert rc == 0
    assert str(ROOT / "scripts" / "render_inline.py") in out["hookSpecificOutput"]["additionalContext"]
    assert "/nonexistent/elsewhere" not in out["hookSpecificOutput"]["additionalContext"]


def test_path_with_spaces_is_quoted(tmp_path):
    plugin = tmp_path / "dir with spaces" / "focus-ux"
    (plugin / "hooks").mkdir(parents=True)
    (plugin / "scripts").mkdir()
    shutil.copy(HOOK, plugin / "hooks" / "render_path_hint.py")
    (plugin / "scripts" / "render_inline.py").write_text("")
    result = subprocess.run(
        [sys.executable, str(plugin / "hooks" / "render_path_hint.py")],
        input=json.dumps(PAYLOAD), capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0, result.stderr
    ctx = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
    assert f'python3 "{plugin / "scripts" / "render_inline.py"}"' in ctx


def test_fails_open_when_the_script_is_missing(tmp_path):
    plugin = tmp_path / "focus-ux"
    (plugin / "hooks").mkdir(parents=True)
    shutil.copy(HOOK, plugin / "hooks" / "render_path_hint.py")  # no scripts/ next to it
    result = subprocess.run(
        [sys.executable, str(plugin / "hooks" / "render_path_hint.py")],
        input=json.dumps(PAYLOAD), capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0
    assert result.stdout.strip() == ""


def test_ignores_garbage_stdin():
    result = subprocess.run(
        [sys.executable, str(HOOK)], input="not json {{", capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0
    assert json.loads(result.stdout)["hookSpecificOutput"]["hookEventName"] == "SessionStart"
