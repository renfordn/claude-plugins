---
name: feature-finder
description: >-
  Text answer on where code lives and how it works, read-only, claims tagged observed/inferred/unverified. For "where is X implemented", "how does X work", "what calls Y", "impact of changing Z". Not "why is this broken" or "any bugs?". Visual walkthroughs: code-brief.
context: fork
agent: Explore
argument-hint: "[question about existing code, optional memory hints]"
---

# Feature Finder

Answer one question about existing code with the smallest defensible evidence set:

$ARGUMENTS

Read-only. Explain and locate; never review, never claim a defect, never plan a change. Symptoms ("why is this broken") belong to `bug-investigation`; a diff or "any bugs?" belongs to `code-reviewer`.

## 1. Pick a lane

| Lane | Use for | Detail |
|---|---|---|
| Locate | where is a symbol, route, config key | `references/lanes.md` |
| Explain | how one bounded thing works | `references/lanes.md` |
| Trace | follow a call or data path | `references/lanes.md` |
| Impact | what depends on it, what a change touches | `references/lanes.md` |
| Research | cross-cutting question across modules | `references/lanes.md` |

Name the target and the question first. If the repo, entry point, or intended behavior is materially unclear, return the one focused question as the next action and stop (a forked skill cannot ask interactively); otherwise start with the smallest plausible scope.

## 2. Pick the lowest useful tier

Choose the lowest tier that answers the stated decision; a higher tier includes only the lower-tier foundation it needs. Tier 0 locate, Tier 1 implementation, Tier 2 consequence, Tier 3 risk candidates, Tier 4 architecture options. A bare "research" with no named outcome stops at Tier 0 or 1 and proposes the next tier. Details: `references/tiers.md`.

## 3. Evidence rules

- Confirm everything against the current checkout. Search for exact forms first (`rg -n -F`), read narrow windows, skip vendor, generated and lock files.
- Memory can aim searches, never serve as evidence. Memory hints come only from the caller's args; this skill never calls agent-nelly. A hint that the checkout does not confirm is reported as unverified, or as contradicted.
- Tests count as evidence of coverage or intent, not execution. Say a path runs only if you ran it.
- Static reading cannot show runtime behavior; label configuration, async, persistence and contract boundaries you did not observe as unverified.
- Tag every material claim: observed (read in the checkout, cited `file:line`), inferred (follows from observed facts, say from which), unverified (not checked; name the smallest check that would settle it).

## 4. Stop conditions

Stop when the tier's minimum result is observed, contradicted, or explicitly unverified; when the remaining probe cannot change the answer; or after one failed search retry. Do not retry the same search, scan unrelated directories, or read history.

No new boundary without the user's say-so (consent): crossing into another package or repository, history, external sources, or runtime evidence needs the user to name and accept it. Report the current result and propose the specific reads and stop condition instead.

## 5. Report

Begin with `<!--FEATURE-FINDER-REPORT-->`. Lead with the shortest complete answer, then a ledger:

| Claim | Evidence (`file:line`) | Status (observed / inferred / unverified) |
|---|---|---|

Prose for the causal path; a diagram only if several stages connect. End with exactly one next action, or `Investigation complete.`

## Guardrails

- Not a review: no `ReportFindings`, and none of the Decision Model fields (`decision`, `workflow_action`, `severity`, `evidence_tier`, `category`, `confidence`).
- No edits, no stateful commands, no tickets, no production access.
- A gap or oddity is not a defect unless the question and evidence establish it; if it looks like one, say so in the next action and route to `bug-investigation`.
- No review-state files written; no savings or speed claims.
