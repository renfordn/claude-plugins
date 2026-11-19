import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "parallel_plan.py"
spec = importlib.util.spec_from_file_location("parallel_plan", SCRIPT)
pp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pp)


def slice_md(n, title, kind="feature", risk="standard", deps="(none)", files="", tests="", shared=""):
    out = f"## Slice {n}: {title}\n\n**Kind:** {kind}\n**Risk Tier:** {risk}\n**Depends On:** {deps}\n**Files:** {files}\n"
    if tests:
        out += f"**Test Files:** {tests}\n"
    if shared:
        out += f"**Shared Files:** {shared}\n"
    out += "**Test Level:** unit\n\n### Test Intent\nx\n\n"
    return out


FIXTURE = "# Tasks\n\n" + "".join([
    slice_md(1, "contract", kind="contract", files="a/types.py", shared="hooks.json"),
    slice_md(2, "hook one", deps="Slice 1", files="a/h1.py", tests="t/h1.py", shared="hooks.json"),
    slice_md(3, "hook two", deps="Slice 1", files="a/h2.py", tests="t/h2.py", shared="hooks.json"),
    slice_md(4, "plain", deps="Slice 1", files="a/p.py"),
    slice_md(5, "risky", risk="high-risk", deps="Slice 1", files="a/r.py"),
    slice_md(6, "after", deps="Slice 2, Slice 4", files="a/z.py"),
])
EXPECTED = [[1], [2, 4], [3, 6], [5]]


class ParseCheckTests(unittest.TestCase):
    def test_parse(self):
        s = pp.parse(FIXTURE)
        self.assertEqual([x["number"] for x in s], [1, 2, 3, 4, 5, 6])
        self.assertEqual(s[1]["depends_on"], [1])
        self.assertEqual(s[5]["depends_on"], [2, 4])
        self.assertEqual(s[0]["depends_on"], [])
        self.assertEqual(s[1]["test_files"], ["t/h1.py"])
        self.assertEqual(s[0]["kind"], "contract")

    def test_fixture_clean(self):
        self.assertEqual(pp.check(pp.parse(FIXTURE)), [])

    def test_undeclared_overlap(self):
        md = slice_md(1, "a", files="x.py") + slice_md(2, "b", files="x.py")
        errs = pp.check(pp.parse(md))
        self.assertTrue(any("x.py" in e for e in errs))
        ok = slice_md(1, "a", files="x.py") + slice_md(2, "b", deps="Slice 1", files="x.py")
        self.assertEqual(pp.check(pp.parse(ok)), [])

    def test_cycle_and_unknown(self):
        md = slice_md(1, "a", deps="Slice 2", files="a") + slice_md(2, "b", deps="Slice 1", files="b")
        self.assertTrue(any("cycle" in e.lower() for e in pp.check(pp.parse(md))))
        md = slice_md(1, "a", deps="Slice 9", files="a")
        self.assertTrue(any("unknown" in e.lower() for e in pp.check(pp.parse(md))))

    def test_shared_without_contract(self):
        md = slice_md(1, "a", files="a", shared="h.json") + slice_md(2, "b", files="b", shared="h.json")
        self.assertTrue(any("h.json" in e for e in pp.check(pp.parse(md))))


class WavesTests(unittest.TestCase):
    def test_fixture_waves(self):
        self.assertEqual(pp.waves(pp.parse(FIXTURE)), EXPECTED)

    def test_width(self):
        md = "".join(slice_md(i, "s", files=f"f{i}") for i in range(1, 6))
        self.assertEqual(pp.waves(pp.parse(md), width=2), [[1, 2], [3, 4], [5]])
        self.assertEqual(pp.waves(pp.parse(md)), [[1, 2, 3, 4], [5]])

    def test_deterministic(self):
        s = pp.parse(FIXTURE)
        self.assertEqual(pp.waves(list(reversed(s))), EXPECTED)


class CliTests(unittest.TestCase):
    def run_cli(self, *a):
        return subprocess.run([sys.executable, str(SCRIPT), *a], capture_output=True, text=True)

    def test_write_idempotent_and_exit(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "tasks.md"
            p.write_text(FIXTURE)
            self.assertEqual(self.run_cli("check", str(p)).returncode, 0)
            r = self.run_cli("waves", str(p), "--json")
            self.assertEqual(json.loads(r.stdout), EXPECTED)
            self.run_cli("waves", str(p), "--write")
            once = p.read_text()
            self.assertIn("**Wave:** 2", once)
            self.run_cli("waves", str(p), "--write")
            self.assertEqual(p.read_text(), once)
            self.assertEqual(once.count("**Wave:**"), 6)
            self.assertEqual(pp.parse(once)[2]["wave"], 2)
            bad = Path(d) / "bad.md"
            bad.write_text(slice_md(1, "a", files="x") + slice_md(2, "b", files="x"))
            self.assertEqual(self.run_cli("check", str(bad)).returncode, 1)


def vcs(cwd, *a):
    return subprocess.run(["git", *a], cwd=cwd, check=True, capture_output=True, text=True).stdout


class VerifyBranchTests(unittest.TestCase):
    def test_flags_outside_owned(self):
        with tempfile.TemporaryDirectory() as d:
            vcs(d, "init", "-q", "-b", "main")
            vcs(d, "config", "user.email", "a@b.c")
            vcs(d, "config", "user.name", "t")
            (Path(d) / "a.txt").write_text("1")
            vcs(d, "add", ".")
            vcs(d, "commit", "-qm", "base")
            base = vcs(d, "rev-parse", "HEAD").strip()
            vcs(d, "checkout", "-qb", "feat")
            (Path(d) / "a.txt").write_text("2")
            (Path(d) / "b.txt").write_text("2")
            vcs(d, "add", ".")
            vcs(d, "commit", "-qm", "work")
            self.assertEqual(pp.verify_branch(base, "feat", ["a.txt", "b.txt"], d), [])
            self.assertEqual(pp.verify_branch(base, "feat", ["a.txt"], d), ["b.txt"])
            r = subprocess.run([sys.executable, str(SCRIPT), "verify-branch", base, "feat",
                                "--owned", "a.txt", "--repo", d], capture_output=True, text=True)
            self.assertEqual(r.returncode, 1)
            self.assertIn("b.txt", r.stdout)


class HardeningTests(unittest.TestCase):
    def test_path_normalisation(self):
        s = pp.parse(slice_md(1, "a", files="./x/y.py (new), `z.py`, a//b/../c.py"))[0]
        self.assertEqual(s["files"], ["x/y.py", "z.py", "a/c.py"])

    def test_brace_expansion(self):
        s = pp.parse(slice_md(1, "a", files="d/{a,b}.md (new), e.py"))[0]
        self.assertEqual(s["files"], ["d/a.md", "d/b.md", "e.py"])

    def test_directory_conflicts_with_children(self):
        md = slice_md(1, "a", files="src/") + slice_md(2, "b", files="src/x.py")
        self.assertTrue(any("src/" in e for e in pp.check(pp.parse(md))))
        md = slice_md(1, "a", files="./x.py") + slice_md(2, "b", files="x.py (new)")
        self.assertTrue(pp.check(pp.parse(md)))

    def test_continuation_bullets(self):
        md = ("## Slice 1: a\n\n**Kind:** feature\n**Risk Tier:** standard\n**Depends On:** (none)\n"
              "**Files:**\n- a.py\n- b.py (new)\n**Test Files:**\n- t.py\n**Test Level:** unit\n\n### Test Intent\n- not a file\n")
        s = pp.parse(md)[0]
        self.assertEqual((s["files"], s["test_files"]), (["a.py", "b.py"], ["t.py"]))

    def test_no_files_fails_closed(self):
        errs = pp.check(pp.parse(slice_md(1, "a", files="")))
        self.assertTrue(any("no Files" in e for e in errs))
        self.assertEqual(pp.check(pp.parse(slice_md(1, "a", kind="contract", files=""))), [])

    def test_duplicates_and_bad_heading(self):
        dup = slice_md(1, "a", files="a") + slice_md(1, "b", files="b")
        self.assertTrue(any("duplicate" in e for e in pp.check(pp.parse(dup))))
        bad = slice_md(1, "a", files="a") + "## Slice two: oops\n\n**Files:** z\n"
        self.assertTrue(any("unparseable" in e for e in pp.check(pp.parse(bad))))
        with self.assertRaises(ValueError):
            pp.waves(pp.parse(bad))

    def test_alphanumeric_ids(self):
        md = slice_md("1a", "a", files="a") + slice_md("1b", "b", deps="Slice 1a", files="b")
        s = pp.parse(md)
        self.assertEqual([x["number"] for x in s], ["1a", "1b"])
        self.assertEqual(s[1]["depends_on"], ["1a"])
        self.assertEqual(pp.waves(s), [["1a"], ["1b"]])

    def test_width_rejected(self):
        s = pp.parse(slice_md(1, "a", files="a"))
        for w in (0, -1):
            with self.assertRaises(ValueError):
                pp.waves(s, width=w)
        r = subprocess.run([sys.executable, str(SCRIPT), "waves", "x", "--width", "0"],
                           capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0)

    def test_deps_range_and_self(self):
        md = (slice_md(1, "a", files="a") + slice_md(2, "b", files="b")
              + slice_md(3, "c", files="c") + slice_md(4, "d", deps="Slice 1-3", files="d"))
        self.assertEqual(pp.parse(md)[3]["depends_on"], [1, 2, 3])
        self.assertTrue(any("itself" in e for e in pp.check(pp.parse(slice_md(1, "a", deps="1", files="a")))))

    def test_owned_vs_shared_conflict_both_directions(self):
        own = pp.parse(slice_md(1, "own", files="hooks.json"))[0]
        share = pp.parse(slice_md(2, "share", files="b", shared="hooks.json"))[0]
        self.assertTrue(pp._conflict(own, share))
        self.assertTrue(pp._conflict(share, own))
        c = slice_md(1, "c", kind="contract", files="c.py", shared="hooks.json")
        owner = lambda n: slice_md(n, "own", deps="Slice 1", files="hooks.json")
        sharer = lambda n: slice_md(n, "share", deps="Slice 1", files=f"b{n}", shared="hooks.json")
        for md in (c + owner(2) + sharer(3), c + sharer(2) + owner(3)):
            self.assertEqual(pp.waves(pp.parse(md)), [[1], [2], [3]])

    def test_write_preserves_list_continuations(self):
        md = ("# Tasks\n\n## Slice 1: a\n\n**Kind:** feature\n**Risk Tier:** standard\n**Depends On:** (none)\n"
              "**Files:**\n- a.py\n- b.py\n\n### Test Intent\nx\n")
        out = pp.stamp(md, {1: 0})
        self.assertIn("- b.py\n**Wave:** 0\n", out)
        self.assertEqual(pp.stamp(out, {1: 0}), out)
        self.assertEqual(pp.parse(out)[0]["files"], ["a.py", "b.py"])

    def test_real_template_parses(self):
        ref = SCRIPT.parent.parent / "references" / "tasks-format.md"
        block = ref.read_text().split("```markdown")[1].split("```")[0]
        s = pp.parse(block)
        self.assertEqual(s[0]["number"], 1)
        self.assertEqual(s[0]["files"], ["src/file1.ts", "src/file2.ts"])


class VerifyBranchHardeningTests(unittest.TestCase):
    def _repo(self, d):
        vcs(d, "init", "-q", "-b", "main")
        vcs(d, "config", "user.email", "a@b.c")
        vcs(d, "config", "user.name", "t")
        (Path(d) / "a.txt").write_text("1\n" * 20)
        (Path(d) / "u.txt").write_text("u\n" * 20)
        vcs(d, "add", ".")
        vcs(d, "commit", "-qm", "base")
        return vcs(d, "rev-parse", "HEAD").strip()

    def test_base_advanced_after_fork(self):
        with tempfile.TemporaryDirectory() as d:
            base = self._repo(d)
            vcs(d, "checkout", "-qb", "feat")
            (Path(d) / "a.txt").write_text("2\n")
            vcs(d, "commit", "-qam", "work")
            vcs(d, "checkout", "-q", "main")
            (Path(d) / "other.txt").write_text("x")
            vcs(d, "add", ".")
            vcs(d, "commit", "-qm", "main moves")
            new_base = vcs(d, "rev-parse", "HEAD").strip()
            self.assertEqual(pp.verify_branch(new_base, "feat", ["a.txt"], d), [])
            self.assertEqual(pp.verify_branch(base, "feat", ["a.txt"], d), [])

    def test_rename_reports_old_path(self):
        with tempfile.TemporaryDirectory() as d:
            base = self._repo(d)
            vcs(d, "checkout", "-qb", "feat")
            vcs(d, "mv", "u.txt", "a2.txt")
            vcs(d, "commit", "-qm", "mv")
            self.assertIn("u.txt", pp.verify_branch(base, "feat", ["a2.txt"], d))

    def test_owned_normalised_and_dir(self):
        with tempfile.TemporaryDirectory() as d:
            base = self._repo(d)
            vcs(d, "checkout", "-qb", "feat")
            (Path(d) / "sub").mkdir()
            (Path(d) / "sub" / "f.txt").write_text("x")
            vcs(d, "add", ".")
            vcs(d, "commit", "-qm", "w")
            self.assertEqual(pp.verify_branch(base, "feat", ["./sub/"], d), [])
            self.assertEqual(pp.verify_branch(base, "feat", ["sub/f.txt (new)"], d), [])


class ValidationKindTests(unittest.TestCase):
    def test_validation_slice_with_no_files_ok_and_runs_alone(self):
        for files in ("none", "(none)", "(none - runs suite)"):
            md = (slice_md(1, "a", files="a.py") + slice_md(2, "b", files="b.py")
                  + slice_md(3, "validate", kind="validation", deps="Slice 1, Slice 2", files=files))
            sl = pp.parse(md)
            self.assertEqual(sl[2]["files"], [], files)
            self.assertEqual(pp.check(sl), [], files)
            self.assertEqual(pp.waves(sl), [[1, 2], [3]], files)

    def test_validation_slice_runs_alone_even_if_ready_with_others(self):
        md = (slice_md(1, "a", files="a.py")
              + slice_md(2, "validate", kind="validation", files="none")
              + slice_md(3, "b", files="b.py"))
        self.assertEqual(pp.waves(pp.parse(md)), [[1, 3], [2]])

    def test_other_kinds_with_no_files_still_error(self):
        for kind in ("feature", "fix", "refactor"):
            for files in ("", "none", "(none)"):
                errs = pp.check(pp.parse(slice_md(1, "x", kind=kind, files=files)))
                self.assertTrue(any("no Files" in e for e in errs), (kind, files))


if __name__ == "__main__":
    unittest.main()


class SliceIdPatternTests(unittest.TestCase):
    def test_id_matches_markers_id(self):
        mspec = importlib.util.spec_from_file_location(
            "markers", SCRIPT.parent.parent / "hooks" / "markers.py")
        markers = importlib.util.module_from_spec(mspec)
        mspec.loader.exec_module(markers)
        self.assertEqual(pp.ID, markers.ID)

    def test_alnum_suffix_ids_parse(self):
        md = "# Tasks\n\n" + slice_md("2F1", "a", files="a.py") + slice_md("2F2", "b", deps="Slice 2F1", files="b.py")
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "tasks.md"
            p.write_text(md)
            r = subprocess.run([sys.executable, str(SCRIPT), "waves", str(p), "--json"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("2F2", r.stdout)
