# Nelly cache lookup (design-author Research First, step 1)

Read by `design-author` when it calls `agent-nelly:agent-nelly` for the brief (step 1): pass `file summary lookup` and `research digest lookup` on that same call and apply the results as below.

**[File & Folder Summary Cache]** On that same call (fresh or reused), also pass `file summary
lookup` for every path the brief's `Relevant entries`/`File relevance:` sub-list already names
plus any file explicitly named in the approved `requirements.md` — this is a smaller place to
check than re-deriving those paths' purpose from scratch. For each **cache hit**, verify
freshness yourself before trusting it: compute the file's current content hash (`Grep`
`pattern: "^"`, `output_mode: "count"` isn't a hash — use a `Bash` `git hash-object <path>`
call, the same primitive `research-consolidator` uses for `git_hash`) and compare it to the
returned `git_hash`; a match is a **confirmed** cache hit, a mismatch is a miss. Pass the list
of paths with a confirmed hit down to `research-consolidator` as "already summarized, skip
deep-reading unless something in this feature's scope specifically requires re-reading it" —
the same skip mechanic it already applies to the brief's `Relevant entries` (see its Pass 1,
step 1). This is the read side of the cache; the write side is step 2 below.

**[Research Digest Cache]** On the same call, also pass `research digest lookup` for the same
paths. Unlike a file summary, a digest carries its own freshness: agent-nelly hashes each
source itself and marks the digest `fresh` or `stale`, with `changed` listing the sources
that changed or were deleted. Pass each `fresh` digest's `summary` to `research-consolidator`
as known context, and treat its sources like confirmed file-summary hits (skip deep-reading
unless this feature's scope requires it). For a `stale` digest, pass its `summary` as
possibly-outdated context and ask `research-consolidator` to re-read only the `changed`
files. No digest for a path means research it normally.
