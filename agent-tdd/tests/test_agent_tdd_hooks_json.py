"""Structural tests for agent-tdd/hooks/hooks.json."""
import json
import os
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


if __name__ == "__main__":
    unittest.main()
