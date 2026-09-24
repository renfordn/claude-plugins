# Shared memory root (agent-nelly + agent-isdd)

By default agent-nelly's memory and agent-isdd's SDD state live under `${CLAUDE_PLUGIN_DATA}`, which is
local disk, separate for every plugin identity (`agent-nelly@inline` vs.
`agent-nelly@renfordn-plugins`) and for every machine. None of it is synced. Memory written on your
laptop won't show up on your desktop, and on one machine it can be split between two identities.

The optional `shared_memory_root` plugin option points both plugins at one directory you choose.
Every identity and every machine configured with it reads and writes the same store. With it unset,
nothing changes.

## Configure

Set the same absolute directory for **agent-nelly and agent-isdd**, and for **every identity** each
one is installed under. Options are stored per plugin id in `pluginConfigs`, so `@inline` and
`@renfordn-plugins` each need the value.

- In Claude Code: `/config`, find the plugin's **Shared memory root** row, or set it when enabling the plugin.
- From a terminal: `claude plugin install agent-nelly@renfordn-plugins --config shared_memory_root=$HOME/claude-memory`
- By hand, in `~/.claude/settings.json`. Project `.claude/settings*.json` files are ignored for plugin options:

  ```json
  "pluginConfigs": {
    "agent-nelly@renfordn-plugins": { "options": { "shared_memory_root": "~/claude-memory" } },
    "agent-nelly@inline":           { "options": { "shared_memory_root": "~/claude-memory" } },
    "agent-isdd@renfordn-plugins":  { "options": { "shared_memory_root": "~/claude-memory" } },
    "agent-isdd@inline":            { "options": { "shared_memory_root": "~/claude-memory" } }
  }
  ```

`~` and `$VARS` are expanded. A relative path is rejected with a clear error instead of being
resolved against whatever directory a hook happens to run in. Start a new session after changing
the option, because hooks resolve it at startup. plugin-harness needs no option of its own: it
follows the location agent-isdd records in its `${CLAUDE_PLUGIN_DATA}/sdd-memory-location.json`.

## Layout

```
<shared_memory_root>/
├── .gitignore / .gitattributes   # created on first use, never overwritten
├── agent-nelly-memory/           # same layout as ${CLAUDE_PLUGIN_DATA}/agent-nelly-memory/
│   ├── <project-slug>/  MEMORY.md, entries/, archive/
│   └── global/          GLOBAL-MEMORY.md
└── sdd-memory/                   # same layout as ${CLAUDE_PLUGIN_DATA}/sdd-memory/
    └── <project-slug>/spec/<feature>/ ...
```

These files stay in `${CLAUDE_PLUGIN_DATA}` even when a shared root is set, because they are rewritten
constantly or only describe this machine's sessions:

| File | Plugin | Why it stays local |
|---|---|---|
| `hotspots.json` | agent-nelly | Rewritten on every Read/Write/Edit. |
| `nelly-index.json` | agent-nelly | Derived from `entries/`, so it's gitignored and rebuilt at SessionStart. |
| `last-stop.json`, `snapshots/` | agent-isdd | Record one machine's clean stops and compactions. |

Once a shared root is active, the slug guards deny Write/Edit into the old
`${CLAUDE_PLUGIN_DATA}` copies of `agent-nelly-memory/` and `sdd-memory/`, so nothing splits off into
stale state. The permission hooks auto-approve writes under the shared root the same way they did
under `${CLAUDE_PLUGIN_DATA}`.

## Recommended: a git repo you pull and push

```bash
mkdir -p ~/claude-memory && cd ~/claude-memory && git init
git remote add origin git@github.com:<you>/claude-memory.git   # private repo
```

Pull before you start work on a machine, and commit and push when you finish:

```bash
git -C ~/claude-memory pull --rebase && git -C ~/claude-memory add -A && git -C ~/claude-memory commit -m sync && git -C ~/claude-memory push
```

The generated `.gitattributes` sets `merge=union` on the append-only files (`MEMORY.md`,
`GLOBAL-MEMORY.md`, `*HISTORY*.md`, `*.jsonl`). When two machines each add memories, git keeps both
sides' lines instead of raising a conflict. Entry files (`entries/<name>.md`) are one file per
memory, so they rarely collide. `workflow-state.*` for one feature is the exception: don't drive the
same SDD feature on two machines at once without syncing in between.

iCloud Drive or Dropbox also work, with no merge step. The trade-off: when two machines edit the same
file before it syncs, you get a "conflicted copy" file instead of a merge. Keep sessions on different
machines from overlapping.

## Migrating existing data

Fold each identity's existing store into the shared root with
[`scripts/merge_plugin_data.py`](../scripts/merge_plugin_data.py). Run it once per identity and per
machine, and use `--dry-run` first:

```bash
ROOT=~/claude-memory
for id in inline renfordn-plugins; do
  python3 scripts/merge_plugin_data.py ~/.claude/plugins/data/agent-nelly-$id/agent-nelly-memory "$ROOT/agent-nelly-memory"
  python3 scripts/merge_plugin_data.py ~/.claude/plugins/data/agent-isdd-$id/sdd-memory "$ROOT/sdd-memory"
done
```

Point the script at the memory subdirectories, not the whole data dir, so machine-local files such
as the pointer file stay out of the shared root. The old copies are left untouched unless you pass
`--delete-source`.

## Caveat: project slugs come from absolute paths

`<project-slug>` is derived from the project's absolute path, e.g.
`/Users/jay.nelson/Codebase/x` becomes `users-jay-nelson-codebase-x`. A project only lines up across
machines when it's checked out at the same absolute path, which means the same username and the same
directory. Checkouts at different paths get separate slugs in the shared root, so their memory
doesn't combine, but nothing breaks.
