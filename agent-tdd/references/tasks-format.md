# tasks.md format and Design Spec report fields

## tasks.md format

```markdown
# Tasks

## Slice 1: <One-sentence behavior>

**Kind:** fix | refactor | feature | contract | validation
**Risk Tier:** standard | high-risk
**Depends On:** (none | Slice N, Slice M)
**Files:** src/file1.ts, src/file2.ts
**Test Level:** unit | extend <existing test> | integration | e2e
**Parallel Group:** (none | A, B, ...)

### Test Intent
<Observable behavior to test>

### Validation Target
<Command to validate, e.g. "npm test -- slice-1">

### Ordered Steps
1. Step, grounded in research or existing code.
```

### Optional slice fields

Add only when they apply; slices without them stay valid.

- `**Kind:** contract` lands shared interfaces, types or fixtures that parallel slices build against; order it ahead of them via Depends On.
- `**Kind:** validation` runs checks only (e.g. the full suite after merges) with `**Files:** none`; it edits nothing.
- `**Test Files:**` test files the slice owns exclusively.
- `**Shared Files:**` files touched but not exclusively owned (hooks.json, conftest.py, manifests, `__init__.py`); slices sharing a file must not run in the same wave.
- `**UI:** true` marks a slice that changes UI: its Red must be an E2E test in the repo's harness (`references/slice-discipline.md` §4).
- `**Blocked:** <reason>` is written by the lead for a slice that reported `<!--AGENT-TDD-BLOCKED-->`; the lead then skips it and its dependents by hand, using the `parallel_plan.py waves` output (the script is unchanged).
- `**Wave:**` integer >= 0, written by a script, never by hand.

## Design Spec report fields

Design Spec reports use the same markers as slice reports (`<!--AGENT-TDD-REPORT-->` plus the `<!--AGENT-TDD-PHASE: ...-->` line, see agent-TDD.md Handoff report) with phase `slicing_complete` (fields: **Research
Validation**, **Task Slicing**, **Risk Tier Distribution**, **High-Risk Slices** by exact name or
"none", **Readiness Verdict** `ready for implementation` or `paused` with the reason, **Tasks File Path**, **Handoff Facts**, **File Summaries**) or `all_slices_complete` (fields: **Slicing
Summary**, **Implementation Summary**, **Validation Summary** with every slice's `TDD-EVIDENCE`
lines, **Review Request**, **Risks and Follow-ups**, **Handoff Facts**). Per-slice reports in
between use the slice report format.

## Parallel mode

With `Parallel: on`, every slice lists owned Files, Test Files, Shared Files and Depends On; shared interfaces go in `contract` slices. `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/parallel_plan.py" check <tasks.md>` verifies disjointness and `... waves --write <tasks.md>` writes each slice's Wave. The `slicing_complete` report then carries the wave table and the caller fans slices out per `references/parallel-delivery.md`. A worker's slice report also carries `<!--SLICE-ID: N-->` (after the PHASE line) so hooks key evidence and review gates per slice.
