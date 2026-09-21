# Code-Reviewer Checkpoint Tracking (High-Risk Slices)

**Corrected 2026-09-16**: this section previously described an automatic invoke-classify-advance
pipeline that was never implemented — see `INTEROP.md`'s "Auto Code-Reviewer Invocation" section
for the full correction. What actually exists:

After agent-tdd spawns and begins Red-Green-Refactor, it marks each slice with a Risk Tier
(`standard` or `high-risk`). On each `agent-tdd` `SubagentStop`, the `high_risk_reviewer` hook
tracks high-risk phases (and standard phases touching a high-risk file path) in
`workflow-state.json`'s `code_reviewer_tracking`, and surfaces a passive reminder listing which
high-risk phases haven't been marked reviewed yet — no severity classification, no automatic
invocation, no auto-resume. Running code-reviewer on those phases, resolving findings, and
resuming `agent-tdd` all go through the ordinary manual review pause (see "The mandatory review
pause" in `agent-tdd/INTEROP.md` and the "Code-Review Gate" section in this plugin's own
`INTEROP.md`) — this checkpoint only helps you not forget a high-risk slice, it doesn't drive
the review itself.

**Configuration** (workflow-state.json):
```json
{
  "code_reviewer_tracking": {
    "high_risk_phases": ["Phase 1", "Phase 2", ...],
    "reviewed_phases": [...]
  }
}
```

See `INTEROP.md`'s "Auto Code-Reviewer Invocation" section for the full correction and the
dead-code inventory it points to.
