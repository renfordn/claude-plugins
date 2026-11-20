"""PostToolUse(Bash): only a code-reviewer run of review_headless.sh clears gates."""
import json
import os
import subprocess
import sys
import tempfile
import unittest

HOOK = os.path.join(os.path.dirname(__file__), "..", "hooks", "review_gate.py")
AG = "agent5eeeeeeeeeee"
GREEN = ("<!--AGENT-TDD-REPORT-->\n<!--AGENT-TDD-PHASE:green_pause-->\n"
         "**Plan**\nSlice 5: do thing")
REVIEWER = "<!--CODE-REVIEWER-REPORT-->\n**Verdict**: clear"
SCRIPT = "code-reviewer/scripts/review_headless.sh"


class HeadlessAgentFlagTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.cwd = os.path.join(self._tmp.name, "project")
        os.makedirs(self.cwd)
        self.env = {k: v for k, v in os.environ.items()
                    if k != "CLAUDE_PLUGIN_OPTION_SHARED_MEMORY_ROOT"}
        self.env.update(CLAUDE_PLUGIN_DATA=os.path.join(self._tmp.name, "data"),
                        CLAUDE_CONFIG_DIR=os.path.join(self._tmp.name, "cfg"))

    def tearDown(self):
        self._tmp.cleanup()

    def _run(self, payload):
        payload["cwd"] = self.cwd
        r = subprocess.run([sys.executable, HOOK], input=json.dumps(payload),
                           capture_output=True, text=True, env=self.env)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout) if r.stdout.strip() else None

    def _gated_after(self, command, stdout):
        self._run({"hook_event_name": "SubagentStop", "agent_id": AG,
                   "agent_type": "agent-tdd:agent-TDD", "last_assistant_message": GREEN})
        self._run({"hook_event_name": "PostToolUse", "tool_name": "Bash",
                   "tool_input": {"command": command},
                   "tool_response": {"stdout": stdout, "stderr": ""}})
        out = self._run({"hook_event_name": "PreToolUse", "tool_name": "SendMessage",
                         "tool_input": {"to": AG, "message": "proceed"}})
        return (out or {}).get("hookSpecificOutput", {}).get("permissionDecision") == "deny"

    def test_clears(self):
        for cmd in (f"{SCRIPT} x", f"{SCRIPT} --agent code-reviewer x",
                    f"{SCRIPT} --agent=code-reviewer x"):
            with self.subTest(cmd=cmd):
                self.assertFalse(self._gated_after(cmd, REVIEWER))

    def test_never_clears(self):
        cases = [
            (f"{SCRIPT} --agent bug-investigator x", REVIEWER),
            (f"{SCRIPT} --agent bug-investigator x", "<!--BUG-INVESTIGATION-REPORT-->\nH1"),
            (f"{SCRIPT} --agent finding-verifier x", REVIEWER),
            (f"{SCRIPT} --agent finding-verifier x", "<!--FINDING-RECHECK-REPORT-->\nok"),
            (f"{SCRIPT} --agent=finding-verifier x", REVIEWER),
            (f"{SCRIPT} x", "no marker here"),
            (f"{SCRIPT} x", "<!--FINDING-RECHECK-REPORT-->\nok"),
        ]
        for cmd, out in cases:
            with self.subTest(cmd=cmd, out=out[:30]):
                self.assertTrue(self._gated_after(cmd, out))

    def test_marker_only_in_command_does_not_clear(self):
        cmd = f"{SCRIPT} --agent bug-investigator 'echo <!--CODE-REVIEWER-REPORT-->'"
        self.assertTrue(self._gated_after(cmd, "nothing"))


if __name__ == "__main__":
    unittest.main()
