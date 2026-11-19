"""Slice 1A: evidence shared across linked worktrees, --slice-id/--base, integration phase."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "tdd_check.py"
sys.path.insert(0, str(ROOT / "scripts"))
import tdd_check  # noqa: E402

PASS = [sys.executable, "-c", "import sys; sys.exit(0)"]
FAIL = [sys.executable, "-c", "import sys; sys.exit(1)"]


def _git(cwd, *args):
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", *args], cwd=cwd, check=True,
                   capture_output=True)


def _run(cwd, args, cmd=()):
    argv = [sys.executable, str(SCRIPT), *args] + (["--", *cmd] if cmd else [])
    r = subprocess.run(argv, cwd=cwd, capture_output=True, text=True)
    lines = [l for l in r.stdout.splitlines() if l.startswith("TDD-EVIDENCE")]
    return r, (lines[-1] if lines else None)


class WorktreeEvidenceTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        base = os.path.realpath(self._tmp.name)
        self.main = os.path.join(base, "main")
        self.wt = os.path.join(base, "wt")
        self.elsewhere = os.path.join(base, "else")
        os.makedirs(self.main)
        os.makedirs(self.elsewhere)
        _git(self.main, "init", "-q")
        _git(self.main, "commit", "-q", "--allow-empty", "-m", "init")
        _git(self.main, "worktree", "add", "-q", self.wt)

    def tearDown(self):
        self._tmp.cleanup()

    def test_red_in_linked_worktree_is_verified_from_main_and_foreign_cwd(self):
        _, line = _run(self.wt, ["red", "--slice", "adds totals"], FAIL)
        token = line.split()[2]
        self.assertIsNotNone(tdd_check.verify([token], cwd=self.main)[token])
        code = ("import sys; sys.path.insert(0, %r); import tdd_check, json; "
                "print(json.dumps(tdd_check.verify([%r], cwd=%r)))" % (str(ROOT / "scripts"), token, self.main))
        r = subprocess.run([sys.executable, "-c", code], cwd=self.elsewhere, capture_output=True, text=True)
        self.assertEqual(json.loads(r.stdout)[token]["phase"], "red")

    def test_slice_id_must_match_title(self):
        r, line = _run(self.main, ["red", "--slice", "Slice 2: foo", "--slice-id", "1"], FAIL)
        self.assertNotEqual(r.returncode, 0)
        self.assertIsNone(line)
        self.assertIn("slice-id", r.stderr + r.stdout)
        r, line = _run(self.main, ["red", "--slice", "Slice 2: foo", "--slice-id", "2"], FAIL)
        self.assertEqual(r.returncode, 0)
        token = line.split()[2]
        self.assertEqual(tdd_check.verify([token], cwd=self.main)[token]["slice_id"], "2")

    def test_green_base_must_match_red_base(self):
        _run(self.main, ["red", "--slice", "t", "--base", "Y"], FAIL)
        r, line = _run(self.main, ["green", "--slice", "t", "--base", "X"], PASS)
        self.assertEqual(r.returncode, 1)
        self.assertIn("NOT CONFIRMED", line)
        r, line = _run(self.main, ["green", "--slice", "t", "--base", "Y"], PASS)
        self.assertEqual(r.returncode, 0)
        self.assertTrue(line.endswith("CONFIRMED"))

    def test_serial_mode_without_flags(self):
        _run(self.main, ["red", "--slice", "adds totals"], FAIL)
        r, line = _run(self.main, ["green", "--slice", "adds totals"], PASS)
        self.assertEqual(r.returncode, 0)
        self.assertTrue(line.endswith("CONFIRMED"))

    def test_integration_phase_records_and_prints(self):
        r, line = _run(self.wt, ["integration", "--wave", "2", "--cmd", "exit 0"])
        self.assertEqual(r.returncode, 0)
        self.assertTrue(line.startswith("TDD-EVIDENCE integration "))
        entry = tdd_check.verify([line.split()[2]], cwd=self.main)[line.split()[2]]
        self.assertEqual((entry["phase"], entry["wave"], entry["exit"]), ("integration", 2, 0))
        r, line = _run(self.main, ["integration", "--wave", "3", "--cmd", "exit 3"])
        self.assertEqual(r.returncode, 1)
        self.assertIn("exit=3", line)

    def test_green_without_base_requires_same_worktree(self):
        _run(self.wt, ["red", "--slice", "shared title"], FAIL)
        r, line = _run(self.main, ["green", "--slice", "shared title"], PASS)
        self.assertEqual(r.returncode, 1)
        self.assertIn("NOT CONFIRMED", line)
        r, line = _run(self.wt, ["green", "--slice", "shared title"], PASS)
        self.assertEqual(r.returncode, 0)

    def test_old_entries_without_worktree_still_match_on_title(self):
        path = tdd_check.evidence_path(self.main)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(json.dumps({"token": "old1", "phase": "red", "slice": "legacy", "confirmed": True}) + "\n")
        r, line = _run(self.wt, ["green", "--slice", "legacy"], PASS)
        self.assertEqual(r.returncode, 0)

    def test_slice_id_stored_normalised(self):
        r, line = _run(self.main, ["red", "--slice", "Slice 1A: x", "--slice-id", "1a"], FAIL)
        token = line.split()[2]
        self.assertEqual(tdd_check.verify([token], cwd=self.main)[token]["slice_id"], "1A")

    def test_base_mismatch_note(self):
        _run(self.main, ["red", "--slice", "t", "--base", "Y"], FAIL)
        _, line = _run(self.main, ["green", "--slice", "t", "--base", "X"], PASS)
        self.assertIn("no confirmed red with this base", line)

    def test_serial_paths_do_not_import_markers(self):
        code = ("import sys; sys.path.insert(0, %r); import tdd_check; "
                "tdd_check.verify([], cwd=%r); print('markers' in sys.modules)" % (str(ROOT / "scripts"), self.main))
        r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
        self.assertEqual(r.stdout.strip(), "False")


if __name__ == "__main__":
    unittest.main()
