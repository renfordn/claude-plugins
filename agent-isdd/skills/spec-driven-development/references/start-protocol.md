# Start Protocol: steps 0, 3, 4, 6

Read by `spec-driven-development` at Start when SessionStart listed open review follow-ups (step 0), when creating `intent/intent.md` (steps 3-4), and for the **Fast Track classification** (step 6). Steps are numbered as in SKILL.md's Start Protocol; text is verbatim.

0. **Review follow-ups.** If SessionStart listed open review follow-ups and the request is vague
   ("what's next?", "clean things up") or overlaps an item's files, offer the matching items as
   candidates in one line each. If the user picks one, run the `set <id> picked` command
   SessionStart printed and hand that item's file to `requirements-agent` as an existing ticket
   (step 7) — its steps and files are the draft. Record `Follow-up: <id>` in `workflow-state.md`.

3. **[NEW Phase 1.1]** Create `intent/intent.md` with:
   - Project Intent (from agent-nelly brief, or "not yet captured")
   - Feature Goal (seeded from step 2)
   - Success Signals (brief, 2-3 observable outcomes)
   - Anti-Patterns (failure indicators)
   - Intent Anchor: compute SHA256 hash of intent.md content
4. Update `workflow-state.md` with:
   - `Intent Hash: <anchor>`
   - `Intent Alignment Status: unreviewed`

6. **Fast Track classification** (see `references/fast-track.md` for the full contract): judge
   whether this request is a small, well-defined change — a single behavior change, no new
   external interface, no data migration, no cross-plugin `INTEROP.md` contract change, testable
   in one sentence. This is a judgment call, never a keyword regex. Skip this judgment and honor
   the user's own words directly if they explicitly asked for the full workflow or explicitly
   asked to fast-track. Set `Track: Fast` or `Track: Standard` in `workflow-state.md`
   accordingly. When `Track: Fast`, tell the user in one line: "Fast-tracking this as a small
   change — say 'full workflow' if you'd rather go through the full Requirements interview and
   task slicing."
