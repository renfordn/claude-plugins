# Pre-push review (R15)

`hooks/pre_push_offer.py` denies a `git push` once per unreviewed HEAD and offers this review. Follow it when the offer is accepted. Dry runs, `--help`, branch deletes, tags-only pushes and pushes with nothing ahead of the upstream are not offered.

- **Scope: the whole outgoing diff.** Review `review_plan.py plan --base <base>` (the command is in the offer; base is the upstream, else `origin/HEAD`, `origin/main` or `main`): every commit being pushed, not just the last. Exclude unrelated working-tree changes (uncommitted or untracked files are not being pushed).
- **Fresh eyes.** Review as if you had not written it: read the diff cold, do not lean on earlier reviews or the author's intent. Run the normal Review Pipeline for the risk level.
- **Marker.** The first line of the review summary is `<!--PRE-PUSH-REVIEW-->`.
- **Marking reviewed.** Finishing an unscoped `code-reviewer` run (report has `<!--CODE-REVIEWER-REPORT-->`, no `<!--REVIEW-SCOPE:` line) marks HEAD of that run's cwd `reviewed` automatically (SubagentStop). Otherwise, and for a review of another worktree (the auto-mark uses the stop's cwd), run `python3 "${CLAUDE_PLUGIN_ROOT}/hooks/pre_push_offer.py" mark-reviewed --cwd <repo>`. A new commit makes HEAD unreviewed again.
- **No push permission.** The review and the mark do not authorize the push; the push still follows the user's own rules.
- **Declining.** Re-running the push without a review pushes and records `declined`. `declined` is never accepted risk: do not write it as `decision: accept`, a `deferred-defect` follow-up, or a Review Fallback.
- **Escape hatch.** `CODE_REVIEWER_PREPUSH=off` disables the offer.
