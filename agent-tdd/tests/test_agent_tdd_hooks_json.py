"""Structural tests for agent-tdd/hooks/hooks.json."""
import glob
import json
import os
import py_compile
import unittest

HOOKS_JSON = os.path.join(os.path.dirname(__file__), "..", "hooks", "hooks.json")
HOOKS_DIR = os.path.join(os.path.dirname(__file__), "..", "hooks")


class HooksJsonTests(unittest.TestCase):
    def setUp(self):
        with open(HOOKS_JSON) as f:
            self.data = json.load(f)
        self.hooks = self.data["hooks"]

    def _commands_for(self, event):
        cmds = []
        for matcher_entry in self.hooks.get(event, []):
            for hook in matcher_entry["hooks"]:
                cmds.append(hook["command"])
        return cmds

    def _all_commands(self):
        cmds = []
        for event in self.hooks:
            cmds.extend(self._commands_for(event))
        return cmds

    def test_hooks_key_exists(self):
        self.assertIn("hooks", self.data)
        self.assertIsInstance(self.hooks, dict)

    def test_session_start_registered(self):
        self.assertIn("SessionStart", self.hooks)

    def test_subagent_stop_registered(self):
        self.assertIn("SubagentStop", self.hooks)

    def test_stop_registered(self):
        self.assertIn("Stop", self.hooks)

    def test_tdd_session_start_script_in_command(self):
        cmds = self._commands_for("SessionStart")
        self.assertTrue(any("tdd_session_start.py" in c for c in cmds))

    def test_tdd_subagent_stop_script_in_command(self):
        cmds = self._commands_for("SubagentStop")
        self.assertTrue(any("tdd_subagent_stop.py" in c for c in cmds))

    def test_tdd_stop_script_in_command(self):
        cmds = self._commands_for("Stop")
        self.assertTrue(any("tdd_stop.py" in c for c in cmds))

    def test_all_referenced_scripts_exist(self):
        for command in self._all_commands():
            # command is like: python3 "${CLAUDE_PLUGIN_ROOT}/hooks/tdd_stop.py"
            script = command.split("/hooks/")[-1].rstrip('"')
            full = os.path.join(HOOKS_DIR, script)
            self.assertTrue(
                os.path.isfile(full),
                f"Script {script!r} referenced in hooks.json does not exist at {full}",
            )


class HooksCompileCleanlyTests(unittest.TestCase):
    """F-04 regression: hooks/ux_render.py shipped with a SyntaxError (an
    invalid f-string) that no test caught, because no test imported or
    otherwise compiled it -- it's reached only via a SubagentStop hook chain,
    not directly from hooks.json's own command strings. py_compile every
    hooks/*.py file directly so a syntax error anywhere in hooks/ fails CI
    regardless of whether hooks.json references it as a top-level command.
    """

    def test_every_hook_script_compiles(self):
        for path in sorted(glob.glob(os.path.join(HOOKS_DIR, "*.py"))):
            with self.subTest(path=path):
                try:
                    py_compile.compile(path, doraise=True)
                except py_compile.PyCompileError as e:
                    self.fail(f"{path} failed to compile: {e}")


if __name__ == "__main__":
    unittest.main()
