# Inline patterns

These are ASCII/Unicode templates for the inline (small) medium. Adapt the labels, keep the
shape, and put each one inside a code block so the alignment holds. Box-drawing characters
(`─ │ ┌ ┐ └ ┘ ├ ┤ ▶ ▼`) render in every surface, including the terminal.

## Contents
- Timeline
- Flow
- Structure map
- Tree
- Comparison matrix
- Before → after
- Progress map
- Ranked findings
- Bar sketch

## Timeline

```
Sep 16 ──●── Sep 22 ──●── Sep 24 ──●── Sep 25 ──▶ next
     Phase 1 done   cache retired   summary cache   ① focus-ux
```

## Flow

```
 request ─▶ [cache lookup] ─ hit ─▶ return summary
                  │
                 miss
                  ▼
            [search repo] ─▶ [write summary] ─▶ return
```

## Structure map

```
┌────────────┐  brief   ┌────────────┐
│ agent-isdd │ ───────▶ │ agent-tdd  │
└─────┬──────┘          └─────┬──────┘
      │ memory                │ review
      ▼                       ▼
┌────────────┐          ┌──────────────┐
│ agent-nelly│          │ code-reviewer│
└────────────┘          └──────────────┘
```

## Tree

```
agent-nelly/
├── hooks/        ← runs automatically (session start/end, edits)
├── scripts/      ← index + weekly cleanup
└── agents/       ← brief, maintenance, planning, research
```

## Comparison matrix

Use a markdown table with a short verdict and reason in each cell. Don't use rating dots, because
they hide *why* an option wins or loses:

| | Speed | Token cost | Persists |
|---|---|---|---|
| Inline ASCII | ✅ instant | ✅ near zero | ❌ scrolls away |
| Widget | ⚠️ one tool call | ❌ large guide to load | ❌ chat only |
| **Artifact** ◀ reports | ⚠️ slowest | ⚠️ moderate | ✅ link you can reopen |

## Before → after

```
BEFORE                         AFTER
agent-cache (never stored) ─▶  nelly research digests
agent-ux (2K tokens/call)  ─▶  focus-ux output style (0 calls)
```

## Progress map

```
Phase 1 Requirements  ✅✅✅
Phase 2 Design        ✅✅▸○      ◀ you are here (step 3/4)
Phase 3 Tasks         ○○○○○
```

## Ranked findings

```
① ⚠ HIGH  Summaries keyed by absolute path → miss across machines   index.py:88
② ◐ MED   No hit counter → can't measure savings                     nelly_memory.py
③ ○ LOW   Stale entries only pruned weekly                           cleanup.py
```

## Bar sketch (quick proportions only, use `dataviz` for anything real)

```
hits    ████████████░░░░░░░░  61%
misses  ███████░░░░░░░░░░░░░  39%
```
