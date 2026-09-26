<!-- TDD-SKIP -->
## [Unreleased]

## [0.1.0] - 2026-09-26

- **Feature**: new plugin. The `follow-through` skill catches the "I'll check back" / "still
  running, I'll report when it's done" anti-pattern — a promise to follow up on background or
  long-running work with no real mechanism behind it, so the promise is silently broken. Before
  making that promise, the skill requires naming which of a tracked background tool call, an
  explicitly scheduled wakeup, or a synchronous wait will actually resume the conversation.
