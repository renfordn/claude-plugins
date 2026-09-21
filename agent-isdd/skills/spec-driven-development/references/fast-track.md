# Fast Track

`Track: Fast | Standard` (`workflow-state.md`'s Status section, `"track"` in
`workflow-state.json`; absent/unset means `Standard` — no migration needed for in-flight
features) is set once at Start (see Start Protocol step 6) for a small, well-defined change,
and never changed automatically once Design begins. It changes exactly two things, both
described in full where they apply:

- `requirements-agent` runs its Fast Track entry mode instead of interviewing from scratch
  (see `requirements-agent/SKILL.md`) — Requirements and Design are otherwise identical to
  `Track: Standard`; Design still runs `design-author` + `research-consolidator` in full,
  just against a smaller scope.
- The Implementation Handoff (see `references/implementation-handoff.md`) sends a single Slice
  Spec instead of a Design Spec, with `Review handoff mode: skip` — no `tasks.md` is ever
  produced. The **inline status line** this skill renders itself (see "Visible Progress" in the
  main SKILL.md) omits the `Tasks` segment for `Track: Fast` (`Requirements [✓] → Design [✓] →
  Implementation [▶]`) rather than showing it as permanently pending. The `agent-ux:ux-agent`-
  rendered phase-transition breadcrumb is a separate contract owned by `agent-ux` (fixed
  4-segment order, see its own `agents/ux-agent.md`) and is unchanged by this feature — a known
  cosmetic mismatch (`Tasks` shows as pending, not skipped, on that path) left for a future
  cross-plugin update rather than modified here.

**Escape hatch**: if `requirements-agent` or `design-author` discovers mid-flight that the
change is bigger than the initial classification assumed (real interface/architecture
decisions, multiple subsystems touched), it says so plainly instead of forcing a thin
requirement or design onto something that needs real interviewing. Flip `Track` to `Standard`
at that point, tell the user why in one line, and continue via the Standard path from wherever
the artifact currently stands (re-running Requirements' interview from what Fast Track already
drafted, not from a blank slate). This is the mitigation for the accepted risk of
auto-classification — it costs one course-correction, never a silent bad fit.
