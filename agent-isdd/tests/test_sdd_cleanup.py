"""Tests for scripts/sdd_cleanup.py: completed-feature summaries and worktree-store merges."""
import datetime
import os
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
import sdd_cleanup  # noqa: E402

TODAY = datetime.date(2026, 10, 30)
OLD = time.mktime(datetime.date(2026, 9, 1).timetuple())

STATE = """# Workflow State: Widget Export

## Feature

- Title: Widget Export
- Slug: 2026-09-01-widget-export
- Goal: Let users export widgets.

## Current State

- Workflow Status: {status}
- Next Action: {next_action}

## Last Updated

- Date: 2026-09-01
"""
RECAP = """# Recap

## Open Items

- [x] Done thing
- [ ] Follow-up: add CSV option
- [ ] Risk: export slow on big sets

## Decisions Made

- Use streaming writer, committed as `abc1234`.
- Keep JSON as the default format.
"""
INTENT = """# Intent

## Feature Goal

Let users export their widgets to a file.

## Success Signals

- Export under 2s for 1k widgets
"""


def _write(path, text, mtime=OLD):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    os.utime(path, (mtime, mtime))


def _feature(base, project, slug, status="Complete", next_action="None", mtime=OLD):
    d = os.path.join(base, project, "spec", slug)
    _write(os.path.join(d, "workflow-state.md"), STATE.format(status=status, next_action=next_action), mtime)
    _write(os.path.join(d, "recap", "recap.md"), RECAP, mtime)
    _write(os.path.join(d, "intent", "intent.md"), INTENT, mtime)
    _write(os.path.join(d, "design", "design.md"), "big design\n" * 100, mtime)
    _write(os.path.join(d, "tasks", "tasks.md"), "tasks\n", mtime)
    return d


class SddCleanupTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.base = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def test_idle_completed_feature_condensed_to_summary(self):
        fdir = _feature(self.base, "proj", "2026-09-01-widget-export", next_action="Ship v2 later")
        path, result = sdd_cleanup.run(today=TODAY, base=self.base)
        self.assertFalse(os.path.exists(fdir))
        summary_path = os.path.join(self.base, "proj", "completed", "2026-09-01-widget-export.md")
        self.assertEqual(result["condensed"], [summary_path])
        summary = open(summary_path).read()
        self.assertIn("title: Widget Export", summary)
        self.assertIn("Let users export their widgets to a file.", summary)
        self.assertIn("- Export under 2s for 1k widgets", summary)
        self.assertIn("- Use streaming writer", summary)
        self.assertIn("- Follow-up: add CSV option", summary)
        self.assertNotIn("Done thing", summary)
        self.assertIn("`abc1234`", summary)
        self.assertIn("Ship v2 later", summary)
        self.assertIn("condensed-completed-feature", open(os.path.join(self.base, "proj", "CLEANUP-LOG.md")).read())
        report = open(path).read()
        self.assertIn(f"- {summary_path}", report.split("## New completed-feature summaries")[1])

    def test_summary_starts_unrecorded_in_nelly(self):
        _feature(self.base, "proj", "2026-09-01-widget-export")
        _, result = sdd_cleanup.run(today=TODAY, base=self.base)
        self.assertIn("nelly_recorded: no", open(result["condensed"][0]).read())

    def test_recently_changed_or_in_progress_features_are_kept(self):
        recent = _feature(self.base, "proj", "2026-10-29-recent", mtime=time.mktime(TODAY.timetuple()))
        active = _feature(self.base, "proj", "2026-09-01-active", status="In Progress")
        _, result = sdd_cleanup.run(today=TODAY, base=self.base)
        self.assertTrue(os.path.isdir(recent))
        self.assertTrue(os.path.isdir(active))
        self.assertEqual(result["condensed"], [])
        self.assertEqual([rel for rel, _ in result["kept_features"]], ["proj/2026-10-29-recent"])

    def test_hook_bookkeeping_does_not_count_as_activity(self):
        fdir = _feature(self.base, "proj", "2026-09-01-widget-export")
        now = time.mktime(TODAY.timetuple())
        for name in ("workflow-state.json", "workflow-state.json.lock", "hook_telemetry_log.jsonl"):
            _write(os.path.join(fdir, name), "{}", now)
        _, result = sdd_cleanup.run(today=TODAY, base=self.base)
        self.assertFalse(os.path.exists(fdir))
        self.assertEqual(len(result["condensed"]), 1)

    def test_dry_run_changes_nothing(self):
        fdir = _feature(self.base, "proj", "2026-09-01-widget-export")
        _, result = sdd_cleanup.run(today=TODAY, base=self.base, dry_run=True)
        self.assertTrue(os.path.isdir(fdir))
        self.assertEqual(result["would_condense"], ["proj/2026-09-01-widget-export"])
        self.assertFalse(os.path.exists(os.path.join(self.base, "proj", "completed")))

    def test_worktree_store_merged_then_its_completed_feature_condensed(self):
        parent = "users-me-repo"
        wt = f"{parent}-claude-worktrees-wt1"
        _write(os.path.join(self.base, parent, "RUN-LOG.jsonl"), '{"parent": 1}\n')
        _feature(self.base, parent, "2026-09-01-widget-export", status="In Progress")
        _feature(self.base, wt, "2026-09-01-widget-export")
        _write(os.path.join(self.base, wt, "RUN-LOG.jsonl"), '{"wt": 1}\n')
        _write(os.path.join(self.base, wt, "DOC-AUDIT-STATE.md"), "wt snapshot\n")

        _, result = sdd_cleanup.run(today=TODAY, base=self.base)

        self.assertFalse(os.path.exists(os.path.join(self.base, wt)))
        self.assertEqual(result["merged"][0]["features"], ["2026-09-01-widget-export--wt1"])
        log = open(os.path.join(self.base, parent, "RUN-LOG.jsonl")).read()
        self.assertIn('{"parent": 1}', log)
        self.assertIn('{"wt": 1}', log)
        self.assertFalse(os.path.exists(os.path.join(self.base, parent, "DOC-AUDIT-STATE.md")))
        # The moved-in completed feature is condensed in the same run; the parent's own
        # in-progress feature of the same name is untouched.
        self.assertTrue(os.path.isfile(os.path.join(
            self.base, parent, "completed", "2026-09-01-widget-export--wt1.md")))
        self.assertTrue(os.path.isdir(os.path.join(self.base, parent, "spec", "2026-09-01-widget-export")))

    def test_recent_worktree_store_is_kept(self):
        wt = "users-me-repo-claude-worktrees-live"
        _feature(self.base, wt, "2026-10-29-x", status="In Progress", mtime=time.mktime(TODAY.timetuple()))
        _, result = sdd_cleanup.run(today=TODAY, base=self.base)
        self.assertTrue(os.path.isdir(os.path.join(self.base, wt)))
        self.assertEqual([s for s, _ in result["kept_worktrees"]], [wt])


if __name__ == "__main__":
    unittest.main()
