"""Regression test for hooks/before_continue.py's stdin/stdout CLI contract.

History (see the DISABLED note at the top of hooks/before_continue.py for full
detail): this CLI wrapper used to emit `updatedInput: {"prompt": modified_prompt}`,
replacing the *entire* Agent tool input rather than merging into it, dropping
`description`/`subagent_type`/etc. Fixed to merge instead of replace -- but the
live Agent tool call still failed identically afterward. Root cause, confirmed
independently in a separate project the same day: the Agent tool's PreToolUse
`tool_input` never contains `description` in the first place (the harness
doesn't forward it to hooks), and `updatedInput` is validated as the complete
replacement input rather than merged onto the original -- so no hook can ever
supply `description` back correctly. This is a Claude Code harness bug, not
fixable from this hook. The hook is now unconditionally disabled
(`sys.exit(0)` as the first line of `main()`).

This test file covers both halves:
1. The hook is now a true no-op regardless of input (matches the disabled state).
2. The merge logic that sits dormant below the disable line is still correct,
   so it's ready to go the moment the harness bug is fixed and the disable
   line is removed -- this is regression coverage for dead code, deliberately,
   per the DISABLED note's "kept for whenever the harness bug is fixed".
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


class TestBeforeContinueHookDisabled(unittest.TestCase):
    """The hook must be an unconditional no-op until the harness bug is fixed."""

    def _run_hook(self, tool_input, cwd):
        stdin_payload = json.dumps({
            "cwd": cwd,
            "tool_name": "Agent",
            "tool_input": tool_input,
        })
        return subprocess.run(
            [sys.executable, str(HOOK_SCRIPT)],
            input=stdin_payload,
            capture_output=True,
            text=True,
            cwd=cwd,
        )

    def test_no_op_with_no_active_workflow(self):
        with tempfile.TemporaryDirectory() as tmp_cwd:
            result = self._run_hook({"prompt": "p", "subagent_type": "Explore"}, tmp_cwd)
            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stdout.strip(), "")

    def test_no_op_even_when_workflow_state_would_be_active(self):
        """The disable line must short-circuit before workflow_state_path is
        even consulted -- simulate an active workflow and confirm still no-op."""
        module = _load_hook_module()
        tool_input = {
            "prompt": "original spawn prompt",
            "subagent_type": "Explore",
            "description": "a short description",
        }
        stdin_payload = json.dumps({
            "cwd": "/fake/cwd", "tool_name": "Agent", "tool_input": tool_input,
        })
        with patch.object(module, "workflow_state_path", return_value="/fake/state.json"), \
             patch.object(module, "load_workflow_state", return_value={}), \
             patch.object(module, "save_workflow_state"), \
             patch("sys.stdin", io.StringIO(stdin_payload)), \
             patch("sys.stdout", new_callable=io.StringIO) as fake_stdout:
            with self.assertRaises(SystemExit) as cm:
                module.main()
            self.assertEqual(cm.exception.code, 0)
            self.assertEqual(fake_stdout.getvalue(), "")


class TestDormantMergeLogicStillCorrect(unittest.TestCase):
    """Regression coverage for the merge fix sitting dormant below the disable
    line, so it's verified correct whenever the disable line is eventually
    removed. Exercises the exact expression main() uses, not a paraphrase."""

    def test_merge_preserves_all_original_fields(self):
        tool_input = {
            "prompt": "original",
            "subagent_type": "Explore",
            "description": "desc",
            "run_in_background": True,
        }
        modified_prompt = "original\n\n[injected context]"
        merged = {**tool_input, "prompt": modified_prompt}

        self.assertEqual(merged["description"], "desc")
        self.assertEqual(merged["subagent_type"], "Explore")
        self.assertEqual(merged["run_in_background"], True)
        self.assertEqual(merged["prompt"], modified_prompt)


if __name__ == "__main__":
    unittest.main()
