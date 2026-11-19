# tasks.md format and Design Spec report fields

## tasks.md format

```markdown
# Tasks

## Slice 1: <One-sentence behavior>

**Kind:** fix | refactor | feature | contract
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
- `**Test Files:**` test files the slice owns exclusively.
- `**Shared Files:**` files touched but not exclusively owned (hooks.json, conftest.py, manifests, `__init__.py`); slices sharing a file must not run in the same wave.
- `**Wave:**` integer >= 0, written by a script, never by hand.

## Design Spec report fields

Design Spec reports use the same markers as slice reports (`<!--AGENT-TDD-REPORT-->` plus the `<!--AGENT-TDD-PHASE: ...-->` line, see agent-TDD.md Handoff report) with phase `slicing_complete` (fields: **Research
Validation**, **Task Slicing**, **Risk Tier Distribution**, **High-Risk Slices** by exact name or
"none", **Readiness Verdict** `ready for implementation` or `paused` with the reason, **Tasks File Path**, **Handoff Facts**, **File Summaries**) or `all_slices_complete` (fields: **Slicing
Summary**, **Implementation Summary**, **Validation Summary** with every slice's `TDD-EVIDENCE`
lines, **Review Request**, **Risks and Follow-ups**, **Handoff Facts**). Per-slice reports in
between use the slice report format.
