---
name: plan-reviewer
description: Fast, token-efficient verification of a design/plan doc before implementation — a scoped, tiered alternative to the built-in Plan subagent. Use to check a doc's claims against the actual codebase before committing to it. Trigger on "verify this design", "sanity-check my plan", "review this design doc", "poke holes in this design", or before writing design.md/tasks.md for independent grounding. NOT for open-ended "help me design X from scratch" — only verifies claims in an existing doc.
---

# Plan Reviewer

Independent, evidence-cited verification of a written design/plan document, without the cost and latency of the built-in `Plan` agent (which is a broad, open-ended architect agent that can run for 10s of minutes). This skill only ever verifies claims — it does not design.

## Why this exists

The built-in `Plan` subagent is general-purpose and open-scoped: given "review my design," it re-explores the whole codebase with a wide toolset, which is slow (observed: 10+ minutes) and token-heavy. Most design reviews only need a handful of factual claims checked ("does this function exist", "does X already handle Y", "is this the only caller"). This skill verifies exactly those claims, tiered by cost, and only pays for deeper investigation on the claims that actually turn out to be contested.

## Process

### Step 0 — Extract claims (you do this, no subagent)

Read the design/plan doc yourself. Pull out every **falsifiable factual claim** it rests on — not opinions or intent, but things that are true or false in the code right now. Examples: "`high_risk_reviewer.py` already parses tasks.md for Risk Tier", "no existing hook validates X", "`agent-TDD` cannot spawn subagents". Number them. Keep this list tight — 5-15 claims is typical; if you're finding 40+, the doc probably needs to be reviewed in sections.

Do not skip this step by dumping the whole doc on Tier 1 — the point of the skill is that Tier 1 verifies a short, explicit list, not that it re-reads the doc itself.

### Step 1 — Tier 1: quick verification (always runs)

Spawn `plan-reviewer-tier1` (Agent tool, `subagent_type: "plan-reviewer-tier1"`) with the numbered claim list. Read/Grep/Glob only, hard budget, fast. Returns a verdict per claim plus `escalate: true` on load-bearing claims that are `contradicted` or `uncertain`.

Run this in the foreground (`run_in_background: false`) if you're about to report back to the user immediately — it should be fast enough (single digit minutes) that this doesn't cost much; otherwise background it.

### Step 2 — Tier 2: boundary expansion (only for escalated findings)

For each Tier 1 finding with `escalate: true`, spawn a separate `plan-reviewer-tier2` agent — one per finding, not one call for all of them, so each stays scoped. Pass it: the original claim, Tier 1's verdict and evidence, and the design's stated intent for that claim. If Tier 1 escalated nothing, skip this step entirely — that's the common case and the whole point of the tiering.

If you have multiple escalated findings, spawn the Tier 2 agents in parallel (independent, no shared state).

### Step 3 — Tier 3: deep research (only for confirmed blockers)

For each Tier 2 result with `escalate_to_tier3: true`, spawn `plan-reviewer-tier3` — again one per finding, in parallel if there are several. This is the only tier with Bash access (git blame/log, call-graph tracing). Should be rare: most designs will never reach this tier.

### Step 4 — Report

Present results grouped by tier reached, most-severe first:

- **Blockers** (Tier 3 `confirmed_blocker`, or Tier 2 `contradicted` that didn't need Tier 3): must address before implementing.
- **Resolved concerns**: things that looked risky but were confirmed fine (Tier 2/3 `confirmed_non_issue`, or Tier 1 straightforward `confirmed`) — worth a one-line mention, not a full writeup.
- **Genuinely unresolved**: Tier 3 `genuinely_unresolved` — flag these explicitly as needing a human judgment call, don't guess.

Cite file:line evidence for every item, same as the subagents did — don't summarize away the evidence trail.

## Token-efficiency notes

- Never spawn Tier 2/3 speculatively "just in case" — only on explicit escalation from the tier below.
- Never re-run a tier on a claim it already resolved.
- If the whole claim list comes back `confirmed` from Tier 1, stop there and report — don't manufacture escalations to seem thorough.
