---
name: bug-investigation
description: >-
  Diagnose a defect from its symptom: "why is this broken", "X fails since...", "error in production", failing test. Read-only; never fixes. Not for reviewing a change (code-reviewer) or code research (feature-finder).
argument-hint: [symptom, error, or failing test]
---

# Bug Investigation

Investigate, don't fix:

$ARGUMENTS

Runs in the main thread. You gather the brief, delegate the testing, and report. You never fix:
a requested fix goes to `/tdd` or the `agent-tdd` agent. This is not a code review.
There are no review findings, no findings payload and no review-report marker.

## 1. Intake

Record the **symptom**, **expected behavior**, **environment**, **time window** (with timezone),
and the intended **outcome** (explanation, root cause, or next step). Take what the user already
gave; ask one focused question only when a missing fact blocks the next step, otherwise proceed
with a bounded first check.

## 2. Investigate

Spawn `code-reviewer:bug-investigator` with the brief. It runs at most 3 read-only passes and
returns a `<!--BUG-INVESTIGATION-REPORT-->` with competing hypotheses, evidence and
counterevidence.

## 3. Challenge the leading hypothesis

Hypotheses carry ids `H1`, `H2`, ... Send only the leading hypothesis to
`code-reviewer:finding-verifier`, in **Hypotheses** mode; never send other hypotheses. The brief
has the shape of a finding: `id` (the hypothesis id, e.g. `H1`), `summary`, `failure_scenario`,
`tier` (`file`/`line` optional), plus the evidence and counterevidence so far. Map the label to
the tier: observed and reproduced -> tier-1, observed -> tier-2, inferred -> tier-3,
associated -> tier-4, unverified -> tier-5.

## 4. Verdict

Report the root cause as **confirmed** only if the verifier upholds it AND there is a verified
mechanism plus a reproduction or before/after proof. An upheld claim without that proof, or a
downgraded one, is a **candidate**: say what would confirm it. If the verifier refutes the
leading hypothesis, report it as **refuted** with the verifier's counterevidence. The next
action then becomes the discriminating check of the next-ranked hypothesis. Re-spawning the
investigator for that check counts toward the 3-pass limit. Temporal overlap is not causation.

## 5. Report

The first line of the report is exactly
`<!--BUG-INVESTIGATION-REPORT-->`
Then:

- competing hypotheses, each with evidence and counterevidence;
- the leading hypothesis and the verifier's outcome;
- confirmed or candidate, with confidence;
- one next action with an owner and a verification condition;
- for a blocker instead: the smallest missing input, and a fallback.

Keep the access status of each source the agent reported. If the user wants the fix, hand it to
`/tdd` or `agent-tdd` with the confirmed cause, and do not edit anything yourself.
