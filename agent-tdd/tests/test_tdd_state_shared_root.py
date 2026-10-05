"""agent-tdd state follows the shared memory root, like agent-nelly and agent-isdd."""
import os
import subprocess
import sys
import tempfile
import unittest

HOOKS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hooks")


class TddStateSharedRootTests(unittest.TestCase):
    def _base(self, env):
        full = {k: v for k, v in os.environ.items() if k != "CLAUDE_PLUGIN_OPTION_SHARED_MEMORY_ROOT"}
        full.update(env)
        out = subprocess.run([sys.executable, "-c", "import tdd_state; print(tdd_state.BASE)"],
                             cwd=HOOKS, env=full, capture_output=True, text=True, check=True)
        return out.stdout.strip()

    def test_state_lives_under_shared_root_when_set(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(self._base({"CLAUDE_PLUGIN_OPTION_SHARED_MEMORY_ROOT": tmp}),
                             os.path.join(tmp, "agent-tdd-state"))

    def test_state_stays_in_plugin_data_without_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(self._base({"CLAUDE_PLUGIN_DATA": tmp}),
                             os.path.join(tmp, "agent-tdd-state"))


if __name__ == "__main__":
    unittest.main()
