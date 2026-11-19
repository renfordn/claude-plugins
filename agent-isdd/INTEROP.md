# Interop: agent-isdd

This plugin owns Requirements → Design → Tasks only. It hands off to three sibling plugins
rather than owning their work. This document is the authoritative description of each boundary,
for both agent-isdd's own maintainers and the sibling plugins' maintainers to cross-check.

> Origin: this file began as a skeleton in Phase 1 of the `agent-isdd` scope refactor and has
> since been finalized. The refactor's requirements/design/tasks live in the author's local SDD
> memory (machine-local, not in this repo).


## → agent-tdd (implementation, Phase 2+3 revised)

At the end of Design, once Design is approved and implementation is requested, `agent-isdd` builds a
**Design Spec** (requirements_md, design_md, research_cache incl. the per-repo line-count ceiling
`{value, source}`, recap_md; optional file_summaries) and spawns `agent-tdd`. `Track: Standard` always
sends `Parallel: on` and, on the wave plan, acts as the `agent-tdd:tdd-parallel` lead; `Track: Fast`
stays serial. Implementation Mode (`agent`/`user`) is asked before the spawn.

Full contract (Design Spec field table, Test-Author Gate, Code-Review Gate, Design Spec completeness
gate and approval hash, availability check, Direct Implementation fallback, Parallel handoff):
[`references/interop-agent-tdd.md`](references/interop-agent-tdd.md).

## ← agent-tdd / code-reviewer, → code-reviewer, Strategic Review Placement

Rollback request markers (`rollback_pending`, `SDD-ROLLBACK-REQUEST`), the review gate, review
follow-ups, Strategic Review Placement, Ralph Loops integration, Auto-Detection Rules and review
tracking: [`references/interop-reviewers.md`](references/interop-reviewers.md).

## Moved sections (index for older citations)

Sections other docs cite as "`INTEROP.md`'s …" now live in the split references:

- **`references/interop-agent-tdd.md`**:
  - "Fallback — Direct Implementation (harness `Agent`-spawn failure)" (its Detection conditions)
  - Design Spec fields, including the `file_summaries` field description
  - "Exception — Test-Author Gate"
  - "Exception — Code-Review Gate"
  - "Design Spec completeness gate"
  - "Agent-tdd Design Spec workflow (pointer)"
  - "Parallel handoff"
- **`references/interop-reviewers.md`**:
  - "← agent-tdd / code-reviewer (rollback request)"
  - "→ code-reviewer (review gate)"
  - "Strategic Review Placement via Review Levels"
  - "Review tracking and user-run commands"

## → agent-ux (removed)

agent-ux was retired. The calling skills now make its `mark_chapter`/`Artifact` calls directly,
per `references/ux-conventions.md` (which has the rationale).

## → agent-nelly (memory)

Before starting or continuing meaningful phase work, `agent-isdd` delegates to
`agent-nelly:agent-nelly` for a goal-aware brief — nelly's four output sections are
`Intent`, `Relevant entries`, `Intent alignment`, and `Written`; agent-isdd uses `Intent` to
seed/check the feature's `Goal` field, and `Intent alignment` as the divergence signal — rather
than reading `${CLAUDE_PLUGIN_DATA}/sdd-memory/` cross-feature index files directly. If `agent-nelly` is
unavailable, agent-isdd surfaces one plain notice and continues without the Intent-alignment
check — never a hard dependency.

agent-isdd still owns writing its own per-feature `spec/` artifacts
(`workflow-state.md`/`.json`, `requirements.md`, `design.md`, `tasks.md`, `recap.md`) under
`${CLAUDE_PLUGIN_DATA}/sdd-memory/<project-slug>/spec/<feature-slug>/` directly — that scaffolding
(`hooks/sdd_memory.py`) is not part of what `agent-nelly` owns.

Within a continuous stretch of phase work, agent-isdd does not re-call
`agent-nelly:agent-nelly` on every step once a brief has already been fetched and is
still visible in context — it reuses the in-session brief instead. The full re-fetch-trigger
convention lives in `skills/spec-driven-development/SKILL.md`'s Goal-Aware Memory section (this
is a documentation pointer, not a duplicate definition). `workflow-state.json` is intentionally
unchanged by this dedup convention — it carries no brief-caching field.

**Write-back during spec phases**: at each `after-*` hook (`after-requirements`,
`after-design`, `after-tasks`), when `agent_nelly_available` is `true`, agent-isdd calls
`agent-nelly:agent-nelly` with a `new facts` batch containing any project-level
discoveries worth persisting across future sessions — for example: interface assumptions
confirmed or denied during requirements, coverage gaps or unexpected interfaces found during
design research, risk flags raised. The criterion is "would a future conversation benefit from
knowing this independently of this feature's own artifacts?" — ephemeral workflow state (user
confirmed step N, phase advanced) never qualifies. Choose the call shape by content: a positive
discovery (a confirmed interface, a constraint, a risk) is a `new fact`/`new facts` batch; a
discovery that a specific approach was tried and rejected is an `error lesson` instead. If the
call fails or nelly is unavailable, log a one-line note in `recap.md` and continue — it is never
a blocking condition.

**[Phase 2+3, corrected 2026-09-24] File & Folder Summary Cache**: this used to describe a
`type: "file_summary"` `new facts` batch item and a per-file JSON cache under
`.../agent-nelly-memory/<project>/files/<slug>.json` — neither of those existed in agent-nelly;
they were this document getting ahead of an integration that was never actually built. The real
contract, now implemented on both sides:

`research-consolidator`'s own "File Summaries" output (`research/cache.md`, the full in-context
shape, per its own agent spec) carries more than what gets persisted to agent-nelly:

```json
{
  "path": "src/api/client.ts",
  "summary": "HTTP client wrapper with retry logic",
  "exports": ["class ApiClient { request() }", "function retry<T>(...)"],
  "constraints": ["Singleton: initialized once", "Not re-entrant"],
  "tech_debt": ["Retry backoff hardcoded"],
  "dependencies": ["axios", "events"],
  "test_surface": ["Mock ApiClient.request()", "Test retry behavior"],
  "migration_risks": ["Request state cached; changes to error handling must clear cache"],
  "line_count": 342,
  "git_hash": "abc123def456"
}
```

After `research-consolidator` completes during Design phase, `design-author` persists a trimmed
version of that same output to agent-nelly's dedicated `file summaries` request field (one
`file-summary` entry per path, under that project's ordinary `entries/` store — not a separate
JSON cache), and one `folder summaries` item per directory containing several touched files.
`test_surface`, `migration_risks`, and `line_count` stay in `research/cache.md` for `agent-tdd`'s
own use — they don't ride along to agent-nelly, since the summary cache exists to answer "what
does this file do," not to duplicate the line-count-ceiling gate or task-slicing inputs. Schema
per persisted file-summary item:

```json
{
  "path": "src/api/client.ts",
  "summary": "HTTP client wrapper with retry logic",
  "exports": ["class ApiClient { request() }", "function retry<T>(...)"],
  "constraints": ["Singleton: initialized once", "Not re-entrant"],
  "tech_debt": ["Retry backoff hardcoded"],
  "dependencies": ["axios", "events"],
  "git_hash": "abc123def456"
}
```

`summary` is capped at 240 characters (`agent-nelly`'s `nelly_memory.SUMMARY_CHAR_LIMIT`,
structurally enforced by its `nelly_summary_guard.py` hook) — there is no `line_count`,
`test_surface`, `migration_risks`, or `touched_by` field in the real entry (those stayed useful as
in-context research findings for `design.md`/`research/cache.md`, just not as part of what gets
persisted to agent-nelly). A folder-summary item is just `{"folder": "src/api", "summary": "..."}`.

When `agent-isdd` needs file context during a later feature (Design phase — see
`design-author/SKILL.md`'s "Research First" step 1 — or `agent-tdd` slicing, per this file's
`file_summaries` field description above), it queries agent-nelly's `file summary lookup` field
by path; agent-nelly returns a cache hit (`description` + `git_hash`), a folder-level partial hit,
or a miss — see `agent-nelly/agents/agent-nelly.md`'s "File & Folder Summary Cache" section for
the full read/write contract and `agent-nelly/INTEROP.md`'s section of the same name for the
consumer-facing summary. `git_hash` validity is always checked by the *caller* (`git hash-object
<path>` against the stored value) — agent-nelly itself never shells out to git.

**[Research Digest Cache]** Alongside file summaries, `design-author` stores
`research-consolidator`'s multi-file findings as agent-nelly `research digest` items and checks
them before the next research pass. Request schema per item (agent-nelly's own `INTEROP.md`
"Research Digest Cache" section is authoritative):

```json
{
  "topic": "nelly-research-digest-cache: index rescan",
  "summary": "Multi-file findings, at most 2,000 characters (agent-nelly truncates longer text)",
  "paths": ["agent-nelly/scripts/build_index.py", "agent-nelly/hooks/nelly_memory.py"]
}
```

`paths` are repo-relative, at most 30 per digest (split by top-level directory beyond that).
Same `topic` + path set overwrites the earlier digest. Agent-nelly hashes the sources itself, so
there is no `git_hash` field. `research digest lookup` (a list of repo-relative paths) returns
each covering digest as `fresh`, or `stale` with `changed` paths; see `design-author/SKILL.md`'s
"Research First" steps 1 and 2 for how both results are used.

Agent-nelly's file cache is optional and transparent to agent-isdd: if unavailable, agent-isdd
continues without pre-loaded file context (slower, but correct). This is documented here as the
contract both plugins can cross-check; agent-nelly's own `INTEROP.md` is authoritative for its
side of the contract.

## → agent-cache-plugin (removed)

agent-cache-plugin was removed from the collection: its hooks read camelCase fields Claude Code
never sends, so it never stored or served anything. agent-isdd never exchanged data with it.

---

## → Plan Board (Artifact page)

agent-isdd keeps an optional living Artifact page, the Plan Board, current as workflows move. A
project opts in by recording the page URL in `PLAN-BOARD.md` in its SDD memory directory. Each
feature is one record in the page's `plans` collection, built by `hooks/plan_board.py doc` from
`workflow-state.md` plus a script-built brief from its sibling state files (`hooks/plan_brief.py`;
fields are listed in the reference below). The post-write hook rebuilds the record on every write to
a state file and, when its hash changed, reminds the model to write it (a hook can't call the
Artifact tools); `SessionStart` is the backstop that lists out-of-date features, and
`/isdd-board-sync` (`hooks/plan_board_sync.py`) verifies, resyncs and prunes in bulk. Nothing else in the plugin depends on the board. See
`skills/workflow-manager/references/plan-board.md`.

