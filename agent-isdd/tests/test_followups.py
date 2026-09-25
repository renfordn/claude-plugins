"""Tests for hooks/followups.py and its SessionStart surfacing.

code-reviewer writes `followups` into <git dir>/code-review/findings.json; SessionStart ingests
them into <sdd memory>/<project>/followups/, lists open ones, and hands unrecorded ones to
agent-nelly. The CLI moves an item through open -> picked -> done/dismissed.
"""
import json
import os
import subprocess
import unittest

import hook_test_utils as h

FINDINGS = {
    "scope": "main...HEAD", "level": "Standard", "findings": [],
    "followups": [
        {"kind": "consolidation", "title": "Use validation.normalize_email everywhere",
         "files": ["app/invites.py", "app/newsletter.py"], "why": "Two copies drift.",
         "steps": ["Replace _clean_email", "Delete sanitize_address"]},
        {"kind": "deferred-defect", "title": "Warehouse ids reused after delete",
         "files": ["app/repos/warehouses.py"], "why": "len()+1 ids collide.", "steps": ["Use a counter"]},
        {"kind": "bogus", "title": "ignored"},
    ],
}


def _write_findings(repo, doc=FINDINGS):
    d = os.path.join(repo, ".git", "code-review")
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "findings.json"), "w") as fh:
        json.dump(doc, fh)


def _cli(repo, home, *args):
    env = dict(os.environ, HOME=home, CLAUDE_PLUGIN_DATA=h.plugin_data_for(home))
    return subprocess.run(["python3", os.path.join(h.HOOKS_DIR, "followups.py"), *args], cwd=repo,
                          env=env, capture_output=True, text=True)


def _followups_dir(home, repo):
    return os.path.join(h.plugin_data_for(home), "sdd-memory", h.project_slug_for(repo), "followups")


class FollowupsTests(unittest.TestCase):
    def test_session_start_ingests_and_lists_open_items(self):
        with h.temp_git_repo() as repo, h.temp_home() as home:
            _write_findings(repo)
            decision, rc = h.run_hook("session_start.py", {"cwd": repo}, cwd=repo, env_extra={"HOME": home})
            self.assertEqual(rc, 0)
            ctx = decision["additionalContext"]
            self.assertIn("2 open review follow-ups", ctx)
            self.assertIn("[consolidation] Use validation.normalize_email everywhere — app/invites.py, "
                          "app/newsletter.py (id: use-validation-normalize-email-everywhere)", ctx)
            self.assertNotIn("ignored", ctx)
            self.assertIn("set <id> picked", ctx)
            self.assertEqual(sorted(os.listdir(_followups_dir(home, repo))),
                             ["use-validation-normalize-email-everywhere.md", "warehouse-ids-reused-after-delete.md"])

    def test_session_start_hands_unrecorded_items_to_nelly(self):
        with h.temp_git_repo() as repo, h.temp_home() as home:
            _write_findings(repo)
            decision, _ = h.run_hook("session_start.py", {"cwd": repo}, cwd=repo, env_extra={"HOME": home})
            ctx = decision["additionalContext"]
            self.assertIn("not yet in Agent Nelly memory", ctx)
            self.assertIn("`file-relevance` entries", ctx)
            self.assertIn("recorded <id>", ctx)

    def test_reingest_keeps_status_and_adds_only_new_items(self):
        with h.temp_git_repo() as repo, h.temp_home() as home:
            _write_findings(repo)
            self.assertEqual(_cli(repo, home, "ingest").returncode, 0)
            self.assertEqual(_cli(repo, home, "set", "warehouse-ids-reused-after-delete", "picked").returncode, 0)
            doc = dict(FINDINGS, followups=FINDINGS["followups"] + [
                {"kind": "refactor", "title": "Split pricing module", "files": [], "why": "w", "steps": ["s"]}])
            _write_findings(repo, doc)
            out = _cli(repo, home, "ingest").stdout
            self.assertEqual(out.strip(), "added split-pricing-module")
            listing = _cli(repo, home, "list", "--all").stdout
            self.assertIn("warehouse-ids-reused-after-delete  picked  deferred-defect", listing)
            self.assertNotIn("warehouse-ids", _cli(repo, home, "list").stdout)

    def test_picked_and_recorded_items_leave_the_prompts(self):
        with h.temp_git_repo() as repo, h.temp_home() as home:
            _write_findings(repo)
            _cli(repo, home, "ingest")
            for fid in ("use-validation-normalize-email-everywhere", "warehouse-ids-reused-after-delete"):
                self.assertEqual(_cli(repo, home, "recorded", fid).returncode, 0)
            _cli(repo, home, "set", "use-validation-normalize-email-everywhere", "done")
            decision, _ = h.run_hook("session_start.py", {"cwd": repo}, cwd=repo, env_extra={"HOME": home})
            ctx = decision["additionalContext"]
            self.assertIn("1 open review follow-up from", ctx)
            self.assertNotIn("not yet in Agent Nelly memory", ctx)

    def test_cli_rejects_bad_status_and_path_ids(self):
        with h.temp_git_repo() as repo, h.temp_home() as home:
            _write_findings(repo)
            _cli(repo, home, "ingest")
            self.assertEqual(_cli(repo, home, "set", "warehouse-ids-reused-after-delete", "closed").returncode, 1)
            self.assertEqual(_cli(repo, home, "set", "../x", "done").returncode, 1)
            self.assertEqual(_cli(repo, home, "set", "nope", "done").returncode, 1)

    def test_no_findings_file_is_silent(self):
        with h.temp_git_repo() as repo, h.temp_home() as home:
            decision, rc = h.run_hook("session_start.py", {"cwd": repo}, cwd=repo, env_extra={"HOME": home})
            self.assertEqual(rc, 0)
            self.assertNotIn("follow-up", decision["additionalContext"])


if __name__ == "__main__":
    unittest.main()
