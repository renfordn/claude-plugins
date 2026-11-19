# Evidence log schema

Read by `scripts/tdd_check.py`, `hooks/tdd_subagent_stop.py` and `hooks/red_first_guard.py` (release 3 contract).

One JSON object per line in `<git common dir>/agent-tdd/evidence.jsonl` (shared by every worktree of a repo). Every entry carries `phase`, `token` (8 hex), `at` (ISO time) and, when known, `worktree` (absolute top level), `slice` (title), `slice_id` and `base`.

| phase | written by | extra fields | meaning |
|---|---|---|---|
| `start` | `tdd_check.py start` | `kind`, `gaps` {`risks`, `inspected`, `run`} | a slice is open in `worktree`; later entries for that worktree belong to it |
| `red` | `tdd_check.py red` | `cmd`, `exit`, `confirmed`, `note` | confirmed when the test fails before implementation |
| `green` | `tdd_check.py green` | `cmd`, `exit`, `confirmed`, `note` | confirmed when it passes after a confirmed `red` logged since the slice's `start` |
| `coverage` | `tdd_check.py coverage` | `cmd`, `mutant`, `exit`, `mutant_exit`, `confirmed` | R7: the new test passes and fails against a mutated `mktemp -d` copy, so it pins the behavior |
| `bypass` | `tdd_check.py bypass` | `reason` | logged permission to edit production files before Red (contract stubs, scaffolding, blockers) |
| `done` | `tdd_check.py done` | — | closes the open slice in `worktree` |
| `integration` | `tdd_check.py integration` | `wave`, `cmd`, `exit`, `confirmed` | the lead's full-suite run after a wave |

A slice is open in a worktree from its latest `start` until a `done` or the next `start`; an open slice older than 4 hours is ignored. `red_first_guard` allows a production edit in an open slice only after a confirmed `red`, a confirmed `coverage` or a `bypass` logged since that `start`.
