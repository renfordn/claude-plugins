# Handoff surfacing

Read by `agent-nelly` when the caller passes the `handoff surfacing` flag (narrower mode, restricted entry types). Text moved verbatim from agent-nelly.md.

### Handoff surfacing (narrower mode, restricted entry types)

When the caller passes `handoff surfacing` for this call — whether alone or
together with `surface relevant memory` — surfacing still runs exactly as
steps 1-6 above describe, with one additional restriction layered on top:
the only entries eligible to appear in `Relevant entries` or the
`File relevance:` sub-list are:

- **`file-relevance`-typed entries**, matched exactly as step 5 above
  already does — same plausibility-matching rule, same gate on whether
  `target files` was also passed for this call (no `target files`, no
  `File relevance:` output; this is unchanged by `handoff surfacing`).
- **`error-prevention`-typed entries whose `metadata.confidence` is
  `explicit`** — never `inferred`, under any circumstance. The
  inferred-confidence exclusion gate (Step 6) applies here without
  modification. `handoff surfacing` is, if
  anything, stricter than the gate alone: it also fully excludes every
  `user`, `feedback`, `project`, and `reference` entry — and any other
  entry type — even when one would otherwise topically match the task
  description under steps 1-2's plain matching. This is the "narrower"
  half of "a narrower version of `Relevant entries`": fewer eligible entry
  types, not a different or looser confidence rule.

How `handoff surfacing` combines with `surface relevant memory`:

- `handoff surfacing` passed alone (no `surface relevant memory`):
  surfacing still runs in full — do not treat `handoff surfacing` as
  requiring `surface relevant memory` to also be set. It is a complete,
  independent request restricted to the two entry types above.
- `handoff surfacing` passed together with `surface relevant memory`: the
  narrower two-type restriction wins for this call. Do not fall back to
  the broader `surface relevant memory` scope just because both flags were
  passed — there is no combination of inputs under which a
  `user`/`feedback`/`project`/`reference` entry, or an `inferred`-
  confidence `error-prevention` entry, ever appears in this call's output.

If nothing matches under this narrower scope, state `Relevant entries:
none matched this task` exactly as step 4 above already does for the
broader scope — no separate wording is needed for `handoff surfacing`.
Step 3's `metadata.last_referenced` update still applies, unchanged, to
any entry actually surfaced this way.

Graceful-degradation obligation: as stated in the Inputs list above — treat
a failed/unreachable call as an empty brief, never block or retry-loop.
