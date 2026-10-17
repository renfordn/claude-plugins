# Subagent Delegation

Read by `spec-driven-development` when delegating to `spec-reviewer`, `research-consolidator` or `agent-nelly:agent-nelly` (roles and delegation rules; text is verbatim).

Three capabilities are delegated to **subagents** (two in this plugin's `agents/`, one external) so their bounded work runs in an isolated
context and returns only a conclusion, keeping this orchestrator thread lean across a long
workflow:

- `spec-reviewer` — delegate when `requirements-agent` needs to assess an existing draft before
  rewriting it.
- **[Phase 2+3]** `research-consolidator` — delegate during Design to produce unified research
  (design_findings, task_findings, file_summaries) in one pass, eliminating redundant research
  between design-author and agent-tdd. Replaces the prior separate planning-agent calls.
- `agent-nelly:agent-nelly` — an external peer-plugin subagent, not one of this plugin's
  own `agents/`, invoked the same way (via the `Agent` tool with that literal `subagent_type`
  string), gated by the Availability Check — delegate before any phase starts, when available,
  for a goal-aware brief (Intent, Relevant entries, Intent alignment, Written); it is
  the sole writer into agent-nelly's own memory store, which agent-isdd never reads or writes
  directly. **[Phase 2+3]** Also used to query and cache file summaries for cross-feature reuse.

Delegation rules:
- Prefer the subagent over inlining these when the task is well-scoped.
- Subagents cannot talk to the user. **You** own every user-facing confirmation checkpoint:
  take a subagent's returned report, surface it, get confirmation, then update
  `workflow-state.md` and `recap.md` yourself — per `workflow-manager`'s field-update contract
  (see its Lifecycle Hooks section), not a separate set of rules.
- `requirements-agent` and `design-author` stay inline for interviewing the user, but delegate
  their bounded sub-tasks (`spec-reviewer` for draft assessment; `research-consolidator` for
  research) to subagents rather than doing that work in the main thread.
