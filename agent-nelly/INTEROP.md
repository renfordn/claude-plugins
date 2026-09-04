<!-- TDD-SKIP -->
# Interoperability: Integrating Agent Nelly Into Another Plugin

Agent Nelly is a general-purpose, project-aware memory plugin for Claude Code. It is not
specific to spec-driven-development (SDD) — SDD is simply its first real consumer, via
`memory-orchestrator`'s soft dependency on `nelly-orchestrator`. This document is the contract
for any *other* plugin author who wants to use it too.

Nothing below requires SDD to be installed, and nothing below is specific to SDD's concepts
(feature slugs, workflow phases, TDD state). If you're looking for how SDD itself uses Agent
Nelly, that's an implementation detail of the SDD plugin, not part of this contract.

## What you get automatically, with zero setup

`hooks/hooks.json` wires Agent Nelly's `SessionStart` and `PreToolUse` hooks **at the plugin
level, on install** — not per-consumer. If Agent Nelly is installed in a Claude Code session,
every session in every project automatically gets:

- A `SessionStart` announcement of that project's memory root, its captured `Intent` (or a
  "not yet captured" placeholder), and a condensed list of stored entries.
- `PreToolUse` guardrails that auto-approve writes under the project's own memory directory and
  deny writes into another project's memory directory (path-shape checks only — see
  `hooks/nelly_slug_guard.py` / `hooks/nelly_memory_permission.py`).
- Automatic, unprompted tool-boundary surfacing: when a `Write`/`Edit`/`MultiEdit` targets a
  file path that a stored `file-relevance` or `error-prevention` entry names (via that entry's
  `paths:` index field), `hooks/nelly_proactive_surface.py` surfaces a one-line
  `permissionDecisionReason` nudge referencing that entry — with no flag, no explicit ask, and
  no per-consumer setup. This is the one place Agent Nelly deliberately breaks its own
  "never fires unprompted" default (see the next section), and it does so narrowly:
  - The hook is a pure, deterministic Python script. It **never invokes `nelly-orchestrator`
    or makes any `Agent`-tool call**, regardless of match strength — it can't (hooks are
    blocking subprocesses with no `Agent`-tool access) and it shouldn't (a full brief costs
    tens of thousands of tokens per call; forcing that onto an ordinary file edit isn't
    acceptable). Any full-brief follow-up is your own separate, later, ordinary call, made at
    your own discretion after seeing the nudge — exactly like reading `SessionStart`'s
    condensed context and deciding whether to look further.
  - An `error-prevention` entry only surfaces when its *entry file's real* `metadata.confidence`
    is `explicit` — an `inferred` (unconfirmed) lesson never surfaces via this path, and the
    index line's own mirrored `confidence:` field is never trusted for this decision, since it
    can drift stale relative to the entry file.
  - No match, an empty/missing memory store, or `NELLY_GATE=off` (and `0`/`false`/`disabled`)
    all produce the same silent no-op as the two existing `PreToolUse` hooks — empty stdout,
    exit 0, zero added tokens or latency.
  - Only file-path matching is supported today (`Write`/`Edit`/`MultiEdit`); command-text
    (`Bash`) matching and matching on a consuming plugin's own internal lifecycle/phase
    transitions are both explicitly out of scope for this mechanism.

**You do not need your own `hooks.json` entry, and you do not need to "opt in" to any of
this.** It is easy to wrongly assume a new consumer plugin needs its own hook wiring to
participate — it doesn't. The only thing your plugin needs to actively do is described below:
ask `nelly-orchestrator` for a brief when you want one.

## The one thing you actively do: ask `nelly-orchestrator` for a brief

Everything else in this plugin (hooks, the `/nelly-memory` command) delegates to the
`nelly-orchestrator` subagent — it is the sole owner of every file under the memory root, and
it's the one interface your plugin should call.

**Request** (what you pass it):

- `cwd` — your plugin's/skill's resolved project root.
- `task description` — one line describing what you're currently doing.
- `surface relevant memory` (optional flag) — pass this only when you explicitly want proactive
  relevant-entry surfacing for this call. It never fires unless you ask for it.
- `new fact` — one fact you want recorded this call (mutually exclusive with `new facts`).
- `new facts` — several facts at once, as a `New facts:` block; near-duplicates within the batch
  are merged into one entry rather than written N times.
- `target files` (optional) — a list of repo-relative paths your current task plausibly touches.
  Only has any effect when `surface relevant memory` (or `handoff surfacing`, below) is also set
  for the same call; it biases which entries are judged relevant and adds a `File relevance:`
  sub-list (see "Response" below) when a `file-relevance`-typed entry matches.
- `error lesson` (optional, raw text) — a lesson about a failed approach worth avoiding next
  time. Written as a new `error-prevention` entry with `metadata.confidence: explicit` before the
  promotion judgment runs. This is the primary capture path for error-prevention entries.
- `confirm error lesson: <name>` (optional) — flips one existing `inferred`-confidence
  `error-prevention` entry named `<name>` to `explicit`. This is the only mechanism by which an
  `inferred` entry ever becomes eligible for surfacing.
- `handoff surfacing` (optional flag) — see "Handoff points" below.
- `aside task description` (optional, text) — see "Spinoff context bundles" below.

**Response**: always the four sections defined in `agents/nelly-orchestrator.md`'s Outputs
block — `Intent`, `Relevant entries`, `Intent alignment`, `Written` — with the same invariants
(never a raw entry file's full contents, never marks anything "resolved," never invents an
Intent). Two conditional trailing lines (`Spinoff prompt:`/`Spinoff tldr:`) may follow `Written`
when you passed `aside task description` this call — see "Spinoff context bundles" below. See
`agents/nelly-orchestrator.md` for the full contract.

## Handoff points

If your plugin has its own orchestrator, workflow-manager, or any notion of phase/agent
transitions (an SDD-style workflow-manager is one example, but this applies to any calling
skill with a similar structure), it is expected to call `nelly-orchestrator` with
`handoff surfacing: true` **at its own existing transition points** — not at points Agent Nelly
invents or injects. Agent Nelly never surfaces memory automatically at a handoff; it stays a
per-call opt-in exactly like `surface relevant memory` already is.

`handoff surfacing` is a narrower alternative to `surface relevant memory`: when passed, the
only entries eligible for `Relevant entries` (and its `File relevance:` sub-list) are
`file-relevance`-typed entries and `error-prevention`-typed entries whose
`metadata.confidence` is `explicit` — never `inferred`, and never any `user`/`feedback`/
`project`/`reference` entry, even if it would otherwise topically match. Pass `target files`
alongside `handoff surfacing` to also get the `File relevance:` sub-list.

**Mandatory graceful-degradation clause (the authoritative consumer-facing contract statement):**
a brief call — with or without `handoff surfacing` — that fails, times out, or returns nothing
MUST be treated by the caller as an empty brief, never a reason to block, retry-loop, or fail the
caller's own handoff.

## Spinoff context bundles

Pass `aside task description` when you believe part of the current work is an "aside" worth
potentially spinning off into its own conversation (e.g. via `mcp__ccd_session__spawn_task`).
`nelly-orchestrator` runs the same relevance judgment used for `Relevant entries`/
`File relevance:`, but against this separate `aside task description` text rather than your
main `task description` — the two never share matches.

When it finds a match, the response's conditional trailing lines are:

- `Spinoff prompt:` — a condensed, self-contained bundle of the relevant facts and/or
  `file-relevance` paths found, worded to stand alone without this parent conversation (mirroring
  `spawn_task`'s own `prompt` requirement).
- `Spinoff tldr:` — one to two plain-English sentences (mirroring `spawn_task`'s `tldr`).

When nothing matches (including everything excluded by the `inferred`-confidence gate), it
returns exactly `Spinoff prompt: insufficient memory to construct a grounded context bundle for
this aside — proceed without one.`, with `Spinoff tldr:` correspondingly absent or stating the
same insufficiency — never a fabricated bundle.

**`nelly-orchestrator` never calls `spawn_task` itself.** It only ever returns the
`Spinoff prompt:`/`Spinoff tldr:` strings; your plugin decides whether and how to invoke
`spawn_task` (or any other spinoff mechanism) with that bundle.

## Handoff targets for memory-grounded planning/research

Two subagents, `nelly-planning-agent` and `nelly-research-agent`, are available if you want a
memory-grounded plan outline or research/handoff summary rather than raw brief text. Both follow
a two-hop, caller-orchestrated pattern: your orchestrator calls `nelly-orchestrator` first (as
above) to get a brief, then pastes that brief verbatim into a `Memory brief:` block in the
subagent's prompt alongside a stated task. Neither subagent calls `nelly-orchestrator` itself or
reads/writes anything under the memory root directly — see `agents/nelly-planning-agent.md` and
`agents/nelly-research-agent.md` for their full contracts.

**Known cost:** if your task needs both subagents, you pay the brief's full input-token cost
twice. This harness has no subagent-to-subagent calling — a subagent can't call another subagent
— so your orchestrator must paste the same `nelly-orchestrator` brief text into each subagent's
prompt separately; there is no way to fetch the brief once and share it across both calls. This
is a hard harness constraint, not a bug, and it is accepted rather than worked around (see the
`2026-08-10-agent-nelly-memory-orchestration-v2` feature's own design.md, Resolution 2, for where
this constraint was first confirmed). Before invoking both subagents for one task, decide whether
you actually need both outputs — if only one is relevant, call only that one and skip the second
brief-repaste entirely.

## Resolving your project's memory path

If you ever need the memory path directly (for logging, or to check something exists), resolve
it through the owning script — never hand-compute it:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/nelly_memory.py" --path [cwd]
```

This is the same discipline this project's own global memory already enforces for any
shared/derived filesystem path: resolve it through the one script that owns the computation,
never approximate it independently. `hooks/nelly_memory.py` also exposes `--global-path` (the
cross-project tier) and `--entries-path` (ensures `entries/` exists, idempotent).

## One terminology note: "slug"

This plugin's `project_slug()` (a deterministic hash of an absolute path, used to namespace
`~/.claude/agent-nelly-memory/<project-slug>/`) is unrelated to a "feature slug" as used by
spec-driven-development (a human-readable spec-folder name like `2026-08-10-my-feature`). They
share a word, not a concept — if you're integrating a plugin that also uses SDD, don't conflate
the two.

## Scope: one memory store per project, not per skill

Memory is scoped by `cwd` (project directory), not by which skill or command triggered the
call. If your plugin has several independent skills covering unrelated concerns, they all read
and write the same project-level memory store when given the same `cwd` — there is no
per-skill isolation built in. Structure your `new fact` entries so they make sense read
alongside facts from your plugin's other skills.

## Independence guarantee

Agent Nelly requires no other plugin to function, and no other plugin requires Agent Nelly.
`/nelly-memory` and `nelly-orchestrator` work standalone in any project, with or without SDD
(or any other plugin) installed. Conversely, installing Agent Nelly never breaks a project that
doesn't use it — its `SessionStart` hook has no effect beyond an informational context string,
and its `PreToolUse` guardrails only ever apply to writes underneath its own memory root.

## Worked example

For a concrete, illustrative (not wired-up) walkthrough of a structurally different consumer —
a personal-assistant plugin with independent skills and no workflow-phase concept at all —
integrating against this contract, see
[`references/example-consumer-pa-jay.md`](references/example-consumer-pa-jay.md).
