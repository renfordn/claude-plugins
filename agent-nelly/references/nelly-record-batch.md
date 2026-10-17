# Recording new facts (batch)

Read by `agent-nelly` when the caller passes a `new facts` field (a batch of facts to record). Text moved verbatim from agent-nelly.md.

### Recording new facts (batch)

When the caller passes `new facts` (plural — a `New facts:` block with
several items), this replaces N separate calls (and N cold subagent spawns)
with one. Do not process the list as N independent runs of "Recording a new
fact" — the one difference that matters is the in-batch duplicate check in
step 1, which only makes sense with the whole list in view at once.

1. **In-batch duplicate check, before writing anything.** Compare every item
   in the list against every other item in the list (same near-duplicate
   judgment used in "Promotion write-back"'s existing-entry check: same
   underlying fact described from a different angle, not merely a related
   topic). Group the list into:
   - singletons — items with no in-batch duplicate, and
   - duplicate groups — two or more items judged to describe the same
     underlying fact.
   This check is scoped to the batch itself, not against entries already on
   disk — an in-batch item that happens to duplicate an existing entry is
   caught later, per-entry, by "Promotion write-back"'s own existing
   near-duplicate check (global tier) or is simply written as a new local
   entry (local tier has no analogous existing-entry dedup step, same as the
   single-fact path today).
2. For each **singleton**, write it exactly as "Recording a new fact" above
   (steps 1-9: name, description, type, `last_referenced`, ensure `entries/`
   exists, write, index line, verify).
3. For each **duplicate group**, write **one** merged entry instead of one
   per item — same reconciliation approach as `nelly-maintenance`'s
   "Consolidation write-back": pick a new kebab-case `name` covering the group's shared subject, write
   one `description`, and reconcile every item's content into one coherent
   body. Nothing was written to disk for these items before the merge, so
   there is nothing to archive and no consolidation-log entry — this is
   arriving-as-duplicates, not becoming-duplicates-later. In `Written`,
   record it as e.g. "Merged 2 in-batch duplicate facts into
   `<name>`." naming which raw items were folded in.
4. Guarantee `entries/` exists once, before the batch's first write (`python3
   hooks/nelly_memory.py --entries-path [cwd]` via `Bash`) — it is
   idempotent, so doing it once for the whole batch instead of once per item
   is safe and avoids a redundant `Bash` call per item.
5. Process singletons and duplicate-group merges **sequentially, one entry
   at a time**, each through its own write-then-promote cycle: write the
   entry, verify it (Read, same as the single-fact path), then immediately
   run the promotion judgment (below) on it before moving to the next entry.
   Never batch all the writes first and run promotion afterward — this keeps
   the existing "promotion always needs a written entry to evaluate"
   invariant true for every entry, and keeps failures independent: if one
   entry's write fails after its retry, record that failure in `Written` and
   continue with the remaining entries rather than aborting the whole batch.
6. `Written` accumulates one block per final entry (singleton or merge), in
   processing order — created, promoted/skipped/near-duplicate-globally, or
   failed. This is the same shape `Written` already tolerates for a list of
   changes; no new reporting format is needed.
