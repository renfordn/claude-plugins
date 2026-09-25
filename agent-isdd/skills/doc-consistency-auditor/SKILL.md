---
name: doc-consistency-auditor
description: "[Internal — invoked automatically by hooks/commit_audit_gate.py, or on request] Audits skills/, agents/, commands/, hooks/, and every plugin's INTEROP.md for duplicated/contradictory claims, dangling references, and cross-plugin interop drift, auto-fixing high-confidence findings."
---

# Doc Consistency Auditor

Claude-native audit skill, invoked as a plain skill (not a Task-tool subagent) so its findings
render directly with `ReportFindings` in the same turn — same reasoning as `code-reviewer`. Tool
references use Claude-native tools: `Bash`, `Read`, `Edit`, `Grep`, `Glob`, `ReportFindings`.

Born from Agent Responsibility Cleanup, whose real problems were found only via a one-off manual
audit, and whose own doc-only fix for the `memory-orchestrator` slug bug failed to prevent
recurrence one session later. This skill exists to make that class of audit repeatable and
enforced, not occasional.

## Use This Skill When

- `hooks/commit_audit_gate.py` denies a `git commit` because no clean, current-diff audit exists
  — the gate's denial reason names this skill; run it, then retry the commit.
- The user explicitly asks for a documentation/responsibility-consistency audit.

Unlike `code-reviewer`, this skill is **not** scoped to a caller-named diff or file set — it
always scans the same four directories in full, because a contradiction can exist between an
untouched file and a touched one. This is a deliberate, new capability shape, not an extension
of `code-reviewer`'s per-diff scoping (as of this skill's Design phase, `code-reviewer`'s own
SKILL.md scoped it to a caller-named diff/file set, not a directory sweep — re-check that file if
this claim needs to be current rather than historical).

## Scope

Read every file under `skills/`, `agents/`, `commands/`, `hooks/` (not just files touched in the
current diff — see above), plus every plugin root's `INTEROP.md` (one per plugin, e.g.
`agent-tdd/INTEROP.md`, `code-reviewer/INTEROP.md` — discover the set with
`find . -maxdepth 2 -name INTEROP.md`, never a hardcoded list, so a new plugin's `INTEROP.md` is
picked up automatically). Look for exactly five finding classes:

1. **Duplicated or contradictory responsibility claims** — two or more files claiming the same
   capability without an explicit "this is a documented shared split" note, or two files stating
   opposite rules for the same thing (Agent Responsibility Cleanup's canonical example: one
   section of a file delegating the `TaskCreate` checklist to a subagent, another section of the
   *same* file saying the opposite).
2. **Near-verbatim duplicated prose** — the same explanation or rule restated almost word-for-
   word across two or more files instead of stated once and referenced (token-cost duplication,
   per the plugin's stated token-efficiency mission).
3. **Unverifiable "confirmed" claims** — phrasing that states a harness/platform behavior as
   settled fact ("confirmed via live test", "confirmed by live re-test," or equivalent) with
   nothing in the repo backing the claim beyond the phrasing itself.
4. **Dangling agent/skill references** — a file naming an agent, skill, command, or hook file
   that no longer exists, was renamed, or never existed. Applies across plugin boundaries too:
   an `INTEROP.md` (or any other file) naming another plugin's agent, skill, tool, file path, or
   schema file is a dangling reference if that target no longer exists in the named plugin.
5. **Cross-plugin interop drift** — a claim one plugin's `INTEROP.md` (or a skill/agent file)
   makes *about another plugin's* current behavior, contract, or shape, where that claim no
   longer matches the referenced plugin's actual current file. This is `doc-consistency-auditor`'s
   only finding class that requires reading a *second* plugin to verify a claim made in the
   first — a same-file or same-plugin contradiction belongs in class 1 instead. Concretely, for
   every cross-plugin reference found (a quoted rule, a named threshold/value, a described
   schema or file shape, a "re-check X if this claim needs to be current" hedge already present
   in the source file — treat that hedge as marking exactly the claim to verify, not as an
   excuse to skip it):
   - Read the referenced plugin's actual current file/section.
   - Confirm the quoted or paraphrased claim still holds (e.g. `agent-isdd`'s own
     `doc-consistency-auditor` SKILL.md claims elsewhere in this file that `code-reviewer`'s
     `SKILL.md` scopes reviews to a caller-named diff/file set — verify that's still what
     `code-reviewer`'s `SKILL.md` says, not what it said historically).
   - A **mirrored value** (the same literal threshold/constant intentionally duplicated across
     plugins, e.g. the 5-finding/1-file dashboard threshold declared once in `code-reviewer`'s
     `SKILL.md` and mirrored by `agent-isdd`'s own override note) drifts the moment the values disagree — diff the literal
     values, don't just confirm each file parses.
   - A documented, explained deviation (like this skill's own "Visual Review" override above) is
     not drift — only flag a mismatch that is *not* already acknowledged as intentional in both
     places.

## Evidence Tier Model

Reused verbatim from the (now-external) `code-reviewer` plugin's `SKILL.md` — same five tiers (`tier-1` directly
observed and mechanically verifiable, down to `tier-5` speculative/needs-human), same downgrade
logic. Read that file's "Evidence Tier Model" section for the full definitions; this skill does
not restate them separately or diverge from them.

## Decision Model

Reused verbatim from `code-reviewer`'s five fields (`decision`, `severity`, `category`,
`workflow_action`, `confidence`) and their valid values. One reuse note: `category` has no
dedicated slot for this finding class in `code-reviewer`'s existing enum
(`correctness|security|test-coverage|style|architecture|performance|documentation`) — every
finding from this skill uses `category: documentation`, never a new invented value, so any
tooling that already reads `category` stays compatible.

## Auto-Fix Rule

For a finding with `confidence: high` that has a safe, mechanical fix (a stale docstring, a
dangling reference to a renamed file, a contradiction resolvable by matching one section to the
other's already-correct rule): apply the fix directly with `Edit`, then re-stage the file
(`git add <file>`) so it's reflected in the fingerprint computed at the end of this pass.
`confidence: medium` or `confidence: low` findings are **never** auto-applied — report only,
same as `code-reviewer`'s existing discipline. This mirrors exactly how Agent Responsibility
Cleanup's Phases 3-7 were actually carried out by hand.

## Visual Review — deliberate override of code-reviewer's threshold

`code-reviewer`'s rule (its `SKILL.md`'s "Visual Review" section — the canonical definition): open a review-dashboard Artifact above 5 findings or more than 1
touched file. This skill is *inherently* multi-file by design (see Scope above), so
applying that rule literally would make the dashboard Artifact the default rendering for every
single commit attempt — heavyweight for a background gate, not an interactive review session.

**Override: `ReportFindings` only, always, regardless of finding count or file count.** This is
a documented exception, not an oversight — a future audit pass (including this skill's own) that
flags this section should recognize it as an intentional, explained deviation, not a
contradiction to "fix."

## Write-Back Contract

After findings are gathered and high-confidence auto-fixes applied and re-staged:

1. Compute the fingerprint: `hooks/diff_fingerprint.compute(repo_root)`.
2. Resolve `${CLAUDE_PLUGIN_DATA}/sdd-memory/<project-slug>/` the same way every other component in this
   plugin does — via the session-announced path, or `hooks/sdd_memory.py --path` — never
   hand-computed (same discipline the `memory-orchestrator` slug bug taught the hard way).
3. Write `DOC-AUDIT-STATE.md` (`references/DOC-AUDIT-STATE.md.template`): `Status` is `passed`
   if no unresolved `confidence: high` finding remains, `needs_detailed_review` otherwise;
   `Diff Fingerprint` is step 1's result (or `none` if nothing was staged under the tracked
   paths); `Last Audited` is now.
4. Append one entry to `DOC-AUDIT-HISTORY.md` (`references/DOC-AUDIT-HISTORY.md.template`) —
   append-only, never edit or remove a prior entry.

These two files live at the **project level** (`${CLAUDE_PLUGIN_DATA}/sdd-memory/<project-slug>/`), not under
any `spec/<feature-slug>/` folder — `hooks/commit_audit_gate.py` must work whether or not an SDD
feature is currently active, so a feature-scoped marker (like `REVIEW-STATE.md`) doesn't fit
here.

## Output Shape

- One `ReportFindings` call with every finding from this pass (empty array if none survived).
- A one-line summary: files scanned, findings count by severity, auto-fixes applied, resulting
  `DOC-AUDIT-STATE.md` status.

## Guardrails

- Never open a review-dashboard Artifact — see Visual Review above.
- Never auto-fix a `confidence: medium` or `confidence: low` finding.
- Never write `DOC-AUDIT-STATE.md`/`DOC-AUDIT-HISTORY.md` anywhere other than the project-level
  memory directory resolved via `hooks/sdd_memory.py`.
- Never mark `Status: passed` while any `confidence: high` finding remains unresolved.
- Never invent a sixth finding class beyond the five in Scope without the user explicitly asking
  — scope creep here defeats the point of a narrowly-defined, repeatable check.
- Never auto-fix a class-5 (cross-plugin interop drift) finding by editing the *referenced*
  plugin's file to match the claim — only the file making the claim is safe to correct
  mechanically (update its own wording/value to match the referenced plugin's actual current
  state). Changing the other plugin's behavior to satisfy a stale claim about it is out of scope
  for this skill regardless of confidence.
