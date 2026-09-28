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
forces it off, and off always wins). The prompt marker is only sticky when `CLAUDE_PLUGIN_DATA`
is set; without it, use the environment variable. On opt-in the session also gets a standing
rule, once per session, to send one push before it asks you a decision question. Once opted in, a Stop that will push (not a repeat of the same unresolved gate, and not the
fail-open case below) is turned into one extra model turn: the child classifies why it stopped (input / gate / done / step / none) and, unless it's
routine, sends one `PushNotification` (loaded via `ToolSearch`) before acknowledging with a
`<!--CHECKPOINT-PUSHED:...-->` marker. **That ack turn becomes the session's last visible
message** -- expect one extra line after the real work in an opted-in Dispatch child.

Other plugins don't need focus-ux installed to cooperate. Any plugin can name a checkpoint by
putting one producer marker in its own output, right before it would otherwise go idle or wait
on the user:

```
<!--CHECKPOINT:type=(input|gate|done|step) name="<short-id>" need="<what's needed, ≤80 chars>"-->
```

The fields must appear in exactly that order, and `name` must match `[a-z0-9:_-]{1,48}`
(lowercase, digits, `:` `_` `-`) with `need` in double quotes. A marker that breaks any of
this is silently ignored, not rejected, so check it against `parse_producer` in
`hooks/focus_ux_transcript.py`. Only the last marker in the final message is read.

focus-ux reads this as a hint for what to push and for R8 dedup (a repeated `name` from the same
still-unresolved gate pushes only once). If focus-ux isn't installed, or the session isn't opted
in, the marker is just an inert HTML comment.

**Without `CLAUDE_PLUGIN_DATA` set** (env-only opt-in, nothing to persist a per-Stop nonce
against), the ack no longer always decides: `checkpoint_push.py` instead trusts
`stop_hook_active` *or* any parseable `<!--CHECKPOINT-PUSHED:...-->` in the model's last turn,
either alone, as "this was already resolved" rather than re-blocking forever. That's a
deliberate quiet-miss trade-off for that configuration only -- with real plugin data present,
the nonce is always what decides, exactly as above.

**If the state can't be saved** (`CLAUDE_PLUGIN_DATA` is set but its folder isn't writable, for
example on a full disk), Stop 1 fails open instead of blocking: with no nonce persisted, the
next Stop couldn't be told apart from a fresh Stop 1 and the session would re-block on every
Stop, even after a valid ack. Expect no push in that environment; the failure is logged. A new
prompt also clears any leftover nonce, so an interrupted ack turn never swallows the next
real checkpoint.

## If focus-ux isn't installed

Nothing breaks. Callers fall back to their own formatting, and checkpoint-push producer markers
are inert comments with no effect.
