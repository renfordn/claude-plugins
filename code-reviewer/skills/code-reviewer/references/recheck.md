# Per-finding re-check (R14)

Use it after an implementer responds to one reported finding and you want to know whether *that
finding* is fixed. It is not a slice review: no new findings, no `<!--CODE-REVIEWER-REPORT-->`, no
`<!--REVIEW-SCOPE-->` marker. For the slice itself use the normal independent review.

## Commands

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/recheck.py" start  F2 [--findings PATH] [--base SHA] [--restart [--reason TEXT]]
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/recheck.py" run    F2 [--findings PATH] [--diff-base SHA] [--paths P [P ...]]
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/recheck.py" status F2 [--findings PATH]
```

- `start` snapshots the finding from `findings.json` into `recheck.json` beside it. Base defaults
  to HEAD. An existing open entry is left as is; a stopped or resolved one is refused unless
  `--restart` (stopped only, once; earlier passes are kept, a `{"restart", "reason"}` marker is
  appended, and the pass limit still counts every pass).
- `run` briefs a fresh `finding-verifier` (re-check mode). The brief holds the finding, earlier
  passes with `Previous evidence: pass n: ...` lines (so the verifier can judge `new_evidence`),
  the response diff, and the direct tests. It parses `<!--FINDING-RECHECK-REPORT-->` (one fenced
  json block; bare JSON also accepted), records a pass, applies the stop conditions and writes the
  finding's `resolution` back.
- `REVIEW_RECHECK_CMD` replaces the verifier command (tests); `REVIEW_RECHECK_TIMEOUT` (seconds,
  default 900) bounds it.

## What the verifier is given

Scope is the finding's `file` plus any `--paths` the caller passes (the files the response touched).

- Diff: `git diff <base> -- <scope>` (working tree plus commits since base), plus each untracked
  file in scope as full content. Files outside the scope are not included. The brief is passed as
  one argv string, so the diff is cut at 60KB with a truncation note.
- Direct tests (at most 10): test-pattern files among the scope paths, plus tracked test files
  that mention the finding file's basename stem (`git grep -w`). The verifier may still read other
  files with its read-only tools; the brief limits what it is shown, not what it can open.

## recheck.json

```
{"F2": {"finding": {...}, "base": "<sha>",
        "passes": [{"outcome", "evidence", "new_evidence", "at"}, {"restart", "reason"}],
        "status": "open|resolved|stopped", "stop_reason": null|"..."}}
```

Writes are atomic and happen under an exclusive lock on `recheck.json.lock`; `run` reloads the file
after the verifier returns and updates only its own id.

## Stop conditions (fixed)

| Report | Result | `resolution` |
|---|---|---|
| `resolved` | done | `resolved` |
| `needs-detailed-review` (blocker, earlier phase or approval boundary) | stop, `escalate (blocker, earlier phase or approval boundary)` | `open` |
| `new_evidence: false` | stop, `no new evidence` | `open` |
| third pass, not resolved | stop, `pass limit` | `open` |
| missing or malformed report, launch failure, timeout | stop, `blocked` | `open` |
| id missing or its `file`/`summary` changed since the snapshot | stop, `stale finding id` | not written |
| `still-open` / `partially-resolved` | continue | `open` |

A stopped finding stays unresolved and is never cleared; hand it to the caller (a detailed review,
or a human decision to decline or accept it).
