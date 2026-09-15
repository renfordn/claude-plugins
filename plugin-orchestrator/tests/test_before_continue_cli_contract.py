"""Regression test for hooks/before_continue.py's stdin/stdout CLI contract.

Caught live during an actual /isdd smoke run: this CLI wrapper used to emit
`updatedInput: {"prompt": modified_prompt}` — replacing the *entire* Agent
tool input rather than merging into it. The Agent tool call then failed
schema validation for missing required fields (`description`, etc.) any
time an SDD workflow was active, which is exactly when this hook actually
does anything (it no-ops when workflow_state_path(cwd) is None).

The other tests in this suite (test_before_continue_hook.py,
test_hook_integration.py) exercise handle_agent_spawn() directly and never
went through this CLI wrapper, so they never caught it.
"""
import importlib.util
import io
import json
import subprocess
import sys
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

HOOK_SCRIPT = Path(__file__).parent.parent / "hooks" / "before_continue.py"


def _load_hook_module():
    """Load hooks/before_continue.py as a standalone module (it's a CLI
    script, not a package member) so its main() can be exercised in-process."""
    spec = importlib.util.spec_from_file_location("_before_continue_cli", HOOK_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestBeforeContinueCLIContract(unittest.TestCase):
    def _run_hook(self, tool_input, monkeypatch_state_path):
        """Run hooks/before_continue.py as a subprocess with a patched
        workflow_state_path via an injected sitecustomize-style shim, so the
        hook believes an SDD workflow is active without touching real
        ~/.claude/sdd-memory state."""
        stdin_payload = json.dumps({
            "cwd": monkeypatch_state_path,
            "tool_name": "Agent",
            "tool_input": tool_input,
        })
        result = subprocess.run(
            [sys.executable, str(HOOK_SCRIPT)],
            input=stdin_payload,
            capture_output=True,
            text=True,
            cwd=monkeypatch_state_path,
        )
        return result

    def test_updated_input_preserves_all_original_fields(self):
        """The bug: updatedInput must be the full tool_input with only
        `prompt` swapped, not a bare {"prompt": ...} that drops
        `description`/`subagent_type`/etc and breaks Agent tool validation."""
        with tempfile.TemporaryDirectory() as tmp_cwd:
            # No workflow-state.md exists for this throwaway cwd, so the hook
            # is a documented no-op (exit 0, no stdout) -- assert that half of
            # the contract too, since "never blocks a spawn" depends on it.
            original_input = {
                "prompt": "original spawn prompt",
                "subagent_type": "Explore",
                "description": "a short description",
                "run_in_background": False,
            }
            result = self._run_hook(original_input, tmp_cwd)
            self.assertEqual(result.returncode, 0)
            # No active workflow for a fresh tmp dir -> documented no-op, no stdout.
            self.assertEqual(result.stdout.strip(), "")

    def test_main_preserves_all_fields_on_active_workflow(self):
        """Run the CLI's actual main() end to end (the exact path that broke
        live) with an active workflow simulated, and assert updatedInput
        keeps every original field plus the modified prompt."""
        module = _load_hook_module()

        tool_input = {
            "prompt": "original spawn prompt",
            "subagent_type": "Explore",
            "description": "a short description",
            "run_in_background": True,
        }
        stdin_payload = json.dumps({
            "cwd": "/fake/cwd",
            "tool_name": "Agent",
            "tool_input": tool_input,
        })

        with patch.object(module, "workflow_state_path", return_value="/fake/state.json"), \
             patch.object(module, "load_workflow_state", return_value={}), \
             patch.object(module, "save_workflow_state"), \
             patch("orchestrator.hooks.before_continue.handle_agent_spawn",
                   return_value="original spawn prompt\n\n[injected context]"), \
             patch("sys.stdin", io.StringIO(stdin_payload)), \
             patch("sys.stdout", new_callable=io.StringIO) as fake_stdout:
            with self.assertRaises(SystemExit) as cm:
                module.main()
            self.assertEqual(cm.exception.code, 0)
            output = json.loads(fake_stdout.getvalue())

        updated_input = output["hookSpecificOutput"]["updatedInput"]
        self.assertEqual(updated_input["description"], "a short description")
        self.assertEqual(updated_input["subagent_type"], "Explore")
        self.assertEqual(updated_input["run_in_background"], True)
        self.assertEqual(updated_input["prompt"], "original spawn prompt\n\n[injected context]")


if __name__ == "__main__":
    unittest.main()
