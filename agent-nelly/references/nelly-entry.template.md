<!--
Schema for a single Agent Nelly memory entry. This is the SAME frontmatter
shape Claude's own native per-topic memory-file convention uses — nothing
Nelly-specific about the frontmatter fields themselves.

Every file under `<project-slug>/entries/*.md` (and every entry inside
`global/GLOBAL-MEMORY.md`'s condensed index) follows this shape:

  - One file per entry, `.md` extension.
  - Filename == the `name` field (see hooks/nelly_memory.py `entry_path()`,
    which builds the path as `entries/<name>.md`, and `list_entries()`,
    which recovers the name by stripping the `.md` suffix from each
    filename in that directory).
  - `name` MUST be a kebab-case slug matching the filename exactly (no
    extension, no path separators — `entry_path()` sanitizes the name to a
    single path segment, so a mismatched `name` field would silently
    disagree with where the file actually lives).

Copy this file to `<project-slug>/entries/<name>.md`, fill in the
frontmatter and body, and delete this comment block.

New metadata fields (optional, type-conditional — only present for their
matching `type`; entries of other types MUST NOT include them):

  - `metadata.files` (type: file-relevance only): a YAML list of one or
    more paths, relative to the project's `cwd` — NEVER absolute, since a
    project can be checked out at different absolute paths across
    machines/worktrees.
  - `metadata.confidence` (type: error-prevention only): REQUIRED for this
    type, no default. `explicit` means a caller/user affirmatively flagged
    this as a reusable lesson. `inferred` means it was noticed unprompted
    and is permanently excluded from surfacing until separately confirmed.
  - `metadata.supersedes` (type: error-prevention only, optional): the
    `name` of an older, now-archived `error-prevention` entry this one
    replaces.
  - `metadata.error_type` / `metadata.source_plugin` / `metadata.target_plugin`
    (type: error-prevention only, all optional, all-or-nothing): structured
    match keys for an *orchestration-error workaround* entry — one written
    specifically to resolve a `plugin-harness` `known_issue` recovery
    lookup (see that plugin's `orchestrator/error_handler.py` and
    `hooks/resolve_nelly_request.py`). `error_type` uses
    `OrchestrationError.VALID_ERROR_TYPES`' vocabulary (`handoff_validation`,
    `plugin_unavailable`, `routing_failed`, `nelly_fetch_failed`, `interop_parse_failure`) —
    NOT `ErrorHandler`'s internal classification vocabulary
    (`contract_mismatch`, `known_issue`, etc.), since those are the terms a
    workaround-lookup query is actually phrased in. A consumer resolving a
    pending `workaround_lookup` request matches on these three fields
    exactly (never fuzzy/substring, unlike the topical relevance matching
    every other entry type uses) against `error-prevention` entries with
    `confidence: explicit`. Omit all three on an ordinary error-prevention
    lesson that isn't meant to auto-resolve an orchestrator lookup — a
    workaround match happens only when all three are present and equal.
-->

---
name: <short-kebab-case-slug>
description: <one-line summary used for relevance matching against a caller's task description>
metadata:
  type: <user | feedback | project | reference | file-relevance | error-prevention | technique | project-defined via types.yaml>
  last_referenced: <YYYY-MM-DD>
  # --- only present when type: file-relevance ---
  files: [<repo-relative path>, ...]      # one or more paths this entry is about
  # --- only present when type: error-prevention ---
  confidence: <explicit | inferred>        # REQUIRED for this type; no default
  supersedes: <name-of-older-entry|absent> # optional
  # --- only present when type: error-prevention AND this entry is an
  #     orchestration-error workaround (see comment block above); all three
  #     or none ---
  error_type: <handoff_validation | plugin_unavailable | routing_failed | nelly_fetch_failed | interop_parse_failure>
  source_plugin: <plugin name, e.g. agent-tdd>
  target_plugin: <plugin name, e.g. orchestrator>
  # --- only present when type: technique (corrected 2026-09-24 -- these
  #     entries are written directly by hooks/nelly_commit_extract.py,
  #     hooks/nelly_auto_extract.py, and hooks/nelly_session_end.py, never
  #     by an LLM agent; always confidence: inferred, no explicit variant ---
  confidence: inferred                     # REQUIRED for this type; always inferred, never explicit
  seen_count: <integer>                    # commit_extract/auto_extract only -- recurrence count
  family: <short label>                    # auto_extract only -- groups related recurring techniques
  passing_count: <integer>                 # auto_extract only -- times seen passing since first noted
  commit: <git commit hash>                # commit_extract only
  files_changed: <integer>                 # commit_extract (count) or session_end (count)
  paths: [<repo-relative path>, ...]       # commit_extract only
---

<The fact or detail this entry captures.

For `feedback` and `project` type entries, structure the body as:

Why: <why this matters / why it was learned this way>
How to apply: <concrete guidance for using this fact going forward>

For `file-relevance` type entries, structure the body as:

Why these files: <why this fact is tied to the listed files>
What the fact is: <the fact or detail itself>

For `error-prevention` type entries, structure the body as:

Failed approach: <what was tried>
Context: <when/where this applies>
Why it failed: <root cause>
How to avoid: <concrete guidance for next time>

For an orchestration-error workaround entry (carries `metadata.error_type` /
`source_plugin` / `target_plugin`), add one more line the resolver applies
verbatim as `ErrorHandler._handle_workaround`'s workaround dict:

Workaround action: <short action string, e.g. "retry_with_research_cache_populated">

Link related entries by their `name` field using `[[name]]` — e.g.
"see [[some-other-entry]]" — rather than restating shared context inline.>
