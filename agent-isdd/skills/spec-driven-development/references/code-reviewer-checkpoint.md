# Code-Reviewer Checkpoint Tracking (High-Risk Slices)

**Corrected 2026-09-16**: this section previously described an automatic invoke-classify-advance
pipeline that was never implemented — this file is now the canonical description. What actually
exists:

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

## Unused helpers

`hooks/high_risk_reviewer.py` still defines helpers from the never-implemented pipeline that only
`tests/test_high_risk_reviewer.py` exercises — nothing in `hooks/` calls them (the hook's
`main()` only tracks phases and emits the passive reminder): `classify_severity`,
`update_reviewed_phases`, `construct_rollback_marker`, `create_follow_up_tasks`,
`create_github_issues`, and `append_to_recap_md` (plus `construct_resume_message` and
`get_high_risk_file_paths_config`, likewise test-only). They model an older code-reviewer output
shape (dimension-level PASS/FAIL/WARN results), not the current `ReportFindings` payload, so do not
wire them up without reconciling that shape first.
