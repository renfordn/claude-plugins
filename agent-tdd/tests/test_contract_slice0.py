import json
import os
import subprocess
import sys
import tempfile
import unittest

HOOKS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hooks")
sys.path.insert(0, HOOKS)
import markers  # noqa: E402
import tdd_state  # noqa: E402


class MarkerTests(unittest.TestCase):
    def test_round_trip(self):
        self.assertEqual(markers.parse_review_scope(markers.scope_marker(3)), "3")
        self.assertEqual(markers.scope_marker(3), "<!--REVIEW-SCOPE: slice=3-->")
        self.assertEqual(markers.parse_slice_id("## Plan\nSlice 12: x"), "12")
        self.assertEqual(markers.parse_slice_id("<!--SLICE-ID: 7-->"), "7")
        self.assertIsNone(markers.parse_slice_id("nothing"))

    def test_title_re(self):
        self.assertTrue(markers.SLICE_TITLE_RE.match("Slice 2: adds totals"))
        self.assertIsNone(markers.SLICE_TITLE_RE.match("adds totals"))


class MarkerRefinementTests(unittest.TestCase):
    def test_marker_beats_prose(self):
        self.assertEqual(markers.parse_slice_id("Depends on Slice 1.\n<!--SLICE-ID: 2-->"), "2")
        self.assertEqual(markers.parse_slice_id("Depends on Slice 1."), "1")

    def test_alphanumeric_ids_agree(self):
        for title, sid in (("### Slice 0a: x", "0a"), ("Slice 12ab: x", "12ab"),
                           ("- Slice 3: x", "3"), ("* Slice 4: x", "4")):
            m = markers.SLICE_TITLE_RE.match(title)
            self.assertIsNotNone(m, title)
            self.assertEqual(m.group(1), sid)
            self.assertEqual(markers.parse_slice_id(title), sid)
        self.assertEqual(markers.parse_review_scope(markers.scope_marker("12ab")), "12ab")

    def test_scope_whitespace_tolerant(self):
        self.assertEqual(markers.parse_review_scope("<!-- REVIEW-SCOPE: slice=0a -->"), "0a")
        self.assertEqual(markers.scope_marker("0a"), "<!--REVIEW-SCOPE: slice=0a-->")


WORKER = """
import sys
sys.path.insert(0, sys.argv[1])
import tdd_state
n = sys.argv[3]
tdd_state.update_json(sys.argv[2], lambda d: dict(d, items=d.get("items", []) + [n]))
"""


class UpdateJsonTests(unittest.TestCase):
    def test_concurrent_appends(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "s.json")
            procs = [subprocess.Popen([sys.executable, "-c", WORKER, HOOKS, p, str(i)])
                     for i in range(8)]
            for pr in procs:
                self.assertEqual(pr.wait(), 0)
            with open(p) as fh:
                self.assertEqual(sorted(json.load(fh)["items"]), [str(i) for i in range(8)])

    def test_corrupt_is_empty(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "s.json")
            with open(p, "w") as fh:
                fh.write("{not json")
            seen = []
            out = tdd_state.update_json(p, lambda x: (seen.append(x), {"ok": 1})[1])
            self.assertEqual(seen, [{}])
            self.assertEqual(out, {"ok": 1})


class UpdateJsonRefinementTests(unittest.TestCase):
    def test_non_dict_is_empty(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "s.json")
            with open(p, "w") as fh:
                fh.write("[1, 2]")
            seen = []
            tdd_state.update_json(p, lambda x: (seen.append(x), {"a": 1})[1])
            self.assertEqual(seen, [{}])

    def test_file_mode_preserved(self):
        with tempfile.TemporaryDirectory() as d:
            new = os.path.join(d, "new.json")
            tdd_state.update_json(new, lambda x: {"a": 1})
            self.assertEqual(os.stat(new).st_mode & 0o777, 0o644)
            old = os.path.join(d, "old.json")
            with open(old, "w") as fh:
                fh.write("{}")
            os.chmod(old, 0o640)
            tdd_state.update_json(old, lambda x: {"a": 1})
            self.assertEqual(os.stat(old).st_mode & 0o777, 0o640)


def _git(cwd, *a):
    subprocess.run(["git", *a], cwd=cwd, check=True, capture_output=True)


class StateCwdTests(unittest.TestCase):
    def test_linked_worktree_returns_main(self):
        with tempfile.TemporaryDirectory() as d:
            main = os.path.realpath(os.path.join(d, "main"))
            os.makedirs(main)
            _git(main, "init", "-q")
            _git(main, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q",
                 "--allow-empty", "-m", "i")
            wt = os.path.join(d, "wt")
            _git(main, "worktree", "add", "-q", wt)
            self.assertEqual(os.path.realpath(tdd_state.state_cwd(wt)), main)

    def test_non_git_returns_input(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(tdd_state.state_cwd(d), d)


if __name__ == "__main__":
    unittest.main()
