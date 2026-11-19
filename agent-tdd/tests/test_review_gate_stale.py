"""Unscoped reviews clear serial (slice=None) gates; stale gates are excluded, never deleted."""
import datetime
import json
import os
import subprocess
import sys
import tempfile
import unittest

HOOK = os.path.join(os.path.dirname(__file__), "..", "hooks", "review_gate.py")


def green(n=None):
    title = f"Slice {n}: do thing" if n else "did the thing"
    return ("<!--AGENT-TDD-REPORT-->\n<!--AGENT-TDD-PHASE:green_pause-->\n"
            f"**Plan**\n{title}")


def review(scope=None):
    marker = f"<!--REVIEW-SCOPE: slice={scope}-->\n" if scope else ""
    return f"<!--CODE-REVIEWER-REPORT-->\n{marker}**Verdict**: clear"


class StaleGateTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.cwd = os.path.join(self._tmp.name, "project")
        os.makedirs(self.cwd)
        self.data = os.path.join(self._tmp.name, "data")
        self.env = {k: v for k, v in os.environ.items()
                    if k != "CLAUDE_PLUGIN_OPTION_SHARED_MEMORY_ROOT"}
        self.env.update(CLAUDE_PLUGIN_DATA=self.data,
                        CLAUDE_CONFIG_DIR=os.path.join(self._tmp.name, "cfg"))

    def tearDown(self):
        self._tmp.cleanup()

    def _run(self, payload):
        payload.setdefault("cwd", self.cwd)
        r = subprocess.run([sys.executable, HOOK], input=json.dumps(payload),
                           capture_output=True, text=True, env=self.env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("[review_gate]", r.stderr)
        return json.loads(r.stdout) if r.stdout.strip() else None

    def _open(self, agent, slice_n=None):
        self._run({"hook_event_name": "SubagentStop", "agent_id": agent,
                   "agent_type": "agent-tdd:agent-TDD",
                   "last_assistant_message": green(slice_n)})

    def _review(self, scope=None):
        return self._run({"hook_event_name": "SubagentStop", "agent_id": "rev",
                          "agent_type": "code-reviewer:code-reviewer",
                          "last_assistant_message": review(scope)})

    def _send(self, to):
        out = self._run({"hook_event_name": "PreToolUse", "tool_name": "SendMessage",
                         "tool_input": {"to": to, "message": "proceed"}})
        return (out or {}).get("hookSpecificOutput", {}).get("permissionDecision", "allow")

    def _gate_file(self):
        for root, _dirs, files in os.walk(self.data):
            if "review-gate.json" in files:
                return os.path.join(root, "review-gate.json")
        raise AssertionError("no gate file")

    def _age(self, agent, hours, naive=False):
        path = self._gate_file()
        with open(path, encoding="utf-8") as fh:
            gates = json.load(fh)
        t = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=hours)
        if naive:
            t = t.astimezone().replace(tzinfo=None)
        gates[agent]["opened_at"] = t.isoformat(timespec="seconds")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(gates, fh)

    def _gates(self):
        with open(self._gate_file(), encoding="utf-8") as fh:
            return json.load(fh)

    def test_opened_at_is_written_timezone_aware(self):
        self._open("a1")
        opened = datetime.datetime.fromisoformat(self._gates()["a1"]["opened_at"])
        self.assertIsNotNone(opened.utcoffset())

    def test_unscoped_clears_all_serial_gates_and_names_them(self):
        self._open("old")
        self._open("cur")
        out = self._review()
        self.assertIn("old", out["systemMessage"])
        self.assertIn("cur", out["systemMessage"])
        self.assertEqual(self._send("old"), "allow")
        self.assertEqual(self._send("cur"), "allow")

    def test_unscoped_with_mixed_none_and_sliced_gates_clears_none_and_warns(self):
        self._open("serial")
        self._open("s4", 4)
        out = self._review()
        self.assertIn("unscoped", out["systemMessage"])
        self.assertEqual(self._send("serial"), "deny")
        self.assertEqual(self._send("s4"), "deny")

    def test_stale_gate_still_blocks_its_agent_and_is_not_deleted(self):
        self._open("stale", 3)
        self._age("stale", 30)
        self._open("fresh", 4)
        self.assertIsNone(self._review())
        self.assertEqual(self._send("fresh"), "allow")
        self.assertEqual(self._send("stale"), "deny")
        self.assertIn("stale", self._gates())

    def test_naive_legacy_timestamp_is_read_as_local_time(self):
        self._open("stale", 3)
        self._age("stale", 30, naive=True)
        self._open("fresh", 4)
        self.assertIsNone(self._review())
        self.assertEqual(self._send("stale"), "deny")
        self.assertEqual(self._send("fresh"), "allow")

    def test_scoped_review_clears_a_stale_gate_of_that_slice(self):
        self._open("stale", 3)
        self._age("stale", 30)
        self._review(3)
        self.assertEqual(self._send("stale"), "allow")

    def test_reviewed_gate_past_ttl_is_pruned_on_next_write(self):
        self._open("done", 3)
        self._review(3)
        self._age("done", 30)
        self._open("next", 4)
        self._review(4)
        self.assertNotIn("done", self._gates())


if __name__ == "__main__":
    unittest.main()
