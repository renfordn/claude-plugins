<!-- TDD-SKIP -->
# focus-ux — Interop

focus-ux has no agents. Its output style and skill cooperate with other plugins through
conventions only. It does have two hooks, `checkpoint_optin.py` (UserPromptSubmit) and
`checkpoint_push.py` (Stop), which make a Dispatch child session push a notification at input,
gate, done, and step checkpoints -- see below.

## Output style (always on)

The `Focus` style is forced while the plugin is enabled (`force-for-plugin: true`). It adds:

| Marker | When |
|---|---|
| `▸ Phase N/M · <name> — Step n/m` | Start of each update in multi-step work |
| `🎯 Goal:` | Start of a step |
| `Next:` | Before a batch of tool calls or any side effect |
| `✅ Done:` | End of a step |
| `✅ / ○ / ⚠` tick list | Recap at the end of a multi-step stretch |

**Plugins with their own progress line** (agent-isdd's SDD breadcrumb) keep printing it. Focus
adds the step counter after that breadcrumb instead of printing a second phase line. Don't
duplicate these markers in plugin instructions. Plugins state *what* the phases and steps are;
Focus decides *how* they're shown.

## visual-brief skill

Any plugin that ends in a large human-facing result (research summary, review findings, plan,
memory view) can say "present with `focus-ux:visual-brief`" instead of defining its own rendering.
The skill picks the shape (timeline, flow, map, matrix, chart) and where it goes (inline in chat,
plus a Brief Board entry when the result earns a page) itself. `code-reviewer:code-brief` stays the specialist for explaining code.

## Checkpoint-push notifications (opt-in, Dispatch children)

A Dispatch child session stays quiet by default. It opts a session in to proactive push
notifications with either the literal marker `[checkpoint-push]` anywhere in a prompt (sticky
for the rest of the session), or the environment variable `FOCUS_UX_CHECKPOINT_PUSH=1` (`=0`
forces it off, and off always wins). Once opted in, every Stop is turned into one extra model
turn: the child classifies why it stopped (input / gate / done / step / none) and, unless it's
routine, sends one `PushNotification` (loaded via `ToolSearch`) before acknowledging with a
`<!--CHECKPOINT-PUSHED:...-->` marker. **That ack turn becomes the session's last visible
message** -- expect one extra line after the real work in an opted-in Dispatch child.

Other plugins don't need focus-ux installed to cooperate. Any plugin can name a checkpoint by
putting one producer marker in its own output, right before it would otherwise go idle or wait
on the user:

```
<!--CHECKPOINT:type=(input|gate|done|step) name="<short-id>" need="<what's needed, ≤80 chars>"-->
```

focus-ux reads this as a hint for what to push and for R8 dedup (a repeated `name` from the same
still-unresolved gate pushes only once). If focus-ux isn't installed, or the session isn't opted
in, the marker is just an inert HTML comment.

**Without `CLAUDE_PLUGIN_DATA` set** (env-only opt-in, nothing to persist a per-Stop nonce
against), the ack no longer always decides: `checkpoint_push.py` instead trusts
`stop_hook_active` *or* any parseable `<!--CHECKPOINT-PUSHED:...-->` in the model's last turn,
either alone, as "this was already resolved" rather than re-blocking forever. That's a
deliberate quiet-miss trade-off for that configuration only -- with real plugin data present,
the nonce is always what decides, exactly as above.

## If focus-ux isn't installed

Nothing breaks. Callers fall back to their own formatting, and checkpoint-push producer markers
are inert comments with no effect.
