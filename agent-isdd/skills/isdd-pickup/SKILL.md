---
name: isdd-pickup
description: >
  Survey all SDD specs for the project to find stalled, stale or ready-to-resume features, detect those claimed by
  another session or worktree (avoid overlap), and recommend the next one. Use proactively at start of /isdd or
  /isdd-continue when no feature is named, and any time the question is what to do next: "what should I work on next",
  "what's stalled", "what's on the brief board", "anything blocked?".
context: fork
agent: Explore
---

# ISDD Session Pickup & Coordinator

Surveys the project's SDD spec memory, cross-references it with active git worktrees,
and produces a ranked feature list with a clear recommendation. It then returns instructions
for the main session to claim and release a lightweight session lock (so two worktrees never
race on the same spec); it does not manage locks itself.

---

## Step 1 — Locate the SDD memory for this project

Resolve the project's memory directory through agent-isdd, never by hand (the slug and the
shared memory root are configured, not derived from `pwd`). Use the no-argument form: it only
prints the path and creates nothing (the creating forms, with a flag, are for the main session):

```bash
CLAUDE_PLUGIN_DATA="${CLAUDE_PLUGIN_DATA}" CLAUDE_PLUGIN_OPTION_SHARED_MEMORY_ROOT="${user_config.shared_memory_root}" python3 "${CLAUDE_PLUGIN_ROOT}/hooks/sdd_memory.py"
```

`<spec_root>` is that printed path plus `/spec`. If it does not exist, report "no specs" and
stop. Otherwise list every spec directory under `<spec_root>`. Each directory name is a `<YYYY-MM-DD-feature-slug>`.

---

## Step 2 — Read each spec's state

For every spec directory, read `workflow-state.md`. Extract:

| Field | Where to find it |
|-------|-----------------|
| Current Phase | `Current Phase:` line |
| Status | `Status:` line |
| Feature title | `Feature:` line or directory name |
| Track | `Track:` line (Fast / Standard) |
| Last modified | `stat -f "%Sm" -t "%Y-%m-%d"` on the file (macOS) or `date -r` |

Classify each spec into one of these buckets:

- **🟢 Active** — Implementation or Tasks phase, modified < 2 days ago, no expired lock
- **🟡 Ready** — Requirements or Design phase, gate passed (no blocker), < 3 days idle
- **🟠 Stalled** — Any non-complete phase, modified 3–7 days ago
- **🔴 Abandoned** — Modified > 7 days ago, not complete
- **⛔ Blocked** — workflow-state has an explicit blocker note
- **✅ Complete** — Phase = Implementation and Status = complete/done

---

## Step 3 — Check for active sessions and session locks

### Git worktrees

From the repo root:

```bash
git worktree list --porcelain
```

Match each worktree's branch name against spec slugs. A worktree on a branch like
`feat/admin-nav-queue-redesign` signals that spec may be actively in use.

### Session lock files

Check every spec directory for a lock:

```bash
ls "${SPEC_ROOT}"/*/session-lock.json
```

(`SPEC_ROOT` is `<spec_root>` from Step 1. No match just means no locks.)

Each `session-lock.json` looks like:

```json
{
  "session_id": "local_abc123",
  "worktree": "/path/to/worktree",
  "feature": "2026-09-28-admin-nav-queue-redesign",
  "claimed_at": "2026-10-14T10:00:00Z",
  "expires_at": "2026-10-14T14:00:00Z"
}
```

- **Active lock**: `expires_at` is in the future → treat that spec as claimed (the file is read-only to you; reading it is all the fork does)
- **Expired lock**: `expires_at` is in the past → ignore the lock, note it as stale (see Overlap prevention for the single staleness rule)

---

## Step 4 — Check external board (future: Trello)

> ⏳ **Follow-up**: A Trello integration is planned. When implemented, this step will
> pull card status (To Do / In Progress / Done), priority, and labels from the matching
> Trello board and cross-reference them with spec slugs to enrich classification.
>
> For now, skip this step — classification is based on SDD state + git worktrees only.

---

## Step 5 — Rank and present

Show the feature table, sorted by priority (highest first):

```
▸ Project: file-organiser — 8 specs found

| # | Feature                        | Phase    | Status   | Sessions | Days idle |
|---|--------------------------------|----------|----------|----------|-----------|
| 1 | admin-nav-queue-redesign       | Tasks    | 🟠 Stalled | none   | 5         |
| 2 | sentry-error-logging           | Req.     | 🟡 Ready | none     | 2         |
| 3 | duplicate-gallery-view         | Design   | ⛔ Blocked | none   | 1         |
| 4 | consolidate-outstanding-slices | Req.     | 🟢 Active | local_da | 0        |
| 5 | ...                            |          |          |          |           |
```

Priority rules (higher = better candidate to pick up):
1. Stalled specs furthest along (Tasks > Design > Requirements)
2. Ready specs with no lock and a worktree available
3. Blocked specs (list them but explain the blocker; don't recommend without user override)
4. Abandoned specs — flag for archiving or dropping
5. Active (already claimed) specs — list for awareness only, do not recommend

**Recommendation** — state the single best feature to pick up and why in one sentence:

> 🎯 Recommended: `admin-nav-queue-redesign` — furthest along (Tasks phase), stalled 5 days,
> no active session holding it.

If everything is either active or blocked, say so clearly and have the main session ask (Step 6) whether to force-claim or wait.

---

## Step 6 — Return "Main-session actions" (the fork never writes)

This skill runs forked in a read-only Explore agent. The fork never writes, deletes, or waits
for the user. It ends by returning the Step 5 table and recommendation, then the block below
copied verbatim, with every `<placeholder>` filled in. Report each candidate's lock status
(none / active until `<expires_at>` held by `<worktree>` / expired) in the table; the lock may
change before the main session acts, which is why the claim step re-reads it.

```text
Main-session actions
1. Ask the user via AskUserQuestion to pick or confirm a feature: <recommended feature>,
   <other candidates>, or wait.
2. Claim the lock for the chosen feature. Just before writing
   <spec_root>/<feature>/session-lock.json, re-read that file. If it exists and its expires_at is
   still in the future, do not overwrite it: offer the Overlap prevention options (wait, force-claim,
   pick another) via AskUserQuestion. Otherwise write the file with these fields:
     session_id:  <current session id, or "unknown">
     worktree:    <output of `git rev-parse --show-toplevel` run in the claiming session>
     feature:     <YYYY-MM-DD-feature-slug>
     claimed_at:  <UTC now, ISO 8601, e.g. 2026-10-14T10:00:00Z>
     expires_at:  <claimed_at + 4 hours, same format>
3. Release: delete <spec_root>/<feature>/session-lock.json when the session finishes, is
   interrupted, or hands off. If never released, it stops counting at its expires_at.
4. Then continue with /isdd-continue for the chosen feature.
```

Fill `<spec_root>` (from Step 1) and the `<feature>` values for the recommended feature and each
alternative, so the main session needs no further lookup.

---

## Overlap prevention

One staleness rule everywhere: a lock is **active** while its `expires_at` (claim time + 4 hours)
is in the future, and **expired** after, so it is ignored and may be claimed without asking. The
4-hour window is the only time threshold; there is no separate "older than N hours" test.

When the chosen spec has an **active** lock, the main session must not claim. It shows who holds
the lock, from which worktree, and when it expires, then offers via AskUserQuestion:

- **(a) Wait** — check back later or set a reminder
- **(b) Force-claim** — override the lock; only after explicit user confirmation, and only when
  the locking worktree is no longer in `git worktree list` (its session likely crashed)
- **(c) Pick a different feature** — re-run the ranked list and recommend the next best

This is the only place the force-claim rule is defined; Step 6 refers here.

---

## Integration with `/isdd` and `/isdd-continue`

This skill fires automatically at the start of `spec-driven-development` and `workflow-manager`
when no specific feature is identified in the user's request. The triggering check is:

> "Does the user's message name a specific feature or spec slug?"

- Named → skip this skill, proceed directly.
- Not named → run Steps 1–5 and return the table plus Main-session actions; the main session
  asks the user (AskUserQuestion), claims the lock (Step 6), then continues.

---

## Staleness reference

| Threshold | Label | Recommendation |
|-----------|-------|---------------|
| < 1 day | Fresh | Active session, don't interrupt |
| 1–3 days | Idle | Fair game, check for a lock |
| 3–7 days | Stalled | Good candidate to resume |
| > 7 days | Abandoned | Ask user: resume, defer, or archive? |
