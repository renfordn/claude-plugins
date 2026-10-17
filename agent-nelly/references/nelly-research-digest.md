# Research Digest Cache

Read by `agent-nelly` when the caller passes `research digest` or `research digest lookup` (store or look up a subagent's multi-file findings). Text moved verbatim from agent-nelly.md.

### Research Digest Cache

Purpose: a file summary covers one file in 240 characters; a **research digest** keeps a
subagent's multi-file findings (up to 2,000 characters over up to 30 source files) so the next
task touching those files starts from them instead of re-reading everything. Each digest records
the git-blob hash of every source file it was written from, so a lookup can say whether it is
still `fresh` or has gone `stale`, and which sources `changed`.

Digests live one file per digest in `entries/<DIGEST_SUBDIR>/` (`nelly_memory.DIGEST_SUBDIR`,
currently `research-digest`), are keyed by topic + sorted source-path set, are overwritten in
place for the same key, and are never promoted, archived, or duplicate-checked, just like file
summaries. Only `scripts/research_digest.py` writes them: it hashes the sources, truncates the
body, and writes atomically, none of which the `Write` tool can do.
`hooks/nelly_digest_guard.py` denies a hand-written digest whose body is over 2,000 characters.

**Write path: `research digest`.**

When the caller passes `research digest` (one `{topic, summary, paths}` object, or a list of
them; `paths` are repo-relative with forward slashes):

1. For each item, write the item as JSON to the script's stdin:
   `CLAUDE_PLUGIN_DATA="${CLAUDE_PLUGIN_DATA}" CLAUDE_PLUGIN_OPTION_SHARED_MEMORY_ROOT="${user_config.shared_memory_root}" python3 "${CLAUDE_PLUGIN_ROOT}/scripts/research_digest.py" write --json - --cwd [cwd] --repo-root [repo root]`
   via `Bash` (`--repo-root` defaults to `cwd`; pass the repository root when they differ).
2. The script normalizes and de-duplicates `paths`, hashes each source file's working-tree
   bytes, truncates `summary` to 2,000 characters at a line boundary with a
   `…[truncated N chars]` marker, writes `digest-<topic slug>-<hash12>.md` atomically, and
   upserts `nelly-index.json`. It prints `{file, name, topic, sources, updated, truncated}`.
3. It rejects the item with exit code 2 and stores nothing when: `topic` or `summary` is empty,
   `paths` is empty, a path is absolute or contains `..`, there are more than 30 paths (the
   caller splits the digest, e.g. by top-level directory), or a source file does not exist.
   Report the script's stderr reason back to the caller in `Written`; don't retry the same item.
4. `Written` reports one line per item: `Wrote research digest "<topic>" (<N> sources)`, plus
   `(truncated)` when `truncated` is true.

**Read path: `research digest lookup`.**

For each repo-relative path the caller lists:

1. Run `CLAUDE_PLUGIN_DATA="${CLAUDE_PLUGIN_DATA}" CLAUDE_PLUGIN_OPTION_SHARED_MEMORY_ROOT="${user_config.shared_memory_root}" python3 "${CLAUDE_PLUGIN_ROOT}/scripts/research_digest.py" lookup <path> --cwd [cwd] --repo-root [repo root]` via `Bash`. It answers from
   `nelly-index.json` when the index matches the digest files on disk, and otherwise scans
   `entries/<DIGEST_SUBDIR>/` directly (iCloud conflict copies such as `name 2.md` are ignored).
   Either way the results are the same; the output's `source` says which was used.
2. The output is `{path, digests: [{name, topic, status, changed, updated, file, summary}],
   source}`, ordered `fresh` first, then newest `updated`. Report each digest as:
   - `fresh`: every source still hashes to its recorded value. The caller can use `summary` as
     known context instead of re-reading those files.
   - `stale`: `changed` lists the sources whose content changed or that no longer exist. The
     caller re-reads only those, then sends an updated `research digest` for the same topic
     and paths (same key, so it overwrites in place).
3. No digests: a plain miss. The caller researches normally and sends a `research digest`
   afterward.
4. Like `file summary lookup`, this is a read: it never touches `metadata.last_referenced` and
   never appears in `Written`.
