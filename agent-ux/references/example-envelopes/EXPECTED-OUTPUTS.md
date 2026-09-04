# Expected Outputs — Manual Walkthrough Script (Phase 3 Red)

Manual walkthrough script for Phase 3 of
`agent-isdd/proposals/2026-08-12-agent-ux-plugin-extraction/tasks/tasks.md`. Exercises all 5
`event_type`s from `references/example-envelopes/` against `agent-ux/agents/ux-agent.md`, plus
one deliberately malformed envelope, per `INTEROP.md`'s "Envelope misuse" section.

This is a test artifact, not committed code: run each envelope through `ux-agent.md` by hand (or
via a real subagent call) once Phase 3's implementation lands, and confirm the actual output
matches the expected lines stated below, verbatim in structure if not exact wording.

## Current state (Red)

As of this writing, `agent-ux/agents/ux-agent.md` is still the unmodified Phase 1 port. It has:

- No section dispatching on an incoming `event_type` field — its five behavior sections
  ("Breadcrumb", "Spec canvas", "Review dashboard", "Chapter markers", "Out-of-scope flags") are
  each triggered by a caller *narrating* what happened in prose ("the caller tells you a
  section-confirmation checkpoint occurred"), not by reading a structured `delta` keyed to a
  named `event_type`.
- No mention of a `caller` field anywhere, so `agent-tdd`'s TDD-stage chapter exclusion
  (`INTEROP.md`'s "`caller`-keyed rendering rules") has no home to be checked against.
- No defined behavior for a malformed or oversized `delta` — nothing corresponding to
  `INTEROP.md`'s "Envelope misuse" truncate-and-report rule exists in the file at all.

Passing any of the 5 example envelopes, or the misuse variant below, to today's `ux-agent.md`
therefore has **undefined behavior**: it may partially work if the surrounding conversation
happens to also narrate the event in prose (since the file still expects narration), but nothing
in the file governs the envelope's structured fields, and nothing in it references `caller` or
enforces `delta` shape. This is the Red condition Phase 3 must resolve by adding per-`event_type`
dispatch logic that reads the envelope's structured fields directly.

## Gating thresholds under test

Referenced by short name below, from `design.md` / `references/ux-conventions.md`:

1. **Checkpoint-only artifact publishing** — spec-canvas Artifact only republishes on an explicit
   section-confirmation checkpoint, never on every message.
2. **>5-findings/>1-file dashboard threshold** — review dashboard Artifact opens only when
   `finding_count > 5` OR `files_touched` has more than 1 entry; below that, no artifact action.
3. **Phase-transition-only chapter marking** — `mark_chapter` fires only on a phase-level
   transition (or restart/rewind), never on a TDD-stage boundary or a session's first message.
4. **Confirmed-out-of-scope-only task spawning** — `spawn_task` fires only for an issue the
   caller has already confirmed concrete and out of scope; never inferred by `agent-ux` itself.

---

## 1. `breadcrumb-only.md`

Envelope: `caller: agent-isdd`, `phase_state: "Design"`, `delta: {}`, no `artifact_path`.

**Expected output (exactly one line):**

```
Requirements ▸ **Design** ▸ Tasks ▸ Implementation
```

No other line — no artifact action line, no chapter-mark line, no task-spawn line. Any second
line is itself a Test Intent violation for this event type (the breadcrumb_only minimality
invariant extends to the *output* side, not just the input `delta`).

**Threshold exercised:** none of the 4 directly — this event type never touches artifact
publishing, the dashboard, chapter marking, or task spawning. It is the negative control: the
correct output is the breadcrumb line and nothing else, which implicitly confirms none of
thresholds 1/2/3/4 misfire on a bare `breadcrumb_only` event.

---

## 2. `phase-transition.md`

Envelope: `caller: agent-isdd`, `phase_state: "Tasks"`, `delta: {from_phase: "Design",
to_phase: "Tasks", feature_slug: "2026-07-01-session-timeout-warning-banner", one_line_summary:
"Design approved; entering Tasks to slice the warning-banner rollout."}`, `artifact_path` set to
the just-finalized `design.md`.

**Expected output (two lines):**

```
Requirements ▸ Design ▸ **Tasks** ▸ Implementation
Chapter marked: "Tasks" — 2026-07-01-session-timeout-warning-banner: Design approved; entering Tasks to slice the warning-banner rollout.
```

- Breadcrumb reflects the *new* phase (`Tasks` bolded), not the outgoing one.
- Chapter title is exactly `to_phase` (`"Tasks"`), summary drawn from `one_line_summary` plus
  `feature_slug`, per `ux-conventions.md`'s "Title after the phase being entered... keep the
  summary to the feature slug plus what's starting."
- No line reading `artifact_path`'s contents — `agent-ux` may read the design doc on its own
  initiative to corroborate the summary, but that is optional and, if done, produces no separate
  output line; the artifact itself is not republished for this event type.

**Threshold exercised:** #3 (phase-transition-only chapter marking) — this example is a genuine
phase-level transition (`Design → Tasks`), so the chapter mark IS expected to fire. Because
`from_phase`/`to_phase` are phase-level values (not TDD-internal stage names), the TDD-internal
stage exclusion in `INTEROP.md`'s `caller`-keyed rendering rules does not apply here and is not
exercised by this example — see scenario 2a below for the exclusion case itself.

---

## 2a. `tdd-stage-exclusion.md`

Envelope: `caller: agent-isdd`, `phase_state: "TDD:green"`, `delta: {from_phase: "red",
to_phase: "green", feature_slug: "2026-07-01-session-timeout-warning-banner", one_line_summary:
"Red test written for the countdown-dismiss debounce; entering Green to implement."}`,
`artifact_path` set to `tasks.md`.

**Expected output (exactly one line):**

```
Requirements ▸ Design ▸ Tasks ▸ **Implementation**
```

- Same `event_type` (`phase_transition`), same 4-key `delta` shape, and **same `caller:
  agent-isdd`** as scenario 2 above — the difference that changes the outcome is entirely
  `from_phase`/`to_phase` being TDD-internal stages (`red`/`green`) rather than phase-level
  values. `caller` is deliberately identical to scenario 2's: `agent-tdd` can never send this
  envelope itself (no `Agent` tool), so the exclusion can't rely on `caller` differing and is
  keyed on the stage names instead — see `INTEROP.md`'s envelope-shape table.
- No chapter-marked line — the TDD-internal stage exclusion in `INTEROP.md`'s `caller`-keyed
  rendering rules withholds `mark_chapter` for this envelope. This is a silent exclusion, not a
  misuse report: no second line of any kind.
- Breadcrumb collapses to `Implementation` bolded — `phase_state: "TDD:green"` isn't one of
  `Requirements`/`Design`/`Tasks`, and `agents/ux-agent.md`'s Breadcrumb section states
  `Implementation` "renders plain once the handoff to `agent-tdd` has been made — this plugin
  tracks no finer-grained stage detail past that point," so no TDD-stage detail leaks into the
  breadcrumb string itself.

**Threshold exercised:** #3 (phase-transition-only chapter marking), specifically the
TDD-internal stage exclusion sub-case that scenario 2 explicitly does not cover. This closes the
coverage gap this file's own "Open questions" section previously flagged.

---

## 3. `section-checkpoint.md`

Envelope: `caller: agent-isdd`, `phase_state: "Requirements"`, `delta: {section_name:
"Acceptance Criteria", section_body: "...", remaining_section_names: ["Problem Statement",
"Success Metrics", "Constraints", "Out Of Scope"], open_gaps: ["No decision yet on cross-tab
session sync behavior."]}`, `artifact_path` set to `requirements.md`.

**Expected output (two lines):**

```
Requirements ▸ **Requirements** ▸ Tasks ▸ Implementation
Spec canvas published/redeployed to proposals/2026-07-01-session-timeout-warning-banner/requirements/requirements.md
```

(Breadcrumb line note: `phase_state` value `"Requirements"` maps to the same bolded segment name
— the exact rendering of the fixed-order breadcrumb string with `Requirements` bolded.)

- The Artifact line must confirm the *same path* as `artifact_path`, not a newly generated one
  (stable-URL invariant).
- Content of the republished Artifact (not itself an output line, but a property the next slice
  must satisfy): "Acceptance Criteria" rendered in full from `section_body`, the four
  `remaining_section_names` rendered as stubs/placeholders only (no body text for any of them),
  and the one `open_gaps` entry listed.
- Fallback line, if the Artifact tool is unavailable instead: `Artifact tool unavailable — spec
  canvas not published` (or equivalent single line), and nothing else — never a second line
  blocking further caller progress.

**Threshold exercised:** #1 (checkpoint-only artifact publishing) — this event type IS by
definition an explicit checkpoint (the envelope's existence encodes that a section was just
confirmed), so publishing IS expected. This example does not demonstrate the negative case (no
publish on a non-checkpoint event) — that negative case is implicitly covered by scenario 1
(`breadcrumb_only`) producing no artifact line at all.

---

## 4. `review-threshold.md`

Envelope: `caller: code-reviewer`, `phase_state: "Implementation"`, `delta: {finding_count: 7,
files_touched: [3 paths], findings: [7 objects, each {id, title, tier, severity}, no evidence/diff]}`,
`artifact_path` set to `findings.md`.

**Expected output (two lines):**

```
Requirements ▸ Design ▸ Tasks ▸ **Implementation**
Review dashboard published/redeployed with 7 resolvable finding cards
```

**Threshold exercised:** #2 (>5-findings/>1-file dashboard threshold) — this example
deliberately EXCEEDS the threshold on both independent axes (`finding_count: 7 > 5`,
`files_touched.length: 3 > 1`), so the dashboard IS expected to open. The companion
under-threshold counter-example noted in `review-threshold.md`'s own file (`finding_count: 2,
files_touched: ["a.ts"]`) is NOT one of the 5 fixture files, but its expected output is stated
here for completeness since Test Intent requires confirming the threshold both ways:

```
Requirements ▸ Design ▸ Tasks ▸ **Implementation**
no artifact action — below threshold
```

### Ordering requirement: `artifact_path` reads must be deferred until AFTER the threshold check

This is the specific anti-pattern the next slice (`agent-TDD`'s implementation) must not
introduce, called out explicitly per this Test Intent's acceptance criteria:

- **Correct order:** (1) read `finding_count` and `files_touched` directly from `delta`, (2)
  compute whether either exceeds its threshold, (3) only if the threshold is exceeded, read
  `artifact_path` (`findings.md`) to pull evidence/diff hunks for each finding card, (4) publish
  the dashboard.
- **Wrong behavior (what would fail this test):** reading `artifact_path` first — i.e. issuing a
  `Read` call against `findings.md` before or without ever inspecting `finding_count`/
  `files_touched` from the envelope's `delta`. This is wrong for two independent reasons: (a) it
  defeats the pull-over-push invariant's entire point (evidence is pulled *only once an action is
  already decided*, not speculatively), and (b) it would pull evidence even for the
  under-threshold case, wasting a `Read` call and tokens on a dashboard that should never open.
  A correct implementation's `Read` call against `artifact_path` must be causally downstream of,
  and conditioned on, the threshold check passing — not merely textually placed after it while
  actually happening unconditionally.
- A walkthrough that confirms this ordering should show the >5/>1 case producing exactly one
  `Read` against `findings.md` (after the threshold math), and the under-threshold companion case
  producing **zero** `Read` calls against `findings.md` at all.

---

## 5. `out-of-scope-flag.md`

Envelope: `caller: agent-isdd`, `phase_state: "Design"`, `delta: {title: "Cross-tab session sync
uses a polling fallback, not BroadcastChannel", file_path: "src/session/session-context.ts",
context_summary: "..."}`, no `artifact_path`.

**Expected output (two lines):**

```
Requirements ▸ **Design** ▸ Tasks ▸ Implementation
Task spawned: <task-id> — "Cross-tab session sync uses a polling fallback, not BroadcastChannel"
```

- `<task-id>` is whatever id `spawn_task` returns at call time — the expected-output assertion is
  that the id is present and echoed (needed later for `dismiss_task`), not any specific literal
  value.
- The `spawn_task` prompt itself (not a separate output line, but a property to check) must be
  self-contained: built from `context_summary` plus `file_path` only, taking no additional detail
  from surrounding conversation the caller didn't supply.

**Threshold exercised:** #4 (confirmed-out-of-scope-only task spawning) — this example's `delta`
already encodes that the caller has confirmed the issue concrete and out of scope (design.md's
"the caller has already judged this concrete and out of scope before delegating"), so spawning IS
expected without any additional confirmation step by `agent-ux` itself. This fixture set contains
no negative example (a vague/unconfirmed flag) since `out_of_scope_flag`'s envelope shape has no
field for expressing "maybe" — the threshold's negative case is structurally unrepresentable in a
well-formed envelope, only in caller misuse (an agent inventing a flag from a hunch rather than
being told one), which is a caller-side error, not something `ux-agent.md`'s dispatch logic can
detect from the envelope alone.

---

## 6. Malformed/misused envelope — oversized `delta` for `event_type`

Not one of the 5 example-envelope files; a deliberately invalid variant constructed for this test,
per `INTEROP.md`'s "Envelope misuse" section. Uses `phase_transition`'s shape but with a 5th key
smuggling in a full document body, which no `phase_transition` field permits:

```json
{
  "caller": "agent-isdd",
  "event_type": "phase_transition",
  "phase_state": "Tasks",
  "delta": {
    "from_phase": "Design",
    "to_phase": "Tasks",
    "feature_slug": "2026-07-01-session-timeout-warning-banner",
    "one_line_summary": "Design approved; entering Tasks to slice the warning-banner rollout.",
    "full_design_doc": "# Design\n\n## Problem Statement\n\n... (entire design.md body, several hundred lines) ..."
  },
  "artifact_path": "proposals/2026-07-01-session-timeout-warning-banner/design/design.md"
}
```

**Expected output (two lines):**

```
Requirements ▸ Design ▸ **Tasks** ▸ Implementation
Envelope misuse: delta for phase_transition has an unexpected key "full_design_doc" (expected exactly from_phase, to_phase, feature_slug, one_line_summary) — truncated, chapter not marked from unverified payload
```

- The breadcrumb line still renders — it is free and depends only on `phase_state`, which is
  well-formed here, per `ux-conventions.md`'s "Never redraw the breadcrumb mid-explanation" not
  applying to withholding it entirely.
- The oversized/extra field (`full_design_doc`) must NOT appear anywhere in the output — no
  echoing, no partial rendering of the smuggled document body. Per `INTEROP.md`: "`agent-ux`
  truncates and reports the mismatch in one line rather than rendering the oversized payload."
- `mark_chapter` must NOT be called for this envelope — an oversized/malformed `delta` is treated
  as unverified rather than a green light to proceed with the well-formed subset of fields it
  happens to also contain.

**What "wrong" looks like for this scenario specifically:** silently accepting the envelope,
ignoring the extra `full_design_doc` key without reporting it, and marking the chapter anyway
using only the 4 valid fields. That would satisfy the phase-transition dispatch logic in
isolation but violates the misuse-reporting contract — the malformed envelope must be visibly
flagged, not quietly tolerated.

---

## Open questions

- `INTEROP.md`'s misuse rule says `agent-ux` "truncates and reports the mismatch in one line" but
  does not fully specify whether a misuse report should still perform the *valid* subset of the
  action (e.g. still mark the chapter using the 4 conforming fields, report-only on the extra
  key) or withhold the action entirely, as scenario 6 above assumes. I've asserted the
  more conservative "withhold" reading (unverified payload → no action) because `INTEROP.md`'s
  framing treats an oversized `delta` as "a defined failure mode, not undefined behavior," which
  reads as a full refusal rather than a partial-execution compromise — but this is not stated
  explicitly enough in the source `INTEROP.md`/design.md text to be fully unambiguous. Flagging
  for `agent-TDD` and the caller to confirm before Green; if the intended behavior is
  "act on the valid subset, just report the extra key," scenario 6's expected output line 2
  should instead read something like `Chapter marked: "Tasks" — ...; Envelope misuse: unexpected
  key "full_design_doc" in delta (ignored)`.
- ~~No fixture in this 5-file set exercises the `caller: agent-tdd` TDD-stage chapter exclusion~~
  **Resolved**: `tdd-stage-exclusion.md` (scenario 2a above) now covers this case, and
  `INTEROP.md`'s rule itself is verified directly against `agent-tdd`'s own repo (its real six
  stages: Plan → Red → Green → Review → Refactor → Validate), not carried over as an unconfirmed
  assumption. What's still open is adoption, not stage-naming: `agent-tdd` has no live
  integration with `agent-ux` today (see `INTEROP.md`'s `caller`-keyed rendering rules).
