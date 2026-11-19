"""Slice 1A: start/coverage/bypass/done phases, fresh-Red rule, open_slice/unlocked helpers."""
import datetime
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "tdd_check.py"
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "hooks"))
import tdd_check  # noqa: E402
import markers  # noqa: E402

PASS = [sys.executable, "-c", "import sys; sys.exit(0)"]
FAIL = [sys.executable, "-c", "import sys; sys.exit(1)"]
PASS_SH = "exit 0"
FAIL_SH = "exit 1"


def _git(cwd, *args):
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", *args], cwd=cwd, check=True,
                   capture_output=True)


def _run(cwd, args, cmd=()):
    argv = [sys.executable, str(SCRIPT), *args] + (["--", *cmd] if cmd else [])
    r = subprocess.run(argv, cwd=cwd, capture_output=True, text=True)
    lines = [l for l in r.stdout.splitlines() if l.startswith("TDD-EVIDENCE")]
    return r, (lines[-1] if lines else None)


class CliTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = os.path.realpath(self._tmp.name)
        _git(self.repo, "init", "-q")
        _git(self.repo, "commit", "-q", "--allow-empty", "-m", "init")

    def tearDown(self):
        self._tmp.cleanup()

    def log(self):
        return tdd_check.read_log(self.repo)

    def test_all_phase_lines_match_markers_regex_and_format(self):
        lines = [
            _run(self.repo, ["start", "--slice", "T"])[1],
            _run(self.repo, ["red", "--slice", "T"], FAIL)[1],
            _run(self.repo, ["green", "--slice", "T"], PASS)[1],
            _run(self.repo, ["coverage", "--slice", "T", "--mutant", FAIL_SH], PASS)[1],
            _run(self.repo, ["bypass", "--slice", "T", "--reason", "r"])[1],
            _run(self.repo, ["integration", "--wave", "1", "--cmd", "exit 0"])[1],
            _run(self.repo, ["done"])[1],
        ]
        for line in lines:
            self.assertIsNotNone(markers.EVIDENCE_LINE_RE.fullmatch(line), line)
        by_phase = {markers.EVIDENCE_LINE_RE.match(l).group("phase"): l for l in lines}
        for p in ("start", "bypass", "done"):
            self.assertNotIn("exit=", by_phase[p])
        for p in ("red", "green", "coverage", "integration"):
            self.assertIn("exit=", by_phase[p])
        tok = by_phase["red"].split()[2]
        self.assertEqual(by_phase["red"], markers.format_evidence_line("red", tok, 1, True))
        self.assertEqual(len(self.log()), 7)

    def test_start_records_kind_gaps_ids(self):
        r, _ = _run(self.repo, ["start", "--slice", "Slice 1A: x", "--slice-id", "1A", "--base", "abc",
                                "--kind", "fix", "--risks", "2", "--inspected", "3", "--run", "1"])
        self.assertEqual(r.returncode, 0)
        e = self.log()[0]
        self.assertEqual((e["phase"], e["kind"], e["gaps"], e["confirmed"], e["slice_id"], e["base"]),
                         ("start", "fix", {"risks": 2, "inspected": 3, "run": 1}, True, "1A", "abc"))
        _run(self.repo, ["start", "--slice", "Y"])
        e = self.log()[1]
        self.assertEqual((e["kind"], e["gaps"]), ("feature", {"risks": 0, "inspected": 0, "run": 0}))

    def test_coverage_confirmed_only_when_mutant_fails(self):
        r, line = _run(self.repo, ["coverage", "--slice", "T", "--mutant", FAIL_SH], PASS)
        self.assertEqual(r.returncode, 0)
        self.assertNotIn("NOT", line)
        e = self.log()[-1]
        self.assertEqual((e["exit"], e["mutant_exit"], e["mutant"]), (0, 1, FAIL_SH))
        r, line = _run(self.repo, ["coverage", "--slice", "T", "--mutant", PASS_SH], PASS)
        self.assertEqual(r.returncode, 1)
        self.assertIn("NOT CONFIRMED", line)
        r, _ = _run(self.repo, ["coverage", "--slice", "T", "--mutant", FAIL_SH], FAIL)
        self.assertEqual(r.returncode, 1)

    def test_fresh_red_required_after_start(self):
        _run(self.repo, ["red", "--slice", "T"], FAIL)
        _run(self.repo, ["start", "--slice", "T"])
        r, line = _run(self.repo, ["green", "--slice", "T"], PASS)
        self.assertEqual(r.returncode, 1)
        self.assertIn("NOT CONFIRMED", line)
        _run(self.repo, ["red", "--slice", "T"], FAIL)
        r, line = _run(self.repo, ["green", "--slice", "T"], PASS)
        self.assertEqual(r.returncode, 0, line)

    def test_legacy_green_without_start_and_red_warns(self):
        r, _ = _run(self.repo, ["red", "--slice", "T"], FAIL)
        self.assertEqual(r.returncode, 0)
        self.assertIn("warning", r.stderr.lower())
        r, line = _run(self.repo, ["green", "--slice", "T"], PASS)
        self.assertEqual(r.returncode, 0, line)

    def test_red_inside_open_start_does_not_warn(self):
        _run(self.repo, ["start", "--slice", "T"])
        r, _ = _run(self.repo, ["red", "--slice", "T"], FAIL)
        self.assertEqual(r.stderr.strip(), "")

    def test_done_closes_slice_so_legacy_rule_applies(self):
        _run(self.repo, ["red", "--slice", "T"], FAIL)
        _run(self.repo, ["start", "--slice", "T"])
        _run(self.repo, ["done"])
        r, line = _run(self.repo, ["green", "--slice", "T"], PASS)
        self.assertEqual(r.returncode, 0, line)

    def test_done_accepts_parallel_ids(self):
        """2F review F1: parallel workers pass --slice-id/--base to every phase, including done."""
        _run(self.repo, ["start", "--slice", "Slice 3: x", "--slice-id", "3", "--base", "abc"])
        r, line = _run(self.repo, ["done", "--slice", "Slice 3: x", "--slice-id", "3", "--base", "abc"])
        self.assertEqual(r.returncode, 0, line)
        last = tdd_check.read_log(self.repo)[-1]
        self.assertEqual((last["phase"], last.get("slice_id"), last.get("base")), ("done", "3", "abc"))

    def test_worktree_ignores_inherited_git_dir(self):
        other = tempfile.TemporaryDirectory()
        old = os.environ.get("GIT_DIR")
        try:
            _git(other.name, "init", "-q")
            os.environ["GIT_DIR"] = os.path.join(other.name, ".git")
            self.assertEqual(tdd_check._worktree(self.repo), self.repo)
        finally:
            if old is None:
                os.environ.pop("GIT_DIR", None)
            else:
                os.environ["GIT_DIR"] = old
            other.cleanup()

    def append(self, phase, **kw):
        d = {"phase": phase, "at": datetime.datetime.now().isoformat(timespec="seconds"),
             "confirmed": True, "worktree": self.repo}
        d.update(kw)
        tdd_check._append(d, self.repo)

    def green(self, *args):
        r, line = _run(self.repo, ["green", "--slice", "T", *args], PASS)
        return r.returncode, line

    def test_mutant_must_actually_run_and_fail(self):
        for sh, ok in (("exit 1", True), ("exit 2", True), ("exit 3", True), ("exit 127", False),
                       ("exit 126", False), ("exit 5", False), ("exit 4", False),
                       ("echo boom-tail; kill -9 $$", False), ("exit 0", False)):
            r, line = _run(self.repo, ["coverage", "--slice", "T", "--mutant", sh], PASS)
            self.assertEqual(r.returncode, 0 if ok else 1, sh)
            self.assertEqual("NOT CONFIRMED" not in line, ok, sh)
            if sh in ("exit 127", "exit 126", "exit 5", "exit 4") or "kill" in sh:
                self.assertIn("mutant did not run", line, sh)
        self.assertEqual(self.log()[-2]["mutant_exit"], -9)
        r, _ = _run(self.repo, ["coverage", "--slice", "T", "--mutant", "echo boom-tail; kill -9 $$"], PASS)
        self.assertIn("boom-tail", r.stdout)

    def test_fresh_red_ignores_foreign_worktree_base_title_and_unconfirmed(self):
        self.append("start", slice="T")
        for bad in (dict(slice="T", worktree="/other"), dict(slice="T", base="Z"), dict(slice="U"),
                    dict(slice="T", confirmed=False)):
            self.append("red", **bad)
        code, line = self.green("--base", "B")
        self.assertEqual(code, 1, line)
        self.assertIn("NOT CONFIRMED", line)

    def test_stale_start_falls_back_to_legacy_green(self):
        self.append("red", slice="T")
        self.append("start", slice="T", at="2000-01-01T00:00:00")
        code, line = self.green()
        self.assertEqual(code, 0, line)

    def test_bypass_and_done_entries_read_back(self):
        _run(self.repo, ["bypass", "--slice", "Slice 1A: x", "--slice-id", "1A", "--base", "abc",
                         "--reason", "docs only"])
        _run(self.repo, ["done", "--slice", "Slice 1A: x"])
        b, d = self.log()
        self.assertEqual((b["phase"], b["reason"], b["slice"], b["slice_id"], b["base"], b["confirmed"]),
                         ("bypass", "docs only", "Slice 1A: x", "1A", "abc", True))
        self.assertEqual((d["phase"], d["slice"], d["confirmed"]), ("done", "Slice 1A: x", True))

    def test_read_log_keeps_only_dicts(self):
        self.append("start", slice="T")
        path = tdd_check.evidence_path(self.repo)
        with open(path, "a") as fh:
            fh.write("[1]\n42\n\"s\"\nnull\n")
        self.assertTrue(all(isinstance(x, dict) for x in self.log()))
        self.assertEqual(len(self.log()), 1)
        self.assertEqual(tdd_check.verify(["zz"], self.repo), {"zz": None})


NOW = datetime.datetime(2026, 1, 1, 12, 0, 0)


def e(phase, at="2026-01-01T11:00:00", wt="/w", **kw):
    d = {"phase": phase, "at": at, "confirmed": True}
    if wt is not None:
        d["worktree"] = wt
    d.update(kw)
    return d


class HelperTests(unittest.TestCase):
    def test_open_slice(self):
        s = e("start", slice="a")
        o = tdd_check.open_slice
        self.assertIsNone(o([], "/w", NOW))
        self.assertIs(o([s], "/w", NOW), s)
        self.assertIsNone(o([s, e("done")], "/w", NOW))
        self.assertEqual(o([s, e("start", slice="b")], "/w", NOW)["slice"], "b")
        self.assertIsNone(o([e("start", wt="/x")], "/w", NOW))
        self.assertIsNone(o([e("start", wt=None)], "/w", NOW))
        self.assertIs(o([s, e("done", wt=None)], "/w", NOW), s)
        self.assertIsNone(o([e("start", at="2026-01-01T07:59:59")], "/w", NOW))
        self.assertIsNotNone(o([e("start", at="2026-01-01T08:00:01")], "/w", NOW))

    def test_bad_at_closes_start_without_raising(self):
        for at in (None, "garbage", "", 5, "2026-01-01T11:00:00+00:00"):
            ent = e("start")
            if at is None:
                del ent["at"]
            else:
                ent["at"] = at
            self.assertIsNone(tdd_check.open_slice([ent], "/w", NOW), repr(at))
            self.assertFalse(tdd_check.unlocked([ent, e("red")], "/w", NOW), repr(at))

    def test_unlocked(self):
        s = e("start")

        def u(*rest):
            return tdd_check.unlocked([s, *rest], "/w", NOW)

        self.assertFalse(u())
        self.assertFalse(u(e("red", confirmed=False)))
        self.assertTrue(u(e("red")))
        self.assertTrue(u(e("coverage")))
        self.assertFalse(u(e("coverage", confirmed=False)))
        self.assertTrue(u(e("bypass")))
        self.assertFalse(u(e("red", wt="/x")))
        self.assertFalse(tdd_check.unlocked([e("red"), s], "/w", NOW))
        self.assertFalse(tdd_check.unlocked([e("red")], "/w", NOW))


if __name__ == "__main__":
    unittest.main()
