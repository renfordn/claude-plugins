<!-- TDD-SKIP -->
# Follow Through

A single skill, no agents, hooks, or subagent calls. It stops Claude from writing a "check back" /
"I'll report when it's done" promise about work that isn't finished unless there's an actual
mechanism (a tracked background tool call, a scheduled wakeup, or a synchronous wait) that will
bring it back to the conversation and deliver the result.

## Why

The recurring failure this fixes: Claude says "Working on it, I'll update you when it's done,"
then later "Still running, I'll check back in a moment" — and never actually reports back, because
nothing was wired up to resume it. The user is left with a stalled conversation. The skill makes
the check explicit: before promising a follow-up, name the mechanism that will fire it, or don't
make the promise.

## Quickstart

Add the plugin to your Claude account (it runs as `follow-through@inline`). The skill triggers on
its own whenever Claude is about to write a future-tense follow-up promise, or right after it
starts a background/long-running operation.
