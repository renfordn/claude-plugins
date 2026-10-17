---
name: isdd-pickup
description: >
  Survey all SDD specs for the project to find stalled, stale or ready-to-resume features, detect those claimed by
  another session or worktree (avoid overlap), and recommend the next one. Use proactively at start of /isdd or
  /isdd-continue when no feature is named, and any time the question is what to do next: "what should I work on next",
  "what's stalled", "what's on the brief board", "anything blocked?".
---

# ISDD Session Pickup & Coordinator

Surveys the project's SDD spec memory, cross-references it with active git worktrees,
and produces a ranked feature list with a clear recommendation. Also manages lightweight
session locks so two worktrees never race on the same spec.

---

## Step 1 — Locate the SDD memory for this project

Resolve the spec directory through agent-isdd, never by hand (the slug and the shared
memory root are configured, not derived from `pwd`):

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/sdd_memory.py" --spec-path
```

List every spec directory under that path. Each directory name is a `<YYYY-MM-DD-feature-slug>`.

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
ls "$(python3 "${CLAUDE_PLUGIN_ROOT}/hooks/sdd_memory.py" --spec-path)"/*/session-lock.json 2>/dev/null
```

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

- **Active lock**: `expires_at` is in the future → treat that spec as claimed
- **Stale lock**: `claimed_at` > 4 hours ago and no recent git activity on that worktree → ignore the lock, note it as stale

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

If everything is either active or blocked, say so clearly and ask whether to force-claim or wait.

---

## Step 6 — Claim a session lock

When the user confirms which feature to work on, write `session-lock.json` to that spec's
directory before handing off to `/isdd-continue`:

```bash
# ISO timestamps (macOS)
CLAIMED=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
EXPIRES=$(date -u -v+4H +"%Y-%m-%dT%H:%M:%SZ")

cat > "${spec_dir}/session-lock.json" <<EOF
{
  "session_id": "${SESSION_ID:-unknown}",
  "worktree": "$(git worktree list | head -1 | awk '{print $1}')",
  "feature": "${FEATURE_SLUG}",
  "claimed_at": "${CLAIMED}",
  "expires_at": "${EXPIRES}"
}
EOF
```

Then continue with `/isdd-continue` for that feature as normal.

---

## Step 7 — Release the lock

When a session finishes, is interrupted, or explicitly hands off, remove the lock:

```bash
rm "${spec_dir}/session-lock.json"
```

The lock also auto-expires after 4 hours — stale locks are ignored at Step 3, so orphaned
locks from crashed sessions don't block future work.

---

## Overlap prevention

If a user tries to `/isdd-continue` a spec that has an **active, non-expired lock**:

1. Show who holds the lock, from which worktree, and when it expires.
2. Offer three options:
   - **(a) Wait** — check back later or set a reminder
   - **(b) Force-claim** — override the lock (use if the locking session crashed)
   - **(c) Pick a different feature** — run the ranked list and recommend the next best

Only proceed with force-claim after explicit user confirmation, and only if the lock is
> 2 hours old or the locking worktree is no longer in `git worktree list`.

---

## Integration with `/isdd` and `/isdd-continue`

This skill fires automatically at the start of `spec-driven-development` and `workflow-manager`
when no specific feature is identified in the user's request. The triggering check is:

> "Does the user's message name a specific feature or spec slug?"

- Named → skip this skill, proceed directly.
- Not named → run Steps 1–5, present the table, wait for the user to confirm, then claim the
  lock (Step 6) before continuing.

---

## Staleness reference

| Threshold | Label | Recommendation |
|-----------|-------|---------------|
| < 1 day | Fresh | Active session, don't interrupt |
| 1–3 days | Idle | Fair game, check for a lock |
| 3–7 days | Stalled | Good candidate to resume |
| > 7 days | Abandoned | Ask user: resume, defer, or archive? |
