# Tiers

Choose the lowest tier that answers the user's stated decision. Each tier is a bounded loop: frame one claim, probe the smallest source, record observed / inferred / unverified, then stop or advance to the next framed claim.

## Tier 0: Locate

Canonical entry and immediate role. Result: location, role, immediate collaborator, evidence boundary.

## Tier 1: Implementation

How it works now. Result: trigger, control and data flow, effects, guards, failure paths, narrowest test. A test shows intended coverage, not execution.

## Tier 2: Consequence

Knock-on effects. Extend only from Tier 1 edges: callers, consumers, persistence, events, API contracts, flags. Result: dependent surfaces and the boundary for consumers you cannot see.

## Tier 3: Risk

Static, read-only risk candidates, not defect claims. For each: precondition, causal path, observed control or gap, status, smallest safe verification. No exploits, scanners or production probes.

## Tier 4: Architecture

Seams and options built on a verified Tier 1 and 2 map. Present alternatives with evidence, benefit, affected surfaces and trade-offs; owner approval is still required. Never a chosen design.

A named tier that would cross an unaccepted boundary (package, repository, history, external, runtime) is reported at the current boundary with the proposed crossing as the one next action.
