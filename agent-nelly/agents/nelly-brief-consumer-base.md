# Shared base: memory-brief consumer agents

This file holds constraints shared verbatim by `nelly-planning-agent.md` and
`nelly-research-agent.md`. It is not itself an agent — nothing invokes it
directly. Each consuming file links here instead of restating this content,
and carries only its own unique intro/body sections.

## Tool-restriction paragraph

`Read`/`Bash` are granted only for the caller's own target project files (e.g.
reading a file the caller names, running a project-local command) — never for
reaching Agent Nelly's memory store. This restriction is enforced by this
agent's own explicit refusal (below), not by a tool-level block: `hooks/hooks.json`'s
`PreToolUse` guard only matches `Write`/`Edit`/`MultiEdit`, so `Read`/`Bash`
are not path-restricted at the hook level for this agent. No `Grep`/`Glob`
scoped there is granted at all, but `Read`/`Bash` alone could technically
resolve a path under `~/.claude/agent-nelly-memory/**` if this agent's own
refusal below were ignored — so the refusal clause is load-bearing, not
decorative.

## How this agent receives memory

This agent can never call `nelly-orchestrator` itself — subagents cannot call
other subagents in this harness. Per the caller-orchestrated two-hop chain:

1. The caller invokes `nelly-orchestrator` first, on its own, to obtain a
   condensed memory brief for the current task.
2. The caller pastes that returned brief text verbatim into this agent's
   prompt as a `Memory brief:` block, alongside the stated task.
3. This agent reasons only over that pasted text — it never fetches, greps,
   or globs anything under the memory root itself.

If asked to read anything under `~/.claude/agent-nelly-memory/`, refuse and
say the caller must supply a brief instead.

## Insufficient memory

If the supplied brief's `Relevant entries` reads `none matched` / `none
requested this call` and there is no `File relevance:` sub-list, state that
plainly — e.g. "The supplied memory brief has no relevant entries for this
task; proceeding without memory-grounded output for this call." — rather than
inventing output content from assumed context. This mirrors
`nelly-orchestrator`'s own "never invent" invariant, applied here: an empty
brief produces an explicit insufficiency statement, never fabricated output
detail.

## Test-shape note

This agent's behavior is validated live, not by an automated test suite: see
`MANUAL-VALIDATION.md` Fixture Set O (two-hop subagent chain) for the runbook
— a live session invokes `nelly-orchestrator` for a brief, pastes it into this
agent's prompt, and confirms grounded output when the brief has content and an
explicit "insufficient memory" statement when it doesn't.
