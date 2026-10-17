# Requirements Gate and Existing Ticket handling

Read by `spec-driven-development` when judging whether Requirements may advance (the Requirements Gate, EARS format) or when the user supplies an existing ticket, PRD or spec (verbatim from SKILL.md).

## Requirements Gate

Ready to advance only when: all required fields are present, expressed in EARS format, and no
unresolved ambiguity remains. Minimum content: problem statement, user outcome, constraints,
non-goals, edge cases, success criteria, dependencies.

If any of the above are weak, vague, or missing: refuse to advance, interview the user to fill
the weakest areas first, prioritizing the most ambiguous or highest-risk gaps. If ambiguity
remains after interviewing: stop, return the partial draft, return an explicit gaps list.

## Existing Ticket Or PRD Handling

When the user provides a ticket, PRD, or existing spec, `requirements-agent`'s review mode
handles it: review first, rewrite only the weak sections into EARS format, present the changed
draft, pause for confirmation, and only then treat it as the canonical requirements artifact.
Never treat incoming material as automatically sufficient for phase advancement.
