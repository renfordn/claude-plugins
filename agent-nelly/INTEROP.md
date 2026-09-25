<!-- TDD-SKIP -->
# Interoperability: Integrating Agent Nelly Into Another Plugin

Agent Nelly is a general-purpose, project-aware memory plugin for Claude Code. It is not
specific to spec-driven-development (SDD) — SDD is simply its first real consumer, via
`agent-isdd`'s `spec-driven-development` skill's soft dependency on `agent-nelly` (see that
skill's Availability Check). **Corrected 2026-09-24**: this used to name `memory-orchestrator`,
a capability inside the old, single `spec-driven-development` plugin before it was split into
today's agent-isdd/agent-tdd/agent-nelly/code-reviewer — the name
doesn't resolve to anything in the current repo (see `agent-isdd/hooks/memory_slug_guard.py`'s
docstring for the historical "memory-orchestrator slug bug" this plugin's own
`doc-consistency-auditor` skill still references by that name — that's a historical incident
label, not a live component). This document is the contract for any *other* plugin author who
wants to use it too.

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
  - The hook is a pure, deterministic Python script. It **never invokes `agent-nelly`
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
ask `agent-nelly` for a brief when you want one.

## The one thing you actively do: ask `agent-nelly` for a brief

Everything else in this plugin (hooks, the `/nelly-memory` command) delegates to the
`agent-nelly` subagent — it's the one interface your plugin should call. Every request/response
shape documented in this file is `agent-nelly`'s; nothing here changes based on the internal
note below.

**Internal note, not part of this contract:** as of this writing, `agent-nelly` has a sibling
agent, `nelly-maintenance`, that owns three explicit, infrequent, user-invoked admin operations
(`/nelly-memory import`/`prune`/`consolidate`) that no consumer plugin has ever called and none
of the request fields below ever trigger. `agent-nelly` remains the sole thing any consumer
plugin talks to; `nelly-maintenance` exists purely so those three admin operations don't load
into every ordinary brief/fact-recording call's context. If this changes, this file's
consumer-facing contract is the thing to check — not which internal agent happens to implement
it.

**Request** (what you pass it):

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| cwd | string | yes | Your plugin's/skill's resolved project root |
| task description | string | yes | One line describing what you're currently doing |
| surface relevant memory | flag | no | Request proactive relevant-entry surfacing; never fires unless explicitly asked |
| new fact | string | no | One fact to record (mutually exclusive with `new facts`) |
| new facts | array/block | no | Multiple facts at once; near-duplicates merged into single entry |
| target files | array | no | List of repo-relative paths your task plausibly touches; only effective when `surface relevant memory` or `handoff surfacing` set; biases relevance judgment and adds `File relevance:` sub-list in response |
| error lesson | string | no | Lesson about failed approach to avoid; written as `error-prevention` entry with `metadata.confidence: explicit` |
| confirm error lesson | string | no | Name of existing `inferred`-confidence `error-prevention` entry to flip to `explicit` |
| file summaries | array | no | Write/overwrite one `file-summary` entry per item (see "File & Folder Summary Cache") |
| folder summaries | array | no | Write/overwrite one `folder-summary` entry per item (see "File & Folder Summary Cache") |
| file summary lookup | array | no | Repo-relative paths to check for a cached summary before searching the repo for them (read-only; see "File & Folder Summary Cache") |
| research digest | object/array | no | Store `{topic, summary, paths}` multi-file findings, keyed by topic + path set (see "Research Digest Cache") |
| research digest lookup | array | no | Repo-relative paths to find stored digests for, each `fresh` or `stale` with `changed` sources (read-only; see "Research Digest Cache") |
| handoff surfacing | flag | no | Enable surfacing at handoff points (see "Handoff points" section) |
| aside task description | string | no | Spinoff aside for potential separate conversation (see "Spinoff context bundles" section) |

**Response**:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| Intent | string | yes | Project-level goal and intent (per `agents/agent-nelly.md` contract) |
| Relevant entries | array | yes | Matching memory entries with content (never raw file contents; never marks "resolved"; never invents Intent) |
| Intent alignment | string | yes | Assessment of whether current task aligns with stored project Intent |
| Written | string/object | yes | Summary of any facts written during this call |
| Spinoff prompt | string | conditional | Self-contained context bundle if `aside task description` matched memory; omitted if no match |
| Spinoff tldr | string | conditional | One-to-two sentence summary if `aside task description` matched memory; omitted if no match |

See `agents/agent-nelly.md` for full contract details.

## Handoff points

If your plugin has its own orchestrator, workflow-manager, or any notion of phase/agent
transitions (an SDD-style workflow-manager is one example, but this applies to any calling
skill with a similar structure), it is expected to call `agent-nelly` with
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

## File & Folder Summary Cache

A cheaper alternative to grepping the whole repo for a targeted change: before reading/searching
a part of the repo your task touches, ask `agent-nelly` whether a summary of it is already
cached; after reading a file or forming a view of a folder's purpose, hand the summary back so
the next caller's lookup is a hit.

**Read, before you search:** pass `file summary lookup` with the repo-relative paths you're about
to look at. For each path the response reports one of:
- **Cache hit** — an existing `file-summary`'s `description` (≤240 chars) and `git_hash`. Compare
  `git_hash` against the file's current content hash yourself (`agent-nelly` never shells out to
  git for this) — a mismatch means treat it as a miss.
- **Partial hit** — no file-level summary, but the nearest ancestor `folder-summary`'s
  `description` as coarser context. Folder summaries carry no `git_hash`; don't treat one as
  guaranteed current.
- **Cache miss** — nothing cached; fall back to reading/searching the path directly.

**Write, after you read:** pass `file summaries` (list of `{path, summary, exports, constraints,
dependencies, tech_debt, git_hash}`) and/or `folder summaries` (list of `{folder, summary}`) for
anything you read that wasn't a fresh cache hit. `summary` is your own one-line "what this
does" text — `agent-nelly` truncates it to 240 characters if you don't already fit, and denies
the underlying write outright past that (`hooks/nelly_summary_guard.py`) if it somehow lands on
disk over-length. A later write for the same path/folder overwrites the earlier one; there is at
most one summary entry per path.

This capability has no phase/handoff concept of its own — call it from wherever your plugin
already reads files for a targeted change (a design/research pass, a task-slicing pass, or any
other file-driven step), independent of `surface relevant memory`/`handoff surfacing` above.

## Research Digest Cache

The multi-file counterpart of the summary cache above: a subagent's findings across several files,
kept until any of those files changes.

**Read, before you research:** pass `research digest lookup` with the repo-relative paths your
task touches. For each path, the response lists every digest whose sources include it, each with
`status` `fresh` or `stale`, `changed` (the sources that changed or were deleted, empty when fresh),
`topic`, `updated`, and the stored `summary`. A `source` field says whether the answer came from
the index or a directory scan; results are the same either way. For a `fresh` digest, use the
`summary` as known context. For a `stale` one, re-read only the `changed` files.

**Write, after you research:** pass `research digest` with `{topic, summary, paths}`:
- `topic`: a short label for what was researched; the same `topic` and path set overwrites the
  earlier digest instead of adding one.
- `summary`: your findings, capped at 2,000 characters (truncated at a line boundary with a
  marker if longer).
- `paths`: the repo-relative source files the findings came from, at most 30. Split larger
  research into several digests (e.g. one per top-level directory).

`agent-nelly` hashes the source files itself (git-blob SHA-1 of the working tree, no `git` needed).
A request with an absolute or `..` path, more than 30 paths, an empty topic or summary, or a
source file that doesn't exist is rejected and nothing is stored. As with every other field, a
failed or unavailable call is never a reason to block your own work.

## Spinoff context bundles

Pass `aside task description` when you believe part of the current work is an "aside" worth
potentially spinning off into its own conversation (e.g. via `mcp__ccd_session__spawn_task`).
`agent-nelly` runs the same relevance judgment used for `Relevant entries`/
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

**`agent-nelly` never calls `spawn_task` itself.** It only ever returns the
`Spinoff prompt:`/`Spinoff tldr:` strings; your plugin decides whether and how to invoke
`spawn_task` (or any other spinoff mechanism) with that bundle.

## Handoff targets for memory-grounded planning/research

Two subagents, `nelly-planning-agent` and `nelly-research-agent`, are available if you want a
memory-grounded plan outline or research/handoff summary rather than raw brief text. Both follow
a two-hop, caller-orchestrated pattern: your orchestrator calls `agent-nelly` first (as
above) to get a brief, then pastes that brief verbatim into a `Memory brief:` block in the
subagent's prompt alongside a stated task. Neither subagent calls `agent-nelly` itself or
reads/writes anything under the memory root directly — see `agents/nelly-planning-agent.md` and
`agents/nelly-research-agent.md` for their full contracts.

**Known cost:** if your task needs both subagents, you pay the brief's full input-token cost
twice. This harness has no subagent-to-subagent calling — a subagent can't call another subagent
— so your orchestrator must paste the same `agent-nelly` brief text into each subagent's
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
`${CLAUDE_PLUGIN_DATA}/agent-nelly-memory/<project-slug>/`) is unrelated to a "feature slug" as used by
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
`/nelly-memory` and `agent-nelly` work standalone in any project, with or without SDD
(or any other plugin) installed. Conversely, installing Agent Nelly never breaks a project that
doesn't use it — its `SessionStart` hook has no effect beyond an informational context string,
and its `PreToolUse` guardrails only ever apply to writes underneath its own memory root.

## Structured lookups for a consumer that can't call agent-nelly at all

Everything above assumes your consumer can invoke the `agent-nelly` subagent (via the
`Agent` tool) whenever it wants a brief. Some consumers can't: a Claude Code hook (`PreToolUse`,
`SubagentStop`, etc.) is a blocking subprocess with no `Agent`-tool access, so code running
inside one can never call `agent-nelly` directly, no matter how it's invoked.

The resolution pattern for a hook-bound consumer:

1. The hook enqueues a request (its own pending-queue, not part of this plugin) and surfaces it
   to the user/main session via whatever the hook contract allows (a `systemMessage` for
   `SubagentStop`, injected prompt context for `PreToolUse`).
2. The **main session** — which does have `Agent`-tool access — notices the surfaced request,
   calls `agent-nelly` for a real answer (exactly as described above), and writes the
   result back into the consumer's own state via whatever mechanism the consumer provides.
3. The consumer's *next* hook invocation reads the now-resolved result from its own state.

Agent Nelly's part of this is unchanged — it still only ever answers `agent-nelly` calls
and writes/reads its own memory files; it has no awareness of any consumer's pending-request
queue or resolution mechanism. The one piece specific to this pattern that Agent Nelly does own
is matching semantics for a **workaround-shaped `error-prevention` entry**: one written to
resolve exactly this kind of structured lookup, as opposed to an ordinary topical
`error-prevention` lesson. See `references/nelly-entry.template.md`'s `error_type` /
`source_plugin` / `target_plugin` metadata fields (error-prevention only, all-or-nothing,
optional) — when a caller's lookup query supplies these three values, match `explicit`-confidence
`error-prevention` entries **exactly** on all three (never the fuzzy/substring topical matching
used for `Relevant entries`/`File relevance:`/error-pattern surfacing elsewhere), and read the
matched entry's `Workaround action:` body line as the answer to hand back to the caller.

## Worked example

For a concrete, illustrative (not wired-up) walkthrough of a structurally different consumer —
a personal-assistant plugin with independent skills and no workflow-phase concept at all —
integrating against this contract, see
[`references/example-consumer-pa-jay.md`](references/example-consumer-pa-jay.md).

## Review follow-ups (from agent-isdd)

agent-isdd's SessionStart may pass code-reviewer follow-ups (refactor / consolidation / deferred
defect) as a `new facts` batch labelled `Source: code-reviewer follow-up <path>`. Record each as a
`file-relevance` entry over its files, noting the source file's `status:` decides whether it is
still open, so editing those files later surfaces it (with the 🧠 marker).
