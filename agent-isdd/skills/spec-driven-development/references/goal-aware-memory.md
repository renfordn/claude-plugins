# Goal-Aware Memory — full caching/reuse contract

This skill is the single fetch/delegation point, per continuous stretch of phase work, for the
nelly brief **and** for `research-consolidator`/`spec-reviewer` findings still valid from earlier
in that same stretch (e.g. a `research-consolidator` finding produced during Design). When a
brief or finding has already been fetched this session and is still visible in context, reuse it
rather than re-calling `agent-nelly:agent-nelly`/`research-consolidator`/`spec-reviewer`
again for the same content. Re-fetch only when one of these triggers applies — identical rule,
same three triggers, scoped to this wider set of cached content, not a new or looser rule:

1. No prior brief or finding is visible in context (a new session, or context was compacted
   since the last fetch) **and** no persistent cache exists in `workflow-state.json`. If persistent
   cache exists and is valid, reuse it instead of fetching. Applies identically to a
   `research-consolidator`/`spec-reviewer` finding: if it isn't visible in context and no
   persistent cache is valid, it isn't reusable.
2. A rewind (Rewind Contract) or a Mid-Phase Change Classification happened since the cached
   brief/finding was fetched — both live in `workflow-manager`'s `SKILL.md`. A rewind or
   mid-phase change can invalidate a cached codebase finding exactly as it can invalidate a
   brief, since either can change what "the current design/task" even means. **[Phase 1.2]** Also
   invalidates persistent cache; clear `nelly_brief_cache` from `workflow-state.json`.
3. `workflow-manager`'s `before-continue` Intent-alignment check flagged a divergence since the
   cached brief/finding was fetched. When this fires, treat every cached item (brief and any
   `research-consolidator`/`spec-reviewer` finding alike) as invalidated, not only the brief — an
   Intent-level divergence is a signal about the whole stretch of work, not brief-specific.
   **[Phase 1.2]** Clear persistent cache on Intent drift.

None of the three triggers assumed brief-specific semantics that fail to hold for a
`research-consolidator`/`spec-reviewer` finding — re-verified as part of extending this rule's
scope, per design.md's mitigation for the correctness risk this generalization raises.

When delegating into `workflow-manager` or `design-author`, pass along the
already-fetched brief and any still-valid finding explicitly rather than letting any of them
re-derive or re-fetch on their own; `design-author` checks for a still-valid
cached finding before re-delegating to `research-consolidator`, mirroring how it already checks for a
reusable agent-nelly brief. `workflow-manager`'s own `start`-time Goal-seeding call is a distinct-purpose, always-fresh
call outside this dedup pool — see its Goal Field Contract section; it is never satisfied by
reusing a cached brief. The `before-continue` Intent-alignment check no longer spawns a nelly
subagent — it runs inline against the Intent already in session context (see
`workflow-manager/SKILL.md`'s Goal Field Contract).

## Brief caching mechanics

**[Phase 1.2] Brief caching:** On workflow resume (`before-continue`), check if a cached nelly
brief exists in `workflow-state.json`'s `nelly_brief_cache` field:
- If cached brief is valid (Intent Hash matches + timestamp < 24h old): reuse cached brief, no fetch
- If cached brief is invalid (Intent Hash mismatch OR timestamp stale): fetch fresh brief, update cache
- If no cached brief: fetch fresh brief, cache it

When the next phase is **Design**, include `surface relevant memory: true` in the nelly call so
the brief's `Relevant entries` section is populated. `design-author` passes those entries to
`research-consolidator` in place of the former separate pre-sweep nelly call — no second nelly
spawn needed. For other phases, `surface relevant memory` is not required unless you have a
specific reason to request it.

## Memory write-back at phase boundaries

At each `after-*` hook, this skill performs the nelly write-back call directly, following the
contract defined in `workflow-manager`'s Lifecycle Hooks section (which owns the rule, not the
call itself — see its ownership note). The criterion and graceful-degradation rules are defined
in `INTEROP.md`'s "→ agent-nelly" section.
