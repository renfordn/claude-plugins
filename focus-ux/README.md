<!-- TDD-SKIP -->
# Focus UX

ADHD-friendly presentation for Claude Code. It has no agents, hooks, or subagent calls:
everything runs on the main thread, so it costs close to nothing per reply. (The per-call subagent
cost is what retired `agent-ux`.)

| Part | What it does | When it applies |
|---|---|---|
| `output-styles/focus.md` (**Focus**) | Phase/step counters (`▸ Phase 2/4 · Design — Step 3/5`), a `🎯 Goal:` line when a step starts, a `Next:` line before actions, a `✅ Done:` line when a step ends, and inline pictures for small shapes | Every reply. `force-for-plugin: true` turns it on whenever the plugin is enabled, and `keep-coding-instructions: true` keeps Claude Code's normal coding behaviour |
| `skills/visual-brief` | Turns big findings into one headline, one picture (timeline, flow, map, matrix, chart), and 3–5 callouts. The chat always gets a text summary. A page is added only when it earns its cost, rendered from small JSON by `scripts/build_brief.py` into a bundled template | Big results: research, reviews, plans, comparisons, recaps |

## Quickstart

Add the plugin to your Claude account (it runs as `focus-ux@inline`). The Focus style is then
active automatically. To turn it off, disable the plugin.

## Relationship to other plugins

- **agent-isdd** keeps its own SDD breadcrumb (`references/ux-conventions.md`). Focus puts its
  step counter after that breadcrumb instead of printing a second phase line.
- **code-reviewer:code-brief** stays the specialist for "explain how this code works".
  `visual-brief` covers everything else that's big enough to need a picture.
