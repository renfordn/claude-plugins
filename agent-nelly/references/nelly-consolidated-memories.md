# Consolidated memories (weekly cleanup output)

Read by `agent-nelly` when reading weekly-cleanup output (consolidated memories). Text moved verbatim from agent-nelly.md.

## Consolidated memories (weekly cleanup output)

The scheduled weekly job (`scripts/nelly_weekly_consolidate.py`, which runs
`scripts/nelly_cleanup.py` first) reshapes the store to stop it bloating. It works on the
memory root, which is the shared_memory_root option when set, so every machine sees the
same result. Know what it leaves behind and how to use it:

- **`SESSION-HISTORY.md`** (per project, append-only). Each old `session-handoff-*` entry
  becomes one line here (date, files in focus, last commit), and only the newest 5 stay as
  entries. It is not indexed in `MEMORY.md` or `nelly-index.json`. When a caller asks what
  was being worked on earlier, or a brief needs continuity beyond the newest handoffs, read
  the tail of this file and cite it as session history. Never turn its lines back into entries.
- **Entries merged from a closed worktree.** A worktree's store is folded into its parent
  repo's store once the worktree is gone and idle, and its entries arrive under their own
  names. An entry named `<name>--<worktree>.md` clashed with a different `<name>.md` that
  was already there. Treat the pair as near-duplicate candidates: surface both in a brief if
  relevant, and leave merging to `/nelly-memory consolidate`. The merge is recorded as an
  `Action: merged-worktree-store` block in `CONSOLIDATION-LOG.md`.
- **Completed SDD feature summaries.** agent-isdd condenses each finished and idle feature
  to `sdd-memory/<project>/completed/<feature>.md` (goal, decisions, open follow-ups,
  commits). Each new summary starts with `nelly_recorded: no`, and agent-isdd's SessionStart
  lists them the next time a session opens in that project. The session then passes them to
  you as a `new facts` batch labelled `Source: agent-isdd completed-feature summary <path>`.
  This happens in-session because your slug guard only allows writes to the session's own
  project. For each one:
  1. Record one `project`-type entry named `feature-<feature-slug>`, holding the goal,
     the decisions that still constrain future work, and the open follow-ups (`Why:` =
     what the feature was for; `How to apply:` = what a later change touching this area
     must respect). If `feature-<feature-slug>` already exists, update it and don't add a
     second one.
  2. Record each distinct lesson, workaround, or recurring issue from the decisions and
     follow-ups as its own entry (`feedback`, or `error-prevention` for a recurring
     failure), so the promotion judgment below runs on each one separately. That is how a
     cross-project lesson found during one project's feature reaches `global/`.
  3. Never copy the whole summary into an entry. The summary file stays in agent-isdd's
     store as the record. The calling session flips its `nelly_recorded` flag to `yes`
     once you report success; you don't edit agent-isdd's files yourself.
- **Weekly reports** (`consolidation-reports/YYYY-MM-DD.md` under the memory root). They
  list near-duplicate pairs and superseded-but-not-archived anomalies, which only
  `/nelly-memory consolidate` resolves. If a caller asks about memory health, point them
  to the newest report.
