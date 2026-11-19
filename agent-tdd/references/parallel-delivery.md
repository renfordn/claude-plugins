# Parallel delivery: lead protocol

Run from the main thread (the lead) on a feature branch. Default width 4. Workers are
`agent-tdd:agent-TDD` instances in isolated worktrees; the lead alone commits, reviews, merges.
Call every plugin script as `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/<name>.py"`.

Harness facts: a worktree-isolated agent runs in `.claude/worktrees/agent-<id>` on branch
`worktree-agent-<id>`; its completion notification returns `worktreePath` and `worktreeBranch`.
Record both per slice.

## 1. Preflight

1. Confirm a feature branch (not main) and a clean tree. Otherwise stop and tell the user.
2. Read `worktree.baseRef` from settings. It must be `"head"` so worktrees fork from the current
   HEAD, not the default branch. If missing, `AskUserQuestion` before setting it in
   `.claude/settings.local.json`. If declined: **serial fallback** (run slices one at a time with
   `/agent-tdd:tdd`, no worktrees).
3. `git worktree list`: if stale `.claude/worktrees/agent-*` entries exist, offer cleanup via
   `AskUserQuestion`. Never auto-remove.
4. `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/parallel_plan.py" check <tasks.md>`; fix or stop on any
   error. Then `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/parallel_plan.py" waves <tasks.md> --width 4 --json`.

## 2. Contract slice(s)

Slices of kind `contract` run alone in their own wave (as do `high-risk` and `validation` slices).
Merge them before any later wave so workers fork from a HEAD that contains the contract.

## 3. Per wave

1. Record `pre_wave_sha` = current HEAD. Base commit for every worker = `pre_wave_sha`.
2. In ONE message, issue one Agent call per slice: `subagent_type` `agent-tdd:agent-TDD`,
   `isolation: "worktree"`, `model: "sonnet"` (or the spec's Model Tier). Each Slice Spec carries:
   - slice id N and the slice's owned files (only these may be edited; no README/CHANGELOG/INTEROP/agents);
   - the base commit, and the instruction to first run `git merge-base --is-ancestor <base> HEAD`
     and stop with a report if it fails;
   - tdd_check usage: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/tdd_check.py" red|green --slice "Slice N: <title>" --slice-id N --base <base> -- <test cmd>`;
   - "do not commit"; and the report must include `<!--SLICE-ID: N-->` plus BASE, WORKTREE, BRANCH.
3. Each worker stops at `green_pause` with its changes uncommitted. For each, the lead:
   - checks the working tree, not commits: `git -C <worktreePath> diff --stat <base>` and
     `git -C <worktreePath> status --porcelain` (untracked files count). Empty on both means the
     gate stays closed; investigate;
   - spawns `code-reviewer:code-reviewer` in the background with this brief:
     `Review cwd: <worktreePath>`, `Review scope: slice=N`, and a line telling it the changes are
     uncommitted, so review `git diff <base>` plus untracked files (`git status --porcelain`).
     The reviewer must echo `<!--REVIEW-SCOPE: slice=N-->`;
   - resumes the worker with `SendMessage` carrying the findings; repeat until `refactor_complete`;
   - only after `refactor_complete`, commits in that worktree (`git -C <worktreePath> add -A`, then commit).

### Validation slice

A `validation` slice has no owned files and no worktree. It runs alone, after its dependencies,
in the main checkout once the previous wave is merged and green. Run its validation command via
`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/tdd_check.py" integration --wave N --cmd "<validation command>"`.
There is no Red/Green, no commit, no merge, and no verify-branch.

## 4. Verify and merge (slice order)

1. Per slice, before merging:
   `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/parallel_plan.py" verify-branch <pre_wave_sha> <branch> --owned <file> <file> ...`
   `--owned` is the slice's Files plus Test Files, each as its own argv. Shared Files are
   owned only by contract slices. zsh does not word-split unquoted variables, so
   `--owned $FILES` passes one string: write the files out literally. A non-zero exit means
   stop the merge of that slice and re-queue it alone.
2. `git merge --no-ff <branch>` in slice order. On conflict: `git merge --abort`, re-queue that
   slice alone (dependents move to a later wave).
3. After the wave, from the repo root:
   `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/tdd_check.py" integration --wave N --cmd "<full suite>"`.
4. If red: `git revert -m 1 <merge>` for the wave's merges, newest first, re-running the suite
   until green. Re-queue each reverted slice alone; its dependents move to a later wave; the
   re-run gets a fresh Red and a fresh review. Never reset or force. If every merge of the wave
   is reverted and the suite is still red (pre-existing or flaky failure), stop and report to
   the user; do not re-queue.
5. Cleanup: `git worktree remove <worktreePath>` and delete merged `worktree-agent-*` branches
   for merged slices only.

## 5. Finish

After the last wave, run a Deep coherence review (code-reviewer) over the union of changed files,
focused on cross-slice conflicts, duplicated logic, and module boundaries. Then return an
`all_slices_complete` summary: slices, waves, every `TDD-EVIDENCE` line (including integration),
re-queued/reverted slices, review outcomes, follow-ups.
