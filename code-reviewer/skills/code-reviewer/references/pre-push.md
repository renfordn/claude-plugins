# Pre-push review (R15)

`hooks/pre_push_offer.py` denies a `git push` once per unreviewed HEAD and offers this review. Follow it when the offer is accepted. Dry runs, `--help`, branch deletes, tags-only pushes and pushes with nothing new (HEAD already on its upstream or any remote-tracking ref) are not offered. The offer lists open gating findings from the last review's findings.json; re-check those first (references/recheck.md). Put the offer to the user (review or skip); never skip it on their behalf, even under a pre-authorized push. A commit and push chained in one command is offered once with a request to split them.

- **Scope: the whole outgoing diff.** Review `review_plan.py plan --base <base>` (the command is in the offer; base is the upstream, else `origin/HEAD`, `origin/main` or `main`): every commit being pushed, not just the last. Exclude unrelated working-tree changes (uncommitted or untracked files are not being pushed).
- **Fresh eyes.** Review as if you had not written it: read the diff cold, do not lean on earlier reviews or the author's intent. Run the normal Review Pipeline for the risk level.
- **Marker.** The first line of the review summary is `<!--PRE-PUSH-REVIEW-->`.
- **Marking reviewed.** Finishing an unscoped `code-reviewer` run (report has `<!--CODE-REVIEWER-REPORT-->`, no `<!--REVIEW-SCOPE:` line) marks HEAD `reviewed` automatically (SubagentStop): the worktree named by the report's `Review cwd:` line, else the run's cwd. A report with open gating findings (block_commit, pause_for_review, decision block) marks nothing: fix and re-check them first. Otherwise run `python3 "${CLAUDE_PLUGIN_ROOT}/hooks/pre_push_offer.py" mark-reviewed --cwd <repo>`. A new commit makes HEAD unreviewed again.
- **No push permission.** The review and the mark do not authorize the push; the push still follows the user's own rules.
- **Declining.** Re-running the push without a review pushes and records `declined`. `declined` is never accepted risk: do not write it as `decision: accept`, a `deferred-defect` follow-up, or a Review Fallback.
- **Escape hatch.** `CODE_REVIEWER_PREPUSH=off` disables the offer.
