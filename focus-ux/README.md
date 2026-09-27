<!-- TDD-SKIP -->
# Focus UX

ADHD-friendly presentation for Claude Code. It has no agents or subagent calls: the output style
and skill run on the main thread, so they cost close to nothing per reply. (The per-call subagent
cost is what retired `agent-ux`.) It does have two small hooks for opt-in Dispatch notifications.

| Part | What it does | When it applies |
|---|---|---|
| `output-styles/focus.md` (**Focus**) | Phase/step counters (`▸ Phase 2/4 · Design — Step 3/5`), a `🎯 Goal:` line when a step starts, a `Next:` line before actions, a `✅ Done:` line when a step ends, and inline pictures for small shapes | Every reply. `force-for-plugin: true` turns it on whenever the plugin is enabled, and `keep-coding-instructions: true` keeps Claude Code's normal coding behaviour |
| `skills/visual-brief` | Turns big findings into one headline, one picture (timeline, flow, map, matrix, chart), and 3–5 callouts. The chat always gets a text summary. A page is added only when it earns its cost, added to the **Brief Board** (one living Artifact page) with a single database write of small JSON | Big results: research, reviews, plans, comparisons, recaps |
| `hooks/checkpoint_optin.py` + `hooks/checkpoint_push.py` (**checkpoint-push**) | Makes a Dispatch child session send one push notification when it needs input, hits a workflow gate, finishes, or idles after a significant step | Only sessions that opt in with `[checkpoint-push]` in a prompt or `FOCUS_UX_CHECKPOINT_PUSH=1`. Every other session stays silent |

## Quickstart

Add the plugin to your Claude account (it runs as `focus-ux@inline`). The Focus style is then
active automatically. To turn it off, disable the plugin.

## Checkpoint-push notifications

If you're running a Dispatch (Cowork-mode) child session and want it to proactively tell you
when it needs input, hits a gate, finishes, or idles after a step, put `[checkpoint-push]`
anywhere in its starting prompt (or set `FOCUS_UX_CHECKPOINT_PUSH=1` for the child). Interactive
sessions stay quiet unless you opt them in the same way. Once opted in, expect one extra
`<!--CHECKPOINT-PUSHED:...-->` line as the session's last message each time it stops -- that's
the hook's ack turn, not an error. See `INTEROP.md` for the full contract and how other plugins
can name a checkpoint.

## Relationship to other plugins

- **agent-isdd** keeps its own SDD breadcrumb (`agent-isdd/references/ux-conventions.md`). Focus puts its
  step counter after that breadcrumb instead of printing a second phase line.
- **code-reviewer:code-brief** stays the specialist for "explain how this code works".
  `visual-brief` covers everything else that's big enough to need a picture.
