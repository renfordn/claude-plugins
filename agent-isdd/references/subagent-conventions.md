# Subagent Conventions

House conventions that apply across this plugin's subagents (`agents/`), documented once here
rather than re-derived or re-explained inline wherever they apply.

## "Excluded — and why"

**What candidate-file triage is**: a subagent evaluates more candidate files/modules than it
actually deep-reads — a fast wide pass to surface candidates, followed by a narrower, focused
read of only the ones that matter.

**Why this matters**: padding a report with every candidate considered, including the ones that
turned out irrelevant, costs tokens without adding signal for the caller. The reverse failure —
silently dropping a candidate with no trace — hides that it was ever considered, which makes a
caller unable to tell "not relevant" apart from "not looked at."

**The convention**: any subagent that performs candidate-file triage includes an explicit
`Excluded — and why` section in its return contract, naming which candidates it deliberately did
not deep-read and the one-line reason. This keeps the caller's report proportional to what was
actually load-bearing, while still making the triage decision auditable.

**Worked example**: `agents/planning-agent.md`'s Pass 1 (wide, fast) / Pass 2 (deep, focused)
structure is the canonical, already-compliant example — see its "Return this to the caller"
section's `Excluded` bullet. A future subagent that performs the same kind of triage should
follow the same shape rather than inventing a new report structure.

**Confirmed non-applicable today** (re-check this premise before retrofitting, don't assume it
still holds without looking): `spec-reviewer` reviews one caller-given document, not a candidate
set, so it has nothing to triage. `tdd-planner` defers codebase research to `planning-agent`
rather than surveying files itself, so it also does no candidate-file triage of its own.
