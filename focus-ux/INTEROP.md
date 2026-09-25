<!-- TDD-SKIP -->
# focus-ux — Interop

focus-ux has no agents, hooks, or events, so there's nothing to call. Other plugins cooperate with
it through conventions only.

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

## If focus-ux isn't installed

Nothing breaks. Callers fall back to their own formatting.
