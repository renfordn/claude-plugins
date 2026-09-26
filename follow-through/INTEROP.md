<!-- TDD-SKIP -->
# follow-through — Interop

follow-through has no agents, hooks, or events, so there's nothing to call. It's a single
behavioral skill that any other plugin's long-running work (a background test run, a subagent, a
workflow) can rely on implicitly: it governs how Claude talks about in-flight work, not what the
work is.

## If follow-through isn't installed

Nothing breaks. Other plugins' background/async work still runs the same way; this plugin only
changes the wording and discipline around promising to follow up on it.
