"""Tests for hooks/resume_context.py (UserPromptSubmit)."""
import json
import os
import subprocess
import sys
import types
import unittest

import hook_test_utils as h

sys.path.insert(0, h.HOOKS_DIR)
import resume_context  # noqa: E402

SLUG = "2020-01-01-test-feature"
RB = {"target": "T", "reason": "r", "source": "s"}


def run(prompt, repo, home, cwd=None):
    script = os.path.join(h.HOOKS_DIR, "resume_context.py")
    r = subprocess.run(["python3", script], input=json.dumps({"cwd": repo, "prompt": prompt}),
                       capture_output=True, text=True, cwd=cwd or repo,
                       env=h._hook_env({"HOME": home}), timeout=10)
    out = r.stdout.strip()
    ctx = json.loads(out)["hookSpecificOutput"]["additionalContext"] if out else None
    return ctx, r.returncode


def seed(home, repo, state_json):
    d = h.feature_spec_dir(home, repo, SLUG)
    h.seed_state_file(d, **{"Current Phase": "Implementation", "Workflow Status": "In Progress"})
    with open(os.path.join(d, "workflow-state.json"), "w") as fh:
        json.dump(state_json, fh)
    return d


def write_cache_json(d, summaries):
    os.makedirs(os.path.join(d, "research"), exist_ok=True)
    with open(os.path.join(d, "research", "cache.md"), "w") as fh:
        fh.write("# Cache\n```json\n" + json.dumps(summaries) + "\n```\n")


def write_intent(d, body, anchor="ID-0"):
    os.makedirs(os.path.join(d, "intent"), exist_ok=True)
    with open(os.path.join(d, "intent", "intent.md"), "w") as fh:
        fh.write("# Intent\n\n## Goal\n%s\n\n## Intent Anchor\nID: %s\n" % (body, anchor))


def git_out(repo, *a):
    return subprocess.run(["git", *a], cwd=repo, capture_output=True, text=True).stdout.strip()


class ResumeContextTests(unittest.TestCase):
    def test_no_workflow_is_silent(self):
        with h.temp_git_repo() as repo, h.temp_home() as home:
            self.assertEqual(run("/isdd-continue", repo, home), (None, 0))

    def test_non_resume_prompt_is_silent(self):
        with h.temp_git_repo() as repo, h.temp_home() as home:
            seed(home, repo, {"rollback_pending": RB})
            self.assertEqual(run("what is the weather", repo, home), (None, 0))

    def test_resume_reports_baseline_labels_intent_and_rollback(self):
        with h.temp_git_repo() as repo, h.temp_home() as home:
            for n, c in (("ok.txt", "1"), ("chg.txt", "2")):
                with open(os.path.join(repo, n), "w") as fh:
                    fh.write(c)
            subprocess.run(["git", "add", "."], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-qm", "x"], cwd=repo, check=True)
            summaries = [{"path": "ok.txt", "git_hash": git_out(repo, "hash-object", "ok.txt")},
                         {"path": "chg.txt", "git_hash": "0" * 40},
                         {"path": "nohash.txt"}]
            d = seed(home, repo, {
                "baseline": {"branch": "other", "head": git_out(repo, "rev-parse", "HEAD"),
                             "dirty_files": []},
                "rollback_pending": {"target": "Design", "reason": "scope", "source": "tdd"},
            })
            write_cache_json(d, summaries)
            write_intent(d, "goal")
            run("/agent-isdd:isdd", repo, home)  # first resume records the repro hash
            write_intent(d, "goal changed")
            ctx, rc = run("/agent-isdd:isdd", repo, home)
            self.assertEqual(rc, 0)
            self.assertIn("branch changed: other -> ", ctx)
            self.assertIn("still-applicable: ok.txt", ctx)
            self.assertIn("needs-recheck: chg.txt", ctx)
            self.assertIn("unknown: nohash.txt", ctx)
            self.assertIn("Intent changed", ctx)
            self.assertIn("rollback_pending", ctx)
            self.assertIn("Design", ctx)

    def test_intent_first_resume_records_then_flags_only_real_change(self):
        with h.temp_git_repo() as repo, h.temp_home() as home:
            d = seed(home, repo, {"intent_hash": "model-written-garbage", "rollback_pending": RB})
            write_intent(d, "goal", anchor="ID-1")
            ctx, _ = run("/isdd", repo, home)
            self.assertNotIn("Intent changed", ctx)
            with open(os.path.join(d, "workflow-state.json")) as fh:
                st = json.load(fh)
            with open(os.path.join(d, "intent", "intent.md")) as fh:
                self.assertEqual(st["intent_hash_repro"], resume_context.intent_repro_hash(fh.read()))
            self.assertEqual(st["rollback_pending"]["target"], "T")
            write_intent(d, "goal", anchor="ID-2")  # anchor-only edit: not a change
            ctx, _ = run("/isdd", repo, home)
            self.assertNotIn("Intent changed", ctx)
            write_intent(d, "other goal", anchor="ID-2")
            ctx, _ = run("/isdd", repo, home)
            self.assertIn("Intent changed", ctx)

    def test_cache_md_bullet_format_and_not_captured(self):
        with h.temp_git_repo() as repo, h.temp_home() as home:
            with open(os.path.join(repo, "f.txt"), "w") as fh:
                fh.write("x")
            blob = git_out(repo, "hash-object", "f.txt")
            d = seed(home, repo, {})
            os.makedirs(os.path.join(d, "research"))
            with open(os.path.join(d, "research", "cache.md"), "w") as fh:
                fh.write("# Cache\n- path: f.txt git_hash: %s\n- path: g.txt git_hash: not captured\n"
                         % blob)
            ctx, _ = run("/isdd-continue", repo, home)
            self.assertIn("still-applicable: f.txt", ctx)
            self.assertIn("unknown: g.txt", ctx)

    def test_unparseable_cache_md_emits_no_labels(self):
        with h.temp_git_repo() as repo, h.temp_home() as home:
            d = seed(home, repo, {"rollback_pending": RB})
            os.makedirs(os.path.join(d, "research"))
            with open(os.path.join(d, "research", "cache.md"), "w") as fh:
                fh.write("just prose\n")
            ctx, _ = run("/isdd-continue", repo, home)
            self.assertNotIn("Carried-forward", ctx)

    def test_resume_detection(self):
        for p, want in (("/isdd", True), ("/agent-isdd:isdd", True), ("/isdd-continue", True),
                        ("/isdd build a new thing", False), ("continue " + SLUG, True),
                        ("continue", False), ("resume the work", False)):
            self.assertEqual(resume_context.is_resume_prompt(p, SLUG), want, p)

    def test_context_prefixed_with_slug(self):
        with h.temp_git_repo() as repo, h.temp_home() as home:
            seed(home, repo, {"rollback_pending": RB})
            ctx, _ = run("/isdd", repo, home)
            self.assertIn(SLUG, ctx.splitlines()[0])

    def test_overall_deadline_skips_slow_steps(self):
        calls = []
        fake = types.SimpleNamespace(monotonic=iter([0.0] + [3.9] * 50).__next__)
        with h.temp_git_repo() as repo, h.temp_home() as home:
            d = seed(home, repo, {"baseline": {"branch": "x", "head": "y", "dirty_files": []}})
            write_cache_json(d, [{"path": "a", "git_hash": "b"}])
            orig = (resume_context.time, resume_context.baseline.diff,
                    resume_context.research_cache.classify_summaries)
            orig_active = resume_context.sdd_state.active_state_file
            resume_context.sdd_state.active_state_file = lambda cwd: os.path.join(
                d, "workflow-state.md")
            self.addCleanup(setattr, resume_context.sdd_state, "active_state_file", orig_active)
            resume_context.time = fake
            resume_context.baseline.diff = lambda *a, **k: calls.append("diff") or {}
            resume_context.research_cache.classify_summaries = lambda *a, **k: calls.append("cls") or {}
            try:
                resume_context.build_context({"cwd": repo, "prompt": "/isdd"})
            finally:
                (resume_context.time, resume_context.baseline.diff,
                 resume_context.research_cache.classify_summaries) = orig
        self.assertEqual(calls, [])

    def test_incomplete_baseline_marks_everything_unknown(self):
        base = {"incomplete": True, "branch_changed": [], "head_moved": [], "files_changed": []}
        ctx = resume_context.format_context(base, {"still_applicable": [{"path": "a"}],
                                                    "needs_recheck": [], "unknown": []},
                                            None, None)
        self.assertIn("unknown: a", ctx)
        self.assertNotIn("still-applicable", ctx)

    def test_git_failure_fails_open(self):
        with h.temp_home() as home, h.temp_git_repo() as repo:
            seed(home, repo, {"baseline": {"branch": "x", "head": "y", "dirty_files": []}})
            _, rc = run("/isdd-continue", repo, home, cwd=repo)
            self.assertEqual(rc, 0)
            _, rc = run("/isdd-continue", os.path.join(repo, "nonexistent"), home, cwd=repo)
            self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
