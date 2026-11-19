# Continue Protocol

Read by `spec-driven-development` when continuing or resuming a feature (`/isdd-continue`, "continue", "resume"): steps 0-4 including the Rollback Request Check (verbatim from SKILL.md).

## What the hooks already did

On a resume prompt (`/isdd`, `/isdd-continue`, or "continue"/"resume" plus the active feature slug) the
`resume_context` hook (UserPromptSubmit) injects `additionalContext` headed "SDD resume context".
Read it before acting. It fails open: no context means a hook error or nothing to report, not "all clear".
It holds up to four items:

- **Baseline diff** (`baseline.diff` against the `baseline` recorded in `workflow-state.json` when
  Implementation began): `branch_changed` and `head_moved` as old -> new, and `files_changed` (committed
  since the baseline, newly dirty, pre-dirty files whose content changed, or files dirty at baseline
  and clean now). `incomplete` covers both a partial result (committed range could not be diffed) and
  a git failure, so the list may be short or empty. "no changes" means git ran and found none.
- **Carried-forward research labels**, from the file summaries in `research/cache.md` (recorded
  `git_hash` vs the file's current blob hash):
  - `still-applicable`: hash matches, reuse the summary as is.
  - `needs-recheck`: file changed, re-read it before relying on the summary.
  - `unknown`: no hash, file gone, git failed, or the deadline ran out. Treat as needs-recheck.
  - The 4s is the hook's total budget; classification gets min(1.5s, time remaining) and is skipped
    below 0.5s left (all labels `unknown`).
  - When the diff is `incomplete`, every carried item is shown as `unknown`.
- **Intent check**: `intent_hash_repro` (hash of `intent/intent.md` without its Intent Anchor) is
  recorded on the first resume; a later mismatch is reported, so re-check alignment with the user.
  The warning repeats on every resume until cleared: once the user confirms re-alignment, remove
  `intent_hash_repro` from `workflow-state.json` via the normal state write (the next resume
  re-records it).
- **`rollback_pending`**: target, reason and source of a pending rollback. Handle it first (step 0).

SessionStart also prints a one-line baseline summary; the full detail is in the injected context. Do
not recompute the diff by hand.

## Steps

0. **Rollback Request Check:**
   - Use the `rollback_pending` item above (also surfaced by the `before_continue` hook): target phase,
     reason and source, from a prior agent-tdd run that found a slicing blocker (task conflict, design
     contradiction, research gap).
   - Address the issue, then ask the user to run `/isdd-rewind <target>` (user-run: the model cannot
     invoke it); continue the workflow once it has run.

1. Use `workflow-manager` to find the relevant feature folder and resolve state (see its
   Decision Order — `agent-nelly:agent-nelly`'s stored Intent first (when available),
   then `workflow-state.md`, then `workflow-state.json`, then open blockers, then phase files,
   then `recap.md`).
2. **[Phase 1.2]** Check the cached nelly brief in `workflow-state.json` → `nelly_brief_cache`;
   reuse it if valid, else fetch fresh (rules: `workflow-manager`'s Goal Field Contract).
3. Continue from the earliest blocked or incomplete phase; auto-advance through later phases
   whose entry gates are satisfied. If the baseline diff touches files the design or tasks name,
   or a research label is `needs-recheck`/`unknown` for a file the next slice uses, re-read those
   files (or re-run research) before implementing.
4. Pause only when a gate fails, a confirmation checkpoint is required, or implementation was
   not requested.

Do not restart from Requirements if a later phase is already the active incomplete phase,
unless requirement changes invalidate the design or tasks.
