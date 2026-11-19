import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hook_test_utils import HOOKS_DIR, feature_spec_dir, make_git_repo, run_hook  # noqa: E402

sys.path.insert(0, HOOKS_DIR)
import approval  # noqa: E402

PAYLOAD = {"hook_event_name": "PostToolUse", "tool_name": "ExitPlanMode"}


class HashTests(unittest.TestCase):
    def test_stable_and_hex(self):
        h = approval.approval_hash("req", "design")
        self.assertEqual(h, approval.approval_hash("req", "design"))
        self.assertRegex(h, r"^[0-9a-f]{64}$")

    def test_changes_with_either_scope(self):
        base = approval.approval_hash("req", "design")
        self.assertNotEqual(base, approval.approval_hash("req2", "design"))
        self.assertNotEqual(base, approval.approval_hash("req", "design2"))

    def test_boundary_is_unambiguous(self):
        self.assertNotEqual(approval.approval_hash("ab", "c"), approval.approval_hash("a", "bc"))

    def test_line_endings_normalised(self):
        self.assertEqual(approval.approval_hash("a\r\nb\n", "x\r\ny"),
                         approval.approval_hash("a\nb\n", "x\ny"))

    def test_none_equals_empty(self):
        self.assertEqual(approval.approval_hash(None, "d"), approval.approval_hash("", "d"))


class VerifyTests(unittest.TestCase):
    def test_outcomes(self):
        h = approval.approval_hash("r", "d")
        self.assertEqual(approval.verify({"approval hash": h}, "r", "d"), "ok")
        self.assertEqual(approval.verify({"approval hash": h}, "r", "d2"), "mismatch")
        self.assertEqual(approval.verify({"approval hash": h.upper()}, "r", "d"), "ok")
        self.assertEqual(approval.verify({"approval hash": ""}, "r", "d"), "missing")
        self.assertEqual(approval.verify({}, "r", "d"), "legacy")
        self.assertEqual(approval.verify(None, "r", "d"), "legacy")

    def test_pending_without_hash(self):
        self.assertEqual(approval.verify({"approval pending": "yes"}, "r", "d"), "pending")
        self.assertEqual(approval.verify({}, "r", "d", {"approval_pending": "yes"}), "pending")
        self.assertEqual(approval.verify({"approval pending": "no"}, "r", "d"), "legacy")

    def test_json_hash_with_md_missing_is_mismatch(self):
        h = approval.approval_hash("r", "d")
        self.assertEqual(approval.verify({}, "r", "d", {"approval_hash": h}), "mismatch")
        self.assertEqual(approval.verify({"approval hash": h}, "r", "d", {"approval_hash": h}), "ok")
        self.assertEqual(approval.verify({"approval hash": h}, "r", "d",
                                         {"approval_hash": "0" * 64}), "mismatch")


class PlaceholderHashTests(unittest.TestCase):
    def test_non_64hex_is_blank(self):
        for junk in ("None", "<hash>", "abc123", "g" * 64, "0" * 63):
            self.assertEqual(approval.verify({"approval hash": junk}, "r", "d"), "missing")
            self.assertEqual(approval.verify({"approval hash": junk, "approval pending": "yes"},
                                             "r", "d"), "pending")
            self.assertEqual(approval.verify({}, "r", "d", {"approval_hash": junk}), "legacy")


class CliTests(unittest.TestCase):
    def _run(self, args, env=None):
        import subprocess
        e = dict(os.environ)
        e.pop("CLAUDE_PLUGIN_DATA", None)
        e.update(env or {})
        return subprocess.run(["python3", os.path.join(HOOKS_DIR, "approval.py")] + args,
                              capture_output=True, text=True, env=e, timeout=20)

    def _spec(self, d, hash_line="- Approval Hash: deadbeef"):
        os.makedirs(os.path.join(d, "requirements"))
        os.makedirs(os.path.join(d, "design"))
        with open(os.path.join(d, "requirements", "requirements.md"), "w") as f:
            f.write("req")
        with open(os.path.join(d, "design", "design.md"), "w") as f:
            f.write("design")
        with open(os.path.join(d, "workflow-state.md"), "w") as f:
            f.write("# S\n- Implementation Requested: No\n%s\n" % hash_line)
        with open(os.path.join(d, "workflow-state.json"), "w") as f:
            json.dump({"approval_hash": "deadbeef"}, f)

    def test_refreeze_replaces_hash_in_md_and_json(self):
        with tempfile.TemporaryDirectory() as d:
            self._spec(d)
            r = self._run(["refreeze", d], {"CLAUDE_PLUGIN_DATA": d})
            self.assertEqual(r.returncode, 0, r.stderr)
            want = approval.approval_hash("req", "design")
            self.assertEqual(r.stdout.strip(), want)
            from sdd_state import parse_state
            self.assertEqual(parse_state(os.path.join(d, "workflow-state.md"))["approval hash"], want)
            with open(os.path.join(d, "workflow-state.json")) as f:
                self.assertEqual(json.load(f)["approval_hash"], want)

    def test_approve_sets_requested_and_pending(self):
        with tempfile.TemporaryDirectory() as d:
            self._spec(d)
            r = self._run(["approve", d], {"CLAUDE_PLUGIN_DATA": d})
            self.assertEqual(r.returncode, 0, r.stderr)
            from sdd_state import parse_state
            f = parse_state(os.path.join(d, "workflow-state.md"))
            self.assertEqual(f["implementation requested"], "Yes")
            self.assertEqual(f["approval pending"], "yes")

    def test_missing_plugin_data_is_clear_error_not_traceback(self):
        with tempfile.TemporaryDirectory() as d:
            self._spec(d)
            r = self._run(["refreeze", d])
            self.assertEqual(r.returncode, 1)
            self.assertIn("CLAUDE_PLUGIN_DATA", r.stderr)
            self.assertNotIn("Traceback", r.stderr)

    def test_refreeze_with_missing_artifact_fails_cleanly(self):
        with tempfile.TemporaryDirectory() as d:
            self._spec(d)
            os.remove(os.path.join(d, "design", "design.md"))
            r = self._run(["refreeze", d], {"CLAUDE_PLUGIN_DATA": d})
            self.assertEqual(r.returncode, 1)
            self.assertNotIn("Traceback", r.stderr)


class _Base(unittest.TestCase):
    def _setup(self, home, repo, state_lines, req="req\r\ntext\r\n", design="design text\n"):
        fdir = feature_spec_dir(home, repo)
        os.makedirs(os.path.join(fdir, "requirements"))
        os.makedirs(os.path.join(fdir, "design"))
        for rel, text in (("requirements/requirements.md", req), ("design/design.md", design)):
            if text is not None:
                with open(os.path.join(fdir, rel), "w", newline="") as f:
                    f.write(text)
        with open(os.path.join(fdir, "workflow-state.md"), "w") as f:
            f.write("\n".join(state_lines) + "\n")
        with open(os.path.join(fdir, "workflow-state.json"), "w") as f:
            json.dump({"current_phase": "Design", "keep": 1}, f)
        return fdir

    def _run(self, home, repo, **extra):
        payload = dict(PAYLOAD, cwd=repo, tool_response={"plan": "p", "isAgent": False})
        payload.update(extra)
        return run_hook("approval.py", payload, cwd=repo, env_extra={"HOME": home})

    def _md(self, fdir):
        return open(os.path.join(fdir, "workflow-state.md")).read()

    def _js(self, fdir):
        return json.load(open(os.path.join(fdir, "workflow-state.json")))


DESIGN_STATE = ["- Workflow Status: Active", "- Current Phase: Design",
                "- Implementation Requested: No", "- Recap: x"]


class EvaluateTests(_Base):
    def test_approval_records_pending_without_hash(self):
        with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as repo:
            make_git_repo(repo)
            fdir = self._setup(home, repo, DESIGN_STATE)
            self.assertEqual(self._run(home, repo), (None, 0))
            md = self._md(fdir)
            self.assertIn("- Implementation Requested: Yes", md)
            self.assertNotIn("Implementation Requested: No", md)
            self.assertIn("- Approval Pending: yes", md)
            self.assertNotIn("Approval Hash", md)
            self.assertIn("- Recap: x", md)
            data = self._js(fdir)
            self.assertEqual(data["implementation_requested"], "Yes")
            self.assertEqual(data["approval_pending"], "yes")
            self.assertNotIn("approval_hash", data)
            self.assertEqual(data["keep"], 1)
            self._run(home, repo)
            md = self._md(fdir)
            self.assertEqual(md.count("Approval Pending:"), 1)
            self.assertEqual(md.count("Implementation Requested:"), 1)

    def test_rejected_response_is_noop(self):
        with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as repo:
            make_git_repo(repo)
            fdir = self._setup(home, repo, DESIGN_STATE)
            before = self._md(fdir)
            for resp in ("Error: user rejected the plan", {"is_error": True}, {"error": "x"},
                         "The user doesn't want to proceed", None, ""):
                self._run(home, repo, tool_response=resp)
                self.assertEqual(self._md(fdir), before, resp)

    def test_wrong_phase_is_noop(self):
        with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as repo:
            make_git_repo(repo)
            fdir = self._setup(home, repo, ["- Workflow Status: Active",
                                            "- Current Phase: Requirements"])
            before = self._md(fdir)
            self._run(home, repo)
            self.assertEqual(self._md(fdir), before)

    def test_no_active_workflow_is_noop(self):
        with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as repo:
            make_git_repo(repo)
            self.assertEqual(self._run(home, repo), (None, 0))

    def test_other_tool_is_noop(self):
        with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as repo:
            make_git_repo(repo)
            fdir = self._setup(home, repo, DESIGN_STATE)
            before = self._md(fdir)
            self._run(home, repo, tool_name="Write")
            self.assertEqual(self._md(fdir), before)

    def test_md_write_preserves_file_mode(self):
        with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as repo:
            make_git_repo(repo)
            fdir = self._setup(home, repo, DESIGN_STATE)
            path = os.path.join(fdir, "workflow-state.md")
            os.chmod(path, 0o600)
            self._run(home, repo)
            self.assertEqual(os.stat(path).st_mode & 0o777, 0o600)


class FreezeTests(_Base):
    def test_freeze_records_hash_and_clears_pending(self):
        with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as repo:
            make_git_repo(repo)
            fdir = self._setup(home, repo, DESIGN_STATE + ["- Approval Pending: yes"])
            h = approval.freeze(fdir)
            self.assertEqual(h, approval.approval_hash("req\ntext\n", "design text\n"))
            md = self._md(fdir)
            self.assertIn("- Approval Hash: " + h, md)
            self.assertIn("- Approval Pending: no", md)
            data = self._js(fdir)
            self.assertEqual((data["approval_hash"], data["approval_pending"]), (h, "no"))
            self.assertEqual(data["keep"], 1)

    def test_freeze_is_idempotent_and_never_overwrites(self):
        with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as repo:
            make_git_repo(repo)
            fdir = self._setup(home, repo, DESIGN_STATE)
            h = approval.freeze(fdir)
            with open(os.path.join(fdir, "design", "design.md"), "w") as f:
                f.write("edited after approval\n")
            self.assertEqual(approval.freeze(fdir), h)
            self.assertEqual(self._md(fdir).count("Approval Hash:"), 1)
            self.assertEqual(self._js(fdir)["approval_hash"], h)

    def test_freeze_refuses_missing_or_empty_artifacts(self):
        for req, design in ((None, "d\n"), ("r\n", None), ("  \n", "d\n"), ("r\n", "")):
            with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as repo:
                make_git_repo(repo)
                fdir = self._setup(home, repo, DESIGN_STATE, req=req, design=design)
                before = (self._md(fdir), self._js(fdir))
                self.assertIsNone(approval.freeze(fdir))
                self.assertEqual((self._md(fdir), self._js(fdir)), before)

    def test_freeze_preserves_file_mode(self):
        with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as repo:
            make_git_repo(repo)
            fdir = self._setup(home, repo, DESIGN_STATE)
            path = os.path.join(fdir, "workflow-state.md")
            os.chmod(path, 0o640)
            approval.freeze(fdir)
            self.assertEqual(os.stat(path).st_mode & 0o777, 0o640)


if __name__ == "__main__":
    unittest.main()
