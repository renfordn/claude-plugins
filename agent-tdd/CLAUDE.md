<!-- TDD-SKIP -->
# CLAUDE.md

Repo-specific notes for Claude Code sessions working on `agent-tdd`.

## CUPS — the release shorthand

"CUPS" means, in order:

1. **C**ommit — commit the pending changes with a clear, descriptive message.
2. **U**pdate — run `python3 scripts/bump_version.py <new_version>` to move
   `CHANGELOG.md`'s `[Unreleased]` entries under a new version heading and sync
   `.claude-plugin/plugin.json`'s `version` to match. Pick `<new_version>` by
   normal semver judgement from what's actually in `[Unreleased]` (patch/minor/major).
3. **P**ush — `git push -u origin <branch>` (see Git Push Requirements below).
4. **S**tale cache removal — clear the local Claude Code plugin cache so the
   bumped plugin is picked up on next load: `rm -rf ~/.claude/plugins/cache`.

Despite the acronym order (Commit, Update, Push, Stale-cache-removal), the actual
sequence run is **bump → commit → push → clear cache**, since the version bump has
to happen before there's anything meaningful to commit. When asked to "CUPS", run:

```
python3 scripts/bump_version.py <new_version>
git add -A && git commit -m "..."
git push -u origin <branch>
rm -rf ~/.claude/plugins/cache
```

Run the test suite (`python3 -m unittest discover -s tests -p "test_*.py" -v`)
before committing — it should stay green.

Note: `rm -rf ~/.claude/plugins/cache` clears the cache on whatever machine the
command runs on. In a remote/sandboxed session (like Claude Code on the web) that
is not the user's own machine, so this step is a no-op there — mention that to the
user rather than silently skipping it, and let them run it locally if needed.
