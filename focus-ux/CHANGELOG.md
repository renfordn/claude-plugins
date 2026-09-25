<!-- TDD-SKIP -->
## [Unreleased]

## [0.2.0] - 2026-09-25

- **Feature**: Brief Board. One living Artifact page (`assets/brief-board.html`, `db` capability,
  owner-only writes) shows every brief newest first, grouped by day and filterable by project,
  and updates live. Adding a brief is one `ArtifactData` write of the JSON, with no HTML and no
  page publish. The skill then opens the board (`Artifact action: "open"`) so the new brief is
  seen. `build_brief.py --board` builds it, and `--check` validates a brief before writing.
- **Change**: the richer visual style replaces the plain template (IBM Plex; eyebrow + lede,
  tone pills, numbered phase stepper, ranked finding cards with "So what", status-dot `grid`
  section). One JS renderer now serves both the board and standalone pages (`build_brief.py`
  embeds the JSON), so there's one design to maintain. `assets/brief-template.html` is removed.

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
