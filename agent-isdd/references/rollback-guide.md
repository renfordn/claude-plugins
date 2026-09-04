# Rollback Guide: Returning a Finding to agent-isdd

When `agent-tdd` or `code-reviewer` discovers that the *task itself* was wrong — not just
the implementation — it can request a rollback to an earlier spec phase. Two genuinely
different markers feed two different paths, because `agent-tdd` never emits agent-isdd-specific
vocabulary (it's a caller-agnostic plugin — see its own `INTEROP.md`) and so cannot literally
speak the human-relay marker itself.

## Automatic path (agent-tdd's own spawn report, same session)

When `agent-tdd:agent-TDD`'s **initial** spawn report — not a later `SendMessage` resume, which
this hook does not observe — includes its own generic `<!--AGENT-TDD-PLAN-FLAG:reason="..."-->`
marker (its **Plan Validity Flag**; see `agent-tdd/INTEROP.md`), the hook handles the rest
automatically:

1. `hooks/subagent_report.py` sees the marker, defaults the target phase to `Requirements` (see
   "Which target phase to name" below — agent-tdd's marker carries a reason only, never a
   target), and writes `rollback_pending` to `workflow-state.json`, tagging the reason so a
   later reader knows the target was defaulted, not derived.
2. The next time you re-enter agent-isdd (e.g. `/isdd` or `/isdd-continue`),
   `workflow-manager`'s `before-continue` hook detects `rollback_pending` first, re-reads the
   reason text, and routes into the Rewind Contract — re-targeting forward (Design or Tasks) if
   the reason clearly indicates a narrower problem than the defaulted `Requirements`.

**You don't need to do anything** beyond re-entering agent-isdd after the agent-tdd session ends
— but expect the rewind to land on `Requirements` unless the reason text clearly narrows it.

## Human-relay path (agent-isdd's own vocabulary, or agent-isdd NOT in the same session)

This applies when:
- `code-reviewer` found the issue — it has no marker or hook of its own for this at all, per
  its own `INTEROP.md`.
- You resumed `agent-tdd` via `SendMessage` in a separate session (the hook only observes the
  *initial* spawn's `SubagentStop`, not a later resume).
- Anyone already knows agent-isdd's own phase names and wants to name the target explicitly,
  which the automatic path's defaulted `Requirements` cannot do.

In this case there is no automatic hook. To relay the rollback:

1. **Find the marker** in the final report from `agent-tdd` or `code-reviewer`. It looks like:

   ```
   <!--SDD-ROLLBACK-REQUEST: target=<Requirements|Design|Tasks> reason="..."-->
   ```

2. **Open (or re-enter) your agent-isdd session** for this feature.

3. **Paste the marker line** into your message to agent-isdd. For example:

   ```
   <!--SDD-ROLLBACK-REQUEST: target=Design reason="The assumed interface in design.md section 3 doesn't exist — the module was renamed last sprint."-->
   ```

   `workflow-manager`'s `before-continue` hook recognises the marker in user input and
   routes into the Rewind Contract exactly as if it had arrived automatically.

4. agent-isdd will rewind to the named target phase and log the rollback in `recap.md`
   distinctly from a routine rewind.

## Which target phase to name

If the report's `target=` value is unclear or absent, default to the more conservative
(earlier) phase — it is always safe to re-confirm a phase that may have been correct rather
than to skip past one that actually needs revision.

| Finding | Target phase |
|---|---|
| Requirements missed a constraint or edge case | `Requirements` |
| Design assumed a wrong interface or architecture | `Design` |
| Task slicing was oversized or wrongly scoped | `Tasks` |
| Ambiguous — could be Design or Tasks | `Design` (more conservative) |
