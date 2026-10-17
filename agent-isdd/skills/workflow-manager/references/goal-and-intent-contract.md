# Goal Field Contract: brief cache management

Read by `workflow-manager` at `start` and `before-continue` when applying the `nelly_brief_cache` validity rules (verbatim from SKILL.md's Goal Field Contract).

- **[Phase 1.2] Brief cache management:** On workflow start, fetch fresh nelly brief and cache
  it in `workflow-state.json` → `nelly_brief_cache` with structure: `{brief_text, fetched_at,
  intent_hash, valid}`. On workflow resume (`before-continue`), check cache validity:
  - If Intent Hash matches && timestamp < 24h old: reuse cached brief (no fetch)
  - If Intent Hash differs || timestamp stale: clear cache, fetch fresh brief, update cache
  - If Intent drift detected: clear cache immediately
- Both nelly calls above (`start`-time Goal-seeding, and the inline `before-continue` check,
  which spawns no subagent at all) are outside the in-session brief-reuse dedup pool described in
  `spec-driven-development`'s Goal-Aware Memory section — neither is ever satisfied by reusing a
  cached brief (persistent cache is OK; in-session context cache is different).
