# claude-plugins

Monorepo for Renford Nelson's personal Claude Code plugins:

- `agent-isdd/` — spec-driven design agent
- `agent-tdd/` — test-driven implementation agent
- `code-reviewer/` — code review skill
- `agent-nelly/` — memory system
- `focus-ux/` — ADHD-friendly output style + visual-brief skill

Each subdirectory is a standalone plugin (own `.claude-plugin/plugin.json`,
`INTEROP.md`, etc.) migrated here as a fresh snapshot — commit history prior
to the migration lives in the original per-plugin repos:
[agent-isdd](https://github.com/renfordn/agent-isdd),
[agent-tdd](https://github.com/renfordn/agent-tdd),
[code-reviewer](https://github.com/renfordn/code-reviewer),
[agent-nelly](https://github.com/renfordn/agent-nelly),
[agent-ux](https://github.com/renfordn/agent-ux) (archived; retired from this repo).

## Installing the plugins

See [`docs/install-and-verify.md`](./docs/install-and-verify.md) for the full
install, verification, and troubleshooting walkthrough covering all 5 plugins
in the `renfordn-plugins` marketplace.

## Checking account plugin versions

If you use the plugins from your Claude account (the Code tab loads them as `<plugin>@inline`),
`claude plugin update` doesn't manage them. After pushing a release, run
`python3 scripts/check_account_plugins.py` to compare the desktop app's account copies with this
repo. It exits 1 and lists any stale copies; re-sync the account's plugin marketplace, restart the
app, and run it again.

## Sharing memory across machines

agent-nelly's memory and agent-isdd's SDD state are local to each plugin install and each machine by
default. To share them, set the `shared_memory_root` option to a synced directory (a git repo is
recommended). See [`docs/shared-memory-root.md`](./docs/shared-memory-root.md).

## Why one repo

In a fresh Claude Code cloud session, getting a private repo's content
requires an explicit `add_repo` approval per repo — separate repos meant one
approval each, every time. This repo collapses that to one `add_repo` + one
`git clone`.

## Running tests

Several plugins ship a private, identically-named `hooks/path_resolution.py`
as a bare module, not
packages. Running `pytest` across multiple plugins in one invocation lets
`sys.modules` caching from one plugin's copy silently satisfy another
plugin's import of the same bare name, which breaks once the copies diverge.
Always run each plugin's tests in its own `pytest` invocation, the way CI's
`matrix.plugin` strategy does (`.github/workflows/tests.yml`):

```
python3 -m pytest agent-isdd
python3 -m pytest agent-nelly
# ...one plugin per invocation, never `pytest .` from the repo root.
```
