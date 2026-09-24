"""hook_state.BASE must follow agent-isdd's resolved sdd-memory (its shared memory root when set).

agent-isdd records its resolved location in ${CLAUDE_PLUGIN_DATA}/sdd-memory-location.json;
plugin-harness finds that file via get_sibling_plugin_data_dir(). Runs in a subprocess because
BASE is resolved at import time.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

HOOKS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hooks")


def resolved_base(harness_data):
    env = dict(os.environ, CLAUDE_PLUGIN_DATA=harness_data)
    env.pop("CLAUDE_PLUGIN_OPTION_SHARED_MEMORY_ROOT", None)
    proc = subprocess.run(
        [sys.executable, "-c", "import hook_state; print(hook_state.BASE)"],
        cwd=HOOKS, capture_output=True, text=True, env=env,
    )
    assert proc.returncode == 0, proc.stderr
    return proc.stdout.strip()


class HookStateSharedRootTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        data = os.path.join(self._tmp.name, "data")
        self.harness = os.path.join(data, "plugin-harness-mkt")
        self.isdd = os.path.join(data, "agent-isdd-mkt")
        os.makedirs(self.isdd)

    def tearDown(self):
        self._tmp.cleanup()

    def write_pointer(self, record):
        with open(os.path.join(self.isdd, "sdd-memory-location.json"), "w") as fh:
            json.dump(record, fh)

    def test_follows_isdd_pointer_to_shared_root(self):
        shared_sdd = os.path.join(self._tmp.name, "shared", "sdd-memory")
        self.write_pointer({"sdd_memory": shared_sdd, "shared_memory_root": os.path.dirname(shared_sdd)})
        self.assertEqual(resolved_base(self.harness), shared_sdd)
        # No symlink/registry coordination against the stale local dir when the pointer is used.
        self.assertFalse(os.path.lexists(os.path.join(self.harness, "sdd-memory")))

    def test_falls_back_without_pointer(self):
        self.assertEqual(resolved_base(self.harness), os.path.join(self.harness, "sdd-memory"))

    def test_ignores_malformed_or_relative_pointer(self):
        for record in ({"sdd_memory": "relative/sdd-memory"}, {"other": 1}, ["not", "a", "dict"]):
            with self.subTest(record=record):
                self.write_pointer(record)
                self.assertEqual(resolved_base(self.harness), os.path.join(self.harness, "sdd-memory"))


if __name__ == "__main__":
    unittest.main()
