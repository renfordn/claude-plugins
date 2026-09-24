"""Tests for agent-isdd's shared memory root (userConfig `shared_memory_root`).

Every case runs the real hook/CLI in a subprocess with its own CLAUDE_PLUGIN_DATA and
CLAUDE_PLUGIN_OPTION_SHARED_MEMORY_ROOT, because sdd_memory resolves BASE at import time.
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest

HOOKS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hooks")
ENV_KEY = "CLAUDE_PLUGIN_OPTION_SHARED_MEMORY_ROOT"


def slug(cwd):
    return re.sub(r"[^A-Za-z0-9]+", "-", os.path.abspath(cwd)).strip("-").lower() or "root"


class SharedMemoryRootTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        tmp = self._tmp.name
        self.data = os.path.join(tmp, "data", "agent-isdd-inline")
        self.shared = os.path.join(tmp, "shared")
        self.cwd = os.path.join(tmp, "project")

    def tearDown(self):
        self._tmp.cleanup()

    def run_script(self, script, args=(), payload=None, shared=True):
        env = dict(os.environ, CLAUDE_PLUGIN_DATA=self.data)
        if shared:
            env[ENV_KEY] = self.shared
        else:
            env.pop(ENV_KEY, None)
        return subprocess.run(
            [sys.executable, os.path.join(HOOKS, script), *args],
            input=json.dumps(payload) if payload is not None else "",
            capture_output=True, text=True, env=env,
        )

    def decision(self, proc):
        self.assertEqual(proc.returncode, 0, proc.stderr)
        if not proc.stdout.strip():
            return None
        return json.loads(proc.stdout)["hookSpecificOutput"]["permissionDecision"]

    def shared_mem(self):
        return os.path.join(self.shared, "sdd-memory", slug(self.cwd))

    def local_mem(self):
        return os.path.join(self.data, "sdd-memory", slug(self.cwd))

    def test_spec_path_uses_shared_root_when_set(self):
        proc = self.run_script("sdd_memory.py", ["--spec-path", "2026-09-24-x", self.cwd])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.strip(), os.path.join(self.shared_mem(), "spec", "2026-09-24-x"))

    def test_spec_path_falls_back_to_plugin_data_when_unset(self):
        proc = self.run_script("sdd_memory.py", ["--spec-path", "2026-09-24-x", self.cwd], shared=False)
        self.assertEqual(proc.stdout.strip(), os.path.join(self.local_mem(), "spec", "2026-09-24-x"))

    def test_memory_permission_allows_spec_under_shared_root(self):
        target = os.path.join(self.shared_mem(), "spec", "f", "workflow-state.md")
        proc = self.run_script("memory_permission.py",
                               payload={"tool_input": {"file_path": target}, "cwd": self.cwd})
        self.assertEqual(self.decision(proc), "allow")

    def test_memory_permission_ignores_stale_local_spec(self):
        target = os.path.join(self.local_mem(), "spec", "f", "workflow-state.md")
        proc = self.run_script("memory_permission.py",
                               payload={"tool_input": {"file_path": target}, "cwd": self.cwd})
        self.assertIsNone(self.decision(proc))

    def test_slug_guard_denies_wrong_slug_under_shared_root(self):
        target = os.path.join(self.shared, "sdd-memory", "wrong-slug", "spec", "f", "x.md")
        proc = self.run_script("memory_slug_guard.py",
                               payload={"tool_input": {"file_path": target}, "cwd": self.cwd})
        self.assertEqual(self.decision(proc), "deny")

    def test_slug_guard_passes_correct_slug_under_shared_root(self):
        target = os.path.join(self.shared_mem(), "spec", "f", "x.md")
        proc = self.run_script("memory_slug_guard.py",
                               payload={"tool_input": {"file_path": target}, "cwd": self.cwd})
        self.assertIsNone(self.decision(proc))

    def test_slug_guard_denies_local_store_while_shared_root_active(self):
        target = os.path.join(self.local_mem(), "spec", "f", "x.md")
        proc = self.run_script("memory_slug_guard.py",
                               payload={"tool_input": {"file_path": target}, "cwd": self.cwd})
        self.assertEqual(self.decision(proc), "deny")
        self.assertIn("merge_plugin_data.py", proc.stdout)

    def test_slug_guard_leaves_local_store_alone_without_shared_root(self):
        target = os.path.join(self.local_mem(), "spec", "f", "x.md")
        proc = self.run_script("memory_slug_guard.py",
                               payload={"tool_input": {"file_path": target}, "cwd": self.cwd},
                               shared=False)
        self.assertIsNone(self.decision(proc))

    def test_session_start_scaffolds_root_and_writes_pointer(self):
        proc = self.run_script("session_start.py", payload={"cwd": self.cwd})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        ctx = json.loads(proc.stdout)["hookSpecificOutput"]["additionalContext"]
        self.assertIn(self.shared_mem(), ctx)
        self.assertTrue(os.path.isfile(os.path.join(self.shared, ".gitattributes")))
        with open(os.path.join(self.data, "sdd-memory-location.json")) as fh:
            pointer = json.load(fh)
        self.assertEqual(pointer["sdd_memory"], os.path.join(self.shared, "sdd-memory"))
        self.assertEqual(pointer["shared_memory_root"], self.shared)

    def test_session_start_pointer_tracks_unset_root(self):
        self.run_script("session_start.py", payload={"cwd": self.cwd})
        self.run_script("session_start.py", payload={"cwd": self.cwd}, shared=False)
        with open(os.path.join(self.data, "sdd-memory-location.json")) as fh:
            pointer = json.load(fh)
        self.assertEqual(pointer["sdd_memory"], os.path.join(self.data, "sdd-memory"))
        self.assertIsNone(pointer["shared_memory_root"])

    def test_session_markers_stay_machine_local(self):
        feature = os.path.join(self.shared_mem(), "spec", "2026-09-24-x")
        os.makedirs(feature)
        with open(os.path.join(feature, "workflow-state.md"), "w") as fh:
            fh.write("# Workflow State\n\n- Current phase: Design\n- Workflow status: in progress\n")
        proc = self.run_script("stop_check.py", payload={"cwd": self.cwd})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(os.path.isfile(os.path.join(self.local_mem(), "last-stop.json")))
        self.assertFalse(os.path.exists(os.path.join(self.shared_mem(), "last-stop.json")))


if __name__ == "__main__":
    unittest.main()
