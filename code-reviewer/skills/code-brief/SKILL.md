---
name: code-brief
description: Explain how existing code works as a visual Artifact — structure and/or timeline diagrams plus a narrative walkthrough — for a person building understanding. Use whenever the user asks to explain, visualize, diagram, or walk through how code, a feature, or a subsystem works. Not a code review — for reviewing a change, use the code-reviewer skill.
argument-hint: [file, feature, or subsystem to explain]
---

# Code Brief

Explain, don't review:

$ARGUMENTS

If no scope was given, ask one question (what to explain) rather than guessing at a subsystem.

This answers "how does this work?", not "should this change be accepted?". The intended reader
is a person, not an agent resuming work, so nothing is handed back to a workflow.

## Depth

Match investigation depth to the scope: a fast orientation for one file or function; a full
deep-dive for a whole subsystem. If the user names a `review_level` (`Quick` | `Standard` |
`Deep` | `Ultra`), treat it as that depth dial.

## Evidence tiers still apply

A brief that states something with unearned confidence is worse than no brief at all. Ground
every claim in one tier:

- **tier-1** — read the exact code path, or ran it, and it's mechanically verifiable.
- **tier-2** — read it directly; light reasoning, no assumptions about unread code.
- **tier-3** — inferred from a partial view; depends on code not inspected.
- **tier-4** — pattern or convention based; not reproduced.
- **tier-5** — speculative; can't be verified with the tools at hand.

Never state a claim above tier-2 without direct evidence. Fold anything at tier-3 or lower into
*Unverified areas* instead of smoothing it into confident prose.

## Output

Build one Artifact (load `artifact-design` for the page contract, `artifact-diagramming` for the
diagram mechanics, and `frontend-design` for the visual design pass before writing it) with:

1. **Overview** — two or three sentences: what this subsystem/feature does and why it's shaped
   the way it is.
2. **Diagram(s)** — pick whichever the material actually calls for:
   - A **structure diagram** (components/modules and how they call or depend on each other) when
     the interesting thing is *what talks to what*.
   - A **timeline / sequence diagram** (steps in order) when the interesting thing is *what
     happens when* — a request lifecycle, a startup sequence, a state machine's transitions.
   - Both, as separate diagrams, when the research covers both a structure and a process — don't
     force one diagram to carry two kinds of information it can't legibly hold at once.
3. **Walkthrough** — prose tied to the diagram, in the same order the diagram reads, not a
   restatement of it: the diagram shows the shape, the walkthrough explains the *why* at each
   step (a design constraint, a non-obvious dependency, a workaround).
4. **Unverified areas** — anything grounded at tier-3 or lower, named plainly as inferred. A
   reader trusting a diagram needs to know which parts of it to double-check themselves.

**Design bar**: a generic-looking diagram defeats the purpose as surely as a wrong one. Run
`frontend-design`'s plan-then-build pass: ground palette, type, and diagram style in the
subsystem's own vernacular (a queueing pipeline, a UI component tree, and a crypto handshake
should not produce the same-looking boxes-and-arrows), and avoid the tells `frontend-design`
calls out — generic SaaS-card chrome, tracked-out ALL-CAPS eyebrows, a monospace face for labels
just because they're technical, uniform drop-shadows and border-radius applied regardless of
hierarchy. One diagram idiom deliberately chosen for this subsystem beats a default flowchart
template reused across every brief.

**Ownership**: this skill owns the Artifact directly — no `agent-ux` dependency. Diagrams are
outside `agent-ux`'s scope (it renders progress/findings state, not explanatory visuals).

## Guardrails

- No review output: no `ReportFindings` call, and no `decision`, `severity`, `category`,
  `workflow_action`, or `confidence` fields anywhere.
- Write nothing to `REVIEW-STATE.md`, `REVIEW-HISTORY.md`, or `TODO-LEDGER.md` — there is no
  decision or outstanding fix to persist.
- Never state a claim above tier-2 without direct evidence.
