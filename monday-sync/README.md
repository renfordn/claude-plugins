# monday-sync

A Claude Code plugin that keeps the monday.com **Software Engineering** board (5105170755) in step
with [agent-isdd](https://github.com/renfordn/agent-isdd) features and their git branches. It
doesn't modify agent-isdd or agent-tdd.

- **Hooks (local only, fail-open, never block):**
  - `flag_sync.py` (PostToolUse on Write|Edit|MultiEdit) flags a feature when its
    `spec/<feature>/workflow-state.md` is written. If the phase or status changed, it asks for a
    sync.
  - `session_start.py` lists the features still waiting for a sync.
- **Skill `monday-sync`:** does the actual sync through the monday MCP connector and the linked
  computer's shell. See `skills/monday-sync/SKILL.md`.
- **Skill `monday-kickoff`:** run hourly on weekdays by a scheduled task that needs the linked
  Mac. It picks at most one ticket in Gather Requirements (oldest first), drafts its isdd
  requirements, design and tasks in `<repo>/spec/<date-slug>/` without asking, posts
  multiple-choice open questions on the ticket and moves it to Implementation Ready. It never
  implements, commits or branches. See `skills/monday-kickoff/SKILL.md`.
- **Status mapping:**
  - Requirements and Design map to Gather Requirements.
  - Tasks, or Awaiting Implementation Request before implementation, maps to Implementation Ready.
  - Implementation maps to In progress.
  - A branch pushed with at least 1 commit and not yet merged maps to Review.
  - A branch merged into `origin/main` maps to Done. Done comes only from a merge.
  - Blocked maps to Stuck. A Stuck set on the board blocks the isdd workflow.

## Layout

```
.claude-plugin/plugin.json
hooks/hooks.json          hook registration
hooks/store.py            atomic I/O: <feature>/monday.json sidecar, ${CLAUDE_PLUGIN_DATA}/store.json
hooks/fields.py           shared workflow-state.md field parser
hooks/planner.py          pure sync logic: desired status, diff-only writes, board->isdd rules
hooks/cli.py              JSON CLI the skills call: sync-begin, plan, record, pending, candidates,
                          kickoff-candidates
hooks/flag_sync.py        PostToolUse hook
hooks/session_start.py    SessionStart hook
hooks/git_probe.sh        read-only POSIX sh git probe, run on the linked computer
skills/monday-sync/       SKILL.md + references/board.md (column IDs, value formats, kickoff markers)
skills/monday-kickoff/    SKILL.md + references/projects.json (Project label -> repo path)
tests/                    pytest suite
```

## Install

Add this repo as a plugin, either through a marketplace entry that points at it, or with
`claude --plugin-dir /path/to/monday-sync` for local testing. Requirements:

- the monday.com MCP connector (connected);
- a linked computer, for git reads on project repos;
- for monday-kickoff, the Claude `memories` folder (agent-nelly-memory, sdd-memory) attached to the scheduled task: read-only context before drafting specs, skipped if absent;
- `python3` (stdlib only) and `sh`.

No API tokens are stored.

State lives in two places:

- `<isdd memory>/spec/<feature>/monday.json`, one per feature: the linked item id, project,
  repo path, branch, pushed head and the last-sync snapshot.
- `${CLAUDE_PLUGIN_DATA}/store.json`, one per install: pending features, linked items and
  dismissed candidates.

## Test

```sh
python3 -m pytest -q
```

The suite has no network access and needs no monday account. It covers:

- the mapping table, rewind, and unknown git;
- kickoff candidate selection: eligibility, markers, the 3h retry/stuck rule, oldest first;
- Stuck in both directions, conflicts, and a second plan making 0 writes;
- recreating a deleted item only once;
- the hooks, run as subprocesses;
- `git_probe.sh` against temp repos with a bare origin: unpushed; pushed and unmerged; 0 commits
  ahead; merged via a merge commit; a deleted branch merged via `pushed_head`; a stale
  `origin/main`; a missing repo.

The skill itself is checked by a manual dry run: syncing twice should make 0 board writes the
second time.

## Opting a feature out

`cli.py record <feature dir> --unlink` stops syncing that feature: it leaves pending, the hook
ignores it, and no ticket is ever created for it. `cli.py record <feature dir> --item-id <id>`
links it again.

## Limits

- Merges are detected only as far as the user's last `git fetch`. The probe never fetches.
- Squash and rebase merges are not detected. A branch that left origin unmerged is surfaced as
  "confirm Done?".
