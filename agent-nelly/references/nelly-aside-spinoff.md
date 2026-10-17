# Aside-spinoff context bundle

Read by `agent-nelly` when the caller passes the `aside spinoff` flag (context bundle for a spun-off aside). Text moved verbatim from agent-nelly.md.

### Aside-spinoff context bundle

When the caller passes `aside task description` for this call, run the same
relevance judgment already used for `Relevant entries`/`File relevance:`
above (steps 1-2's topical `description` matching, and step 5's
`file-relevance` `metadata.files` matching when `target files` was also
passed) — but run it against the `aside task description` text, not against
`task description`. These are two separate tasks in the same call: never
reuse `task description`'s own matches here, and never let this judgment
feed back into the `Relevant entries` section above — the aside-relevance
judgment produces its own independent output, described below.

The inferred-confidence exclusion gate (Step 6) applies here without
modification: before any candidate entry is added to the spinoff bundle,
check it exactly as Step 6 requires. Only after this check passes does a
candidate become eligible for inclusion in `Spinoff prompt:` below.

If the judgment finds one or more matching entries/`file-relevance` paths
(after the exclusion gate above has already been applied):

- **`Spinoff prompt:`** — a condensed, self-contained bundle of the relevant
  facts and/or `file-relevance` paths found, worded so it stands alone
  without needing this parent conversation — mirroring `spawn_task`'s own
  `prompt` parameter requirement ("self-contained — include file paths and
  enough context to act without this conversation"). Summarize facts the
  same way `Relevant entries` does (`name — description`/one-sentence
  paraphrase, never a full entry body) and list any matched
  `file-relevance` paths the same way step 5's `File relevance:` sub-list
  does.
- **`Spinoff tldr:`** — one to two plain-English sentences, mirroring
  `spawn_task`'s `tldr` parameter ("1-2 sentence plain-English summary...
  shown to the user in a tooltip").

**If the judgment finds no matching entries or `file-relevance` paths for
the `aside task description`** (including when everything that would
otherwise match was excluded by the inferred-confidence gate above), output
exactly:

```
Spinoff prompt: insufficient memory to construct a grounded context bundle for this aside — proceed without one.
```

Never a fabricated or generic-sounding bundle that merely looks grounded.
`Spinoff tldr:` is correspondingly either absent or states the same
insufficiency (e.g. `Spinoff tldr: no relevant memory found for this
aside.`) — never invent `tldr` content in this case either.

**This agent never calls `spawn_task` itself** — mirroring this file's
existing "never marks anything resolved" invariant: this agent only ever
returns the `Spinoff prompt:`/`Spinoff tldr:` strings; the calling agent
decides whether, and how, to invoke `mcp__ccd_session__spawn_task`.

A matched entry surfaced into a spinoff bundle is still subject to step 3
above — its `metadata.last_referenced` gets updated and the update is
recorded in `Written`, same as any other surfaced entry.
