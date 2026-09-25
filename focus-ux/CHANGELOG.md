<!-- TDD-SKIP -->
## [Unreleased]

## [0.1.0] - 2026-09-25

- **Feature**: new plugin. The `Focus` output style (forced on, keeps coding instructions) adds
  phase/step counters, goal/next/done lines, and pictures-first replies. The `visual-brief` skill
  adds shape-first visuals for big findings, choosing inline, widget, or Artifact by size, with
  inline ASCII templates in `references/patterns.md`.
- **Feature**: the chat always carries the summary (headline, inline picture, top 3 points,
  decision). An Artifact is built only when it adds value: something to revisit, more than 7
  items, a real chart or branching flow, or on request. Pages are rendered from ~1-2KB of JSON
  by `scripts/build_brief.py` into a pre-designed template (`assets/brief-template.html`),
  instead of 10-16KB of hand-written HTML. Briefs with a `diagram` section load a pinned
  mermaid build from cdnjs (theme follows light/dark), so diagrams render in any viewer.
