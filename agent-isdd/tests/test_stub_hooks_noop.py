import os
import subprocess
import sys
import unittest

HOOKS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hooks")
STUBS = ["state_guard", "complete_guard", "approval", "baseline", "resume_context",
         "user_led_guard", "review_tracking", "pre_write_dispatch"]


class StubHooksNoopTests(unittest.TestCase):
    def test_each_stub_exits_zero_silently_on_empty_payload(self):
        for name in STUBS:
            with self.subTest(hook=name):
                r = subprocess.run([sys.executable, os.path.join(HOOKS, name + ".py")],
                                   input="{}", capture_output=True, text=True, timeout=20)
                self.assertEqual(r.returncode, 0)
                self.assertEqual(r.stdout, "")
                self.assertEqual(r.stderr, "")


class StubSignatureTests(unittest.TestCase):
    def setUp(self):
        sys.path.insert(0, HOOKS)

    def test_consumer_signatures(self):
        import approval, baseline, review_tracking
        self.assertEqual(approval.approval_hash("d", "t"), "")
        self.assertEqual(approval.verify({}, "d", "t"), "legacy")
        self.assertEqual(review_tracking.high_risk_slices("x"), [])
        self.assertEqual(review_tracking.unreviewed_high_risk("/nonexistent"), [])
        self.assertIsNone(review_tracking.record_review("/nonexistent/w.json", "1"))
        self.assertEqual(baseline.diff("/tmp", "/nonexistent/w.json"),
                         {"branch_changed": [], "head_moved": [], "files_changed": []})


class DispatchTests(unittest.TestCase):
    def test_no_active_workflow_is_silent_and_skips_guards(self):
        import tempfile
        with tempfile.TemporaryDirectory() as home:
            env = dict(os.environ, CLAUDE_PLUGIN_DATA=home, HOME=home)
            r = subprocess.run([sys.executable, os.path.join(HOOKS, "pre_write_dispatch.py")],
                               input='{"tool_name":"Write","tool_input":{},"cwd":"%s"}' % home,
                               capture_output=True, text=True, timeout=20, env=env)
            self.assertEqual((r.returncode, r.stdout), (0, ""))

    def test_first_deny_wins_and_guards_get_resolved_state(self):
        sys.path.insert(0, HOOKS)
        import pre_write_dispatch as d
        calls = []
        def mk(name, result):
            def f(payload, state_path=None):
                calls.append((name, state_path))
                return result
            return f
        out = d.run({"cwd": "x"}, state_path="/s/workflow-state.md",
                    guards=[mk("a", None), mk("b", "nope"), mk("c", "later")])
        self.assertEqual(out, "nope")
        self.assertEqual(calls, [("a", "/s/workflow-state.md"), ("b", "/s/workflow-state.md")])


if __name__ == "__main__":
    unittest.main()
