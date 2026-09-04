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
-->

---
name: <short-kebab-case-slug>
description: <one-line summary used for relevance matching against a caller's task description>
metadata:
  type: <user | feedback | project | reference | file-relevance | error-prevention | project-defined via types.yaml>
  last_referenced: <YYYY-MM-DD>
  # --- only present when type: file-relevance ---
  files: [<repo-relative path>, ...]      # one or more paths this entry is about
  # --- only present when type: error-prevention ---
  confidence: <explicit | inferred>        # REQUIRED for this type; no default
  supersedes: <name-of-older-entry|absent> # optional
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

Link related entries by their `name` field using `[[name]]` — e.g.
"see [[some-other-entry]]" — rather than restating shared context inline.>
