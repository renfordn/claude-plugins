# Phase 4 Red Baseline: `ux-agent` / `ux-conventions` Callsite Inventory

Test artifact for Phase 4 ("Wire agent-isdd to delegate to agent-ux") of
`proposals/2026-08-12-agent-ux-plugin-extraction/tasks/tasks.md`. This is the "Red" state per
Phase 4's Test Intent: before this phase, `agent-isdd` still calls its local `ux-agent.md`; this
document is the concrete, line-numbered checklist of every current reference, so the next slice
(`agent-TDD`) has a diffable target for "Green" (Validation Target: `grep -rn "ux-agent"
agent-isdd/` shows zero hits outside `INTEROP.md`'s new section and `CHANGELOG.md`'s historical
entries).

Command used to generate this inventory (run from repo root, `.git/` excluded):

```
grep -rn "ux-agent\|ux-conventions" . --include="*" -I | grep -v "^\./\.git/"
```

Total hits found: **86**, across 18 files.

- Non-proposal-doc files (the actual runtime/skill surface this phase must fix): **41 hits**
  across 15 files.
- `proposals/2026-08-12-agent-ux-plugin-extraction/` planning docs (`requirements.md`,
  `design.md`, `tasks.md` — the plan for this very extraction): **45 hits** across 3 files. See
  "Open Question" below on whether these count toward the Green target.

---

## 1. Files to be DELETED outright (step 5 of Phase 4's Ordered Steps)

### `agents/ux-agent.md` (3 hits — the file itself)
- Line 2: `name: ux-agent` — frontmatter, defines the local agent.
- Line 8: `You are **ux-agent** for the Spec Driven Development workflow...` — agent persona prose.
- Line 18: `...point them at `references/ux-conventions.md`.` — internal cross-reference to the
  sibling file also being deleted.

Category: **deleted**. Whole file removed per Ordered Step 5; no individual line survives.

### `references/ux-conventions.md` (5 hits — the file itself)
- Line 3: `Owned and read by `agents/ux-agent.md` for the breadcrumb, Artifacts, chapter markers, and`
- Line 8: `The phase `TaskCreate` checklist is the one exception: it is **not** delegated to `ux-agent``
- Line 20: `to `ux-agent`, which never talks to the user and only renders progress state, not one-off`
- Line 39: `## Phase tick list (`TaskCreate`/`TaskUpdate`) — driven by the calling skill, not `ux-agent``
- Line 93: `` `ux-agent` does not infer confidence on its own.``

Category: **deleted**. Whole file removed per Ordered Step 5; no individual line survives.

---

## 2. Delegation instructions in calling skills/commands (must MIGRATE to `agent-ux:ux-agent`)

Per Ordered Step 2: "Update each calling skill's ux-agent invocation to construct the envelope
shape... and target `agent-ux:ux-agent` instead of the in-process agent." Design.md's
Architecture Or Code Touchpoints names the calling skills as `spec-driven-development`,
`workflow-manager`, `requirements-agent`, `design-author`, `tdd-planner`.

### `skills/spec-driven-development/SKILL.md` (10 hits)
- Line 51: `...`ux-agent` subagent for the breadcrumb line. On an actual phase transition (Requirements →` — delegation instruction.
- Line 52: `Design → Tasks → Implementation, or a restart/rewind), tell `ux-agent` so it can also mark a` — delegation instruction.
- Line 54: `breadcrumb text or drive `Artifact`/`mark_chapter` directly from this skill — that's `ux-agent`'s` — prose ownership statement.
- Line 55: `job (see `agents/ux-agent.md`).` — direct file-path pointer to the file being deleted.
- Line 57: `The phase `TaskCreate` checklist is different: `ux-agent` cannot reach `TaskCreate`/` — prose capability statement.
- Line 64: `` `TaskUpdate` per `references/ux-conventions.md`'s Phase tick list conventions.`` — file-path pointer to the file being deleted.
- Line 171: `- `ux-agent` — delegate at every phase transition for the breadcrumb, chapter markers, and any` — delegation checklist entry.
- Line 231: `` `Status` section, and delegate to `ux-agent` to refresh the breadcrumb/checklist.`` — delegation instruction.
- Line 245: `` `ux-agent` because it is a user-facing approval checkpoint (`ux-agent` never talks to the user).`` — prose rationale.
- Line 298: `- Do not hand-roll breadcrumb/checklist rendering — delegate to `ux-agent`.` — delegation instruction.

Category: **migrate** (all 10 — this is the highest-density calling skill named in design.md;
every delegation instruction and both file-path pointers need to become `agent-ux:ux-agent` /
point at `agent-ux`'s own docs instead).

### `skills/workflow-manager/SKILL.md` (3 hits)
- Line 393: `The breadcrumb is owned by `ux-agent`; the `TaskCreate`/`TaskUpdate`/`TaskList` checklist is not` — delegation/ownership prose.
- Line 394: `` (`ux-agent`'s isolated subagent context cannot reach deferred tools via `ToolSearch` in this`` — capability prose.
- Line 399: `directly rather than delegating to `ux-agent`.` — delegation instruction.

Category: **migrate** (all 3).

### `skills/requirements-agent/SKILL.md` (2 hits)
- Line 59: `Delegate to `ux-agent` at each section-confirmation checkpoint (a section just got locked or` — delegation instruction.
- Line 61: `` `references/ux-conventions.md`. Do not redeploy on every message; that's `ux-agent`'s job to`` — file-path pointer + delegation prose.

Category: **migrate** (both).

### `skills/design-author/SKILL.md` (1 hit)
- Line 65: `it; it is not the spec canvas (that's `ux-agent`'s redeployable Artifact over confirmed` — prose mention (ownership).

Category: **migrate**.

### `skills/tdd-planner/SKILL.md` (0 hits)
No current reference found, despite design.md's Architecture Or Code Touchpoints naming
`tdd-planner` among the skills to update in Phase 4. See "Open Question" below — flagged, not
assumed.

### `skills/doc-consistency-auditor/SKILL.md` (2 hits — not named in design.md's calling-skill list)
- Line 37: `section of a file delegating the `TaskCreate` checklist to `ux-agent`, another section of the` — prose example (describing the doc-consistency pattern itself, using ux-agent as an illustrative case).
- Line 76: `` `code-reviewer`'s rule: open a `ux-agent` review-dashboard Artifact above 5 findings or more`` — prose mention of `code-reviewer`'s own delegation rule referencing `ux-agent`.

Category: **migrate** (both) — this skill is not in design.md's explicit calling-skill list but
still names `ux-agent` by string, so it will show up in the Phase 4 grep and must be updated or
explicitly justified as out of scope.

### `commands/isdd-status.md` (1 hit)
- Line 10: `` --path`; use the most recently updated feature folder if several exist). Delegate to `ux-agent` `` — delegation instruction.

Category: **migrate**.

### `commands/isdd-rewind.md` (2 hits)
- Line 21: `After the contract runs, delegate to `ux-agent` to refresh the breadcrumb and sync the` — delegation instruction.
- Line 22: `` `TaskCreate`/`TaskUpdate` checklist directly (`ux-agent` cannot reach deferred tools), then report`` — capability prose.

Category: **migrate** (both).

---

## 3. Cross-reference / pointer prose in other reference docs (must MIGRATE or be re-pointed)

### `references/artifact-templates.md` (2 hits)
- Line 56: `` - `Current Phase` is the primary continuation pointer, and is what the top-level breadcrumb (rendered by `ux-agent`, see `agents/ux-agent.md`) reads directly — no separate progress field exists or should be invented.`` — prose + direct file-path pointer to the file being deleted.
- Line 158: `` the calling skill (not `ux-agent` — see `references/ux-conventions.md`).`` — prose + file-path pointer to the file being deleted.

Category: **migrate** (both — the file-path pointers in particular must not survive since the
target files no longer exist after step 5).

---

## 4. Mechanical/hook code and its tests (must MIGRATE wording, and test assertion string)

### `hooks/phase_task_sync.py` (6 hits)
- Line 7: `TaskUpdate checklist convention (see references/ux-conventions.md) applies to` — comment, file-path pointer.
- Line 11: `ux-agent's job; the TaskCreate/TaskUpdate checklist is the calling skill's own` — comment prose.
- Line 12: `job (ux-agent's isolated subagent context can't reach deferred tools).` — comment prose.
- Line 36: `"ux-agent subagent for the breadcrumb line, and sync the "` — string literal emitted in hook output/guidance text.
- Line 38: `"calling skill (ux-agent's subagent context can't reach those "` — string literal.
- Line 39: `"deferred tools) — see references/ux-conventions.md."` — string literal, file-path pointer.

Category: **migrate** (all 6). Lines 36-39 are the highest-risk subset: they're runtime string
literals emitted by the hook, not just comments, and line 19 of
`tests/test_phase_task_sync.py` asserts on this exact string content (see next entry) — so this
file and its test must change together.

### `tests/test_phase_task_sync.py` (1 hit)
- Line 19: `self.assertIn("ux-agent", msg)` — test assertion, directly coupled to
  `hooks/phase_task_sync.py`'s line-36 string literal above.

Category: **migrate**. This is a test file, but its assertion string is itself one of the 86
callsites this Phase 4 grep will catch — it must be updated in lockstep with
`hooks/phase_task_sync.py`'s wording change (e.g. to assert on `agent-ux:ux-agent` or whatever
replacement string the migrated hook emits), or it will fail for the wrong reason (a real
regression, not a missed-callsite false negative) once the hook's wording changes.

### `hooks/subagent_report.py` (1 hit)
- Line 7: `subagents, and the plugin's own mechanical helpers (planning-agent, ux-agent),` — comment,
  descriptive list of subagent types this hook's report-capture logic excludes/handles.

Category: **migrate** — this is a doc-comment describing hook behavior; should be updated to
reflect that `ux-agent` is no longer an in-process subagent, if the underlying exclusion logic
still needs to describe the cross-plugin `agent-ux:ux-agent` case.

### `statusline/sdd_statusline.py` (1 hit)
- Line 14: `list lives in the harness's own task tracker (see agents/ux-agent.md), not here.` — comment, direct file-path pointer to the file being deleted.

Category: **migrate** — the file-path pointer is dangling once `agents/ux-agent.md` is deleted;
needs to point at `agent-ux`'s own docs (or drop the specific pointer and describe the concept
generically) instead.

---

## 5. Historical / intentionally-preserved references

### `CHANGELOG.md` (1 hit)
- Line 134: `` `ux-agent` subagents; `sdd_memory.py`/`sdd_state.py`/`session_start.py`/`stop_check.py`/`` — historical changelog entry describing a past release's contents.

Category: **left as intentional historical reference** — explicitly named as an expected
exception in both tasks.md's Validation Target and this inventory's Green target below. Phase 4
step 6 will add a *new* CHANGELOG entry for this phase's own change; that new entry is expected
to also mention `ux-agent` by name (describing what was removed/migrated) and is likewise an
intentional historical reference, not a missed callsite.

### `INTEROP.md` (0 hits currently)
No current reference to `ux-agent`/`ux-conventions` exists in `agent-isdd/INTEROP.md` as of this
baseline — the "→ agent-nelly (memory)" section is the closest existing pattern to mirror, but it
names `agent-nelly`, not `ux-agent`. Ordered Step 1 of Phase 4 adds a **new** `→ agent-ux (UX
rendering)` section here; once added, that new section's references to `ux-agent`
(`agent-ux:ux-agent`) are the second explicitly-expected exception in the Green target.

---

## 6. Proposal planning documents (ambiguous — see Open Question)

These three files, all under
`proposals/2026-08-12-agent-ux-plugin-extraction/`, are the requirements/design/tasks documents
*for this extraction itself*. They describe, plan, and justify removing `ux-agent.md` — they are
not runtime callsites, but they are not `CHANGELOG.md` or `INTEROP.md` either, so a literal
reading of the Validation Target command (`grep -rn "ux-agent" agent-isdd/` — no path exclusion
stated) would still flag them as "remaining hits."

- `proposals/2026-08-12-agent-ux-plugin-extraction/requirements/requirements.md` — 6 hits (lines
  13, 14, 19, 36, 55, 87). All are plan-authoring prose describing the extraction's scope and
  success criteria.
- `proposals/2026-08-12-agent-ux-plugin-extraction/design/design.md` — 18 hits (lines 11, 21, 22,
  25, 33, 45, 49, 56, 58, 60, 69, 81, 102, 121, 153, 154, 165, 171). All are design-authoring
  prose (architecture, data contracts, refactor opportunities) describing the planned migration.
- `proposals/2026-08-12-agent-ux-plugin-extraction/tasks/tasks.md` — 21 hits (lines 45, 46, 47,
  49, 65, 97, 133, 142, 146, 163, 180, 186, 195, 205, 206, 226, 228, 233, 242, 249, 286). All are
  task-authoring prose (Phase 1-5 steps, validation targets, this very Phase 4 section) — this is
  the source document this inventory was built from.

Category: **not categorized — open question**, deliberately not resolved here (see below).

---

## Open Questions (flagged, not guessed at)

1. **Do the proposal planning docs count toward the Green target?** Tasks.md's Validation Target
   states the post-migration grep "should show zero hits outside `INTEROP.md`'s new section and
   `CHANGELOG.md`'s historical entries" — it does not mention `proposals/` at all. Read
   literally, the 45 hits in `requirements.md`/`design.md`/`tasks.md` would need to either (a) be
   edited to stop naming `ux-agent`/`ux-conventions` (which would blunt their own historical
   record of what was planned and why), or (b) be treated as a third implicit exception category
   alongside `INTEROP.md` and `CHANGELOG.md`, analogous to how `CHANGELOG.md`'s *historical*
   entries are exempted. This inventory does not resolve that ambiguity — the caller/`agent-TDD`
   should decide whether the post-Phase-4 grep command should add a `--exclude-dir=proposals` (or
   equivalent) to match stated intent, or whether the Validation Target's wording itself needs a
   one-line clarification before Green is claimed.
2. **`skills/tdd-planner/SKILL.md` currently has zero hits**, despite design.md's Architecture Or
   Code Touchpoints and Phase 4's own Risk Tier rationale naming `tdd-planner` among the skills
   "touches every calling skill." Either `tdd-planner` doesn't currently delegate to `ux-agent`
   under that exact string (e.g. it delegates via a different name or indirectly through another
   skill) and design.md's touchpoint list is slightly over-inclusive, or there's a callsite this
   grep-based method can't see (e.g. a dynamic reference). Flagging rather than assuming either
   way — `agent-TDD` should confirm during step 2 whether `tdd-planner` needs a new delegation
   added (not just an existing one migrated) or whether it's correctly out of scope.
3. **`skills/doc-consistency-auditor/SKILL.md`'s 2 hits** are not in design.md's named
   calling-skill list. Whether this skill should also gain a live `agent-ux:ux-agent` delegation
   change, or whether its two mentions are purely illustrative prose that just needs word-level
   updating (not a new delegation callsite), is not stated in the Task description passed to this
   inventory — flagged for `agent-TDD` to confirm against the fuller doc-consistency-auditor
   skill content before treating it as in- or out-of-scope for step 2.

---

## Green Target (exact diff this inventory is measured against)

After Phase 4's Ordered Steps 1-6 complete, running the same command from repo root:

```
grep -rn "ux-agent\|ux-conventions" . --include="*" -I | grep -v "^\./\.git/"
```

should show hits **only** in:

- `INTEROP.md` — the new `→ agent-ux (UX rendering)` section added in step 1 (referencing
  `agent-ux:ux-agent` and pointing at `agent-ux`'s own unavailability contract, not restating
  `ux-conventions.md`'s content).
- `CHANGELOG.md` — the pre-existing line 134 historical entry (unchanged) plus the new Phase 4
  entry added in step 6 (which will itself name `ux-agent`/`ux-conventions` as what was removed).

All 41 non-proposal-doc hits enumerated in sections 1-4 above must be gone or migrated:
- 8 hits (both files in section 1) removed by file deletion.
- 33 hits (sections 2-4) migrated to reference `agent-ux:ux-agent` / drop the dangling
  `agents/ux-agent.md` and `references/ux-conventions.md` file-path pointers / update the
  `hooks/phase_task_sync.py` + `tests/test_phase_task_sync.py` string-literal pair together.

The 45 proposal-doc hits (section 6) and the `tdd-planner`/`doc-consistency-auditor` scope
questions (Open Questions 1-3) are unresolved by this baseline and must be explicitly decided —
not silently left ambiguous — before Phase 4 is marked Green.

**Note on this inventory file itself:** because this document quotes every matched line verbatim
(for traceability), it necessarily contains dozens of its own `ux-agent`/`ux-conventions`
mentions and will itself appear in any raw `grep -rn "ux-agent" agent-isdd/` run from this point
forward. It lives under `proposals/2026-08-12-agent-ux-plugin-extraction/tasks/`, alongside
`tasks.md`, so it falls under the same Open Question 1 treatment as the other proposal docs —
`agent-TDD`/the caller should decide whether it stays (as the permanent record of the Red
baseline) or is archived/excluded once Phase 4 reaches Green.
