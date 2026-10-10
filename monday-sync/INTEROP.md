<!-- TDD-SKIP -->
# monday-sync — Interop

monday-sync reads agent-isdd's per-feature `workflow-state.md` and keeps a `monday.json` sidecar
next to it. It never writes agent-isdd's files except through the `monday-sync` skill's recap line.

## Triggers

- `hooks/flag_sync.py` (PostToolUse `Write|Edit|MultiEdit|Bash`) flags a feature when its
  `spec/<slug>/workflow-state.md` changes. Bash commands are resolved by slug under
  `<shared_memory_root>/sdd-memory/*/spec/` and the spec dirs already in `store.json`.
- `hooks/session_start.py` flags linked features whose state hash differs from the sidecar's
  `state_hash`, then lists everything pending.

## If agent-isdd isn't installed

Nothing is flagged; the skills still work against the board directly.
