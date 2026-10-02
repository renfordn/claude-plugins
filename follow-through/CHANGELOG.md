<!-- TDD-SKIP -->
## [Unreleased]

## [0.1.2] - 2026-10-02

- **Fix**: description cut from 832 to 489 characters and made a `>-` block scalar; added "update me" and "circle back" trigger phrases. Selection test 21/24 vs 19/24 before.

## [0.1.1] - 2026-09-28

- **Fix**: documented that `ScheduleWakeup` requires `prompt` even for a long fallback heartbeat
  set while waiting on a background agent/workflow — omitting it caused a real "Failed to
  schedule check-in" error in a session that followed the prior wording.

## [0.1.0] - 2026-09-26

- **Feature**: new plugin. The `follow-through` skill catches the "I'll check back" / "still
  running, I'll report when it's done" anti-pattern — a promise to follow up on background or
  long-running work with no real mechanism behind it, so the promise is silently broken. Before
  making that promise, the skill requires naming which of a tracked background tool call, an
  explicitly scheduled wakeup, or a synchronous wait will actually resume the conversation.
