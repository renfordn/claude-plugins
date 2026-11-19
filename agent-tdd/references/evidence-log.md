# Evidence log schema

Read by `scripts/tdd_check.py`, `hooks/tdd_subagent_stop.py` and `hooks/red_first_guard.py` (release 3 contract).

One JSON object per line in `<git common dir>/agent-tdd/evidence.jsonl`, shared by every worktree of a repo and appended only. Every entry carries `phase` (one of `markers.EVIDENCE_PHASES`), `token` (8 hex) and `at` (`datetime.now().isoformat(timespec="seconds")`: naive local time, second resolution), plus, when known, `worktree` (realpath of `git rev-parse --show-toplevel`), `slice` (title), `slice_id` (normalised) and `base`.

## Entries

| phase | CLI | extra fields | confirmed when |
|---|---|---|---|
| `start` | `start --slice T [--slice-id N --base B] [--kind K] [--risks n --inspected n --run n]` | `kind` (`feature\|fix\|refactor\|contract\|validation\|ui`, default `feature`), `gaps` {`risks`, `inspected`, `run`} (integers, default 0) | always (`confirmed: true`) |
| `red` | `red --slice T [--slice-id N --base B] -- <cmd>` | `cmd`, `exit`, `confirmed`, `note` | the command exits non-zero |
| `green` | `green --slice T [...] -- <cmd>` | `cmd`, `exit`, `confirmed`, `note` | exits 0 and a confirmed `red` exists (rule below) |
| `coverage` | `coverage --slice T [...] --mutant "<shell cmd>" -- <cmd>` | `cmd`, `mutant`, `exit`, `mutant_exit`, `confirmed`, `note` | `exit == 0` and the mutant ran and failed: `mutant_exit` > 0 and not 126/127 (command not runnable) or 4/5 (pytest usage error / no tests collected); a negative exit (signal) is NOT CONFIRMED |
| `bypass` | `bypass --slice T [...] --reason "<why>"` | `reason` | always (`confirmed: true`) |
| `done` | `done [--slice T]` | — | always (`confirmed: true`) |
| `integration` | `integration --wave N --cmd "<cmd>"` | `wave`, `cmd`, `exit`, `confirmed`, `note` | the command exits 0 |

`--mutant` is a full shell command the caller builds: copy the module to a `mktemp -d` directory, change the behavior under test there, and run the same test against the copy (test-strategist's mutation procedure). `tdd_check.py` only runs it and records `mutant_exit` (plus the tail of its output in `note` when not confirmed); it never mutates files itself. A mutant that never ran proves nothing, so it never confirms.

## Printed line

Every phase prints exactly one line, built by `markers.format_evidence_line` and parsed by `markers.EVIDENCE_LINE_RE`:

`TDD-EVIDENCE <phase> <token> [exit=<code>] CONFIRMED` or `... NOT CONFIRMED (<note>)`

Phases without a command (`start`, `bypass`, `done`) omit `exit=`; `coverage` prints the test command's exit. The process exits 1 on NOT CONFIRMED.

## Open slice and ordering

"After" and "since" mean later in append order (file order), never by comparing `at`. In a worktree, a slice is open from its latest `start` until a later `done` or `start` for that worktree; an entry with no `worktree` never opens or closes a slice. An open slice whose `start.at` (naive local) is more than 4 hours old is treated as closed.

Inside an open slice, `red_first_guard` allows a production edit once a confirmed `red`, a confirmed `coverage` or a `bypass` appears after that `start` in the same worktree. `green` needs a confirmed `red` for the same slice title appended after that `start`. With no open `start` in the worktree, `green` keeps the legacy rule (any confirmed `red` with the same title and the same base, or the same worktree), and `red` prints a one-line warning to stderr but never fails, so callers that never log `start` (isdd-coach, older callers) keep working.
