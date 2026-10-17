# Nelly persistence (design-author Research First, step 2)

Read by `design-author` after `research-consolidator` returns, when persisting its `file_summaries` to agent-nelly's `file summaries` field, one `folder summaries` item per multi-file directory, and the pass's `research digest` items.

- Persist `file_summaries` to agent-nelly's `file summaries` field (see its
  `agents/agent-nelly.md`'s "File & Folder Summary Cache" section) — **not** for a file that
  was a confirmed cache hit and skipped deep-reading in step 1 above (nothing changed about it,
  so there's nothing to re-persist), only for files `research-consolidator` actually deep-read
  this pass. Each item's `summary` is `research-consolidator`'s one-line file summary,
  truncated to 240 characters if needed (`file-summary` entries are capped — see the reference
  above); `exports`/`constraints`/`dependencies`/`tech_debt` and `git_hash` carry straight
  through from `research-consolidator`'s output.
- Also persist one `folder summaries` item per directory containing two or more of the files
  `research-consolidator` deep-read this pass, when that directory has no existing
  `folder-summary` cache hit from step 1: a short (≤240 char) description of the directory's
  overall role, drawn from those files' summaries — not a mechanical file-by-file listing.
  Skip a directory that already has a confirmed-fresh folder-summary; its purpose hasn't
  changed just because one more file inside it got touched.
- Persist the pass's multi-file findings to agent-nelly's `research digest` field (see its
  `agents/agent-nelly.md`'s "Research Digest Cache" section): one `{topic, summary, paths}`
  item per feature topic, where `topic` names what was researched (e.g. "<feature>: index
  rescan"), `summary` is the `design_findings`/`task_findings` text for that topic (agent-nelly
  truncates it to 2,000 characters), and `paths` are the repo-relative files it came from.
  A digest takes at most 30 paths, so split a larger pass into one digest per
  top-level directory. Re-send a digest that was `stale` in step 1 with the same topic and paths so it
  is overwritten in place. Skip this when every source was covered by a `fresh` digest.
