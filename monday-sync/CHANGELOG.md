# Changelog

## [0.3.3] - 2026-10-10

### Fixed
- `first_class` moved out of `plugin.json` into `.claude-plugin/first-class.json`; the marketplace sync warned about the unknown manifest key.

## [0.3.2] - 2026-10-10

### Added
- Source now lives in the renfordn/claude-plugins monorepo (previously only an account copy).
- `shared_memory_root` option (same value as agent-isdd).
- SessionStart drift scan: linked features whose `workflow-state.md` changed since the last board sync are flagged for sync, catching changes made outside the Edit/Write hook.

### Fixed
- `flag_sync.py` now also runs on Bash. State files changed through heredocs, `printf >>` or `python3 -` were never flagged, so the board had stopped updating since 2026-10-04.
- `git_probe.sh` failed to parse under macOS bash 3.2 (an unbalanced `case` inside `$(...)`), so merge detection never ran.
