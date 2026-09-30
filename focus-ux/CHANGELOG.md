<!-- TDD-SKIP -->
## [Unreleased]

## [0.3.4] - 2026-09-30

- **Fix**: the checkpoint transcript tail reader (`hooks/focus_ux_transcript.py`) now grows its read window, up to 1 MiB, until it holds a complete final line, so a final assistant message over 16 KB no longer reads as empty and its trailing CHECKPOINT marker is found.
- **Fix**: `hooks/checkpoint_optin.py` ignores `[checkpoint-push]` inside inline code spans and fenced blocks, so an agent report that quotes the marker no longer opts an interactive session in.
- **Docs**: doc-consistency sweep (5 fixes): README pointer to `INTEROP.md`, and the unreproduced `${CLAUDE_PLUGIN_ROOT}` and token-cost claims reworded as reported/estimated.

## [0.3.3] - 2026-09-28

- **Fix**: the Focus output style's inline-picture script (`scripts/render_inline.py`, added in
  0.3.1) can now be located. The style named it with `${CLAUDE_PLUGIN_ROOT}`. That text was reported
  to appear in the model's context unexpanded (not reproduced in this repo), and the variable is unset in the Bash
  tool's shell, so the model had no way to resolve the path. A new `SessionStart`
  hook (`hooks/render_path_hint.py`) adds one context line with the script's absolute path,
  computed from the hook's own location. The style now points at that line and hand-drafts
  when it's absent. The hook fails open (prints nothing if the script is missing, always exits 0).
- **Test**: 7 new tests (5 for the hook, 2 structure checks that pin the registration and
  forbid an unexpanded variable in the style).

## [0.3.2] - 2026-09-28

- **Fix**: `checkpoint_push.py` no longer re-blocks every Stop when `CLAUDE_PLUGIN_DATA` is set but
  its state dir can't be written (full disk, read-only mount). Stop 1's nonce couldn't persist,
  so Stop 2 looked like a fresh Stop 1 and blocked again even after a valid ack. It now fails
  open (logs, no block), so a session can always stop (R9). Env-only opt-in with no plugin data
  is unchanged.
- **Fix**: `checkpoint_optin.py` clears a stale `pending` nonce on every new prompt. An ack turn
  that ended without a Stop (API error, cancel) used to leave it set, so the next real gate was
  consumed as Stop 2 and allowed through with no push.
- **Test**: 4 new tests for the two fixes, plus 3 marker-shape rejections (wrong field order,
  unquoted `need`, lone unterminated marker) in `test_checkpoint_markers.py`.
- **Chore**: `evals/evals.json` sample text no longer contains a `/Users/...` path, which the
  release validator flagged as a hardcoded path.

## [0.3.1] - 2026-09-27

- **Feature**: script-rendered inline visuals. New `scripts/render_inline.py` renders "Small"
  inline pictures (ranked/comparison table, progress map, timeline, flow/decision diagram) from
  a small JSON payload instead of the model hand-drafting ASCII art, mirroring
  `visual-brief`'s `build_brief.py` pattern for the "Big" Artifact path but stdout-only plain
  text (no shared code with `build_brief.py`, per design). `output-styles/focus.md`'s "Small"
  bullet now points at the script via `${CLAUDE_PLUGIN_ROOT}`; the Small/Big split itself is
  unchanged. 40 new tests in `tests/test_render_inline.py`.

## [0.3.0] - 2026-09-27

- **Feature**: checkpoint-push notifications. The plugin's first two hooks:
  `UserPromptSubmit` (`hooks/checkpoint_optin.py`) opts a session in on the `[checkpoint-push]`
  prompt marker or `FOCUS_UX_CHECKPOINT_PUSH=1`, and injects a standing rule so a Dispatch child
  pushes before `AskUserQuestion`. `Stop` (`hooks/checkpoint_push.py`) turns every Stop in an
  opted-in session into one extra classify-and-push turn (input / gate / done / step / none),
  guarded by a per-Stop nonce so the model's ack, not `stop_hook_active`, decides when the real
  stop happens (except when `CLAUDE_PLUGIN_DATA` isn't set, so there's no nonce to persist --
  there, `stop_hook_active` or any parseable ack alone is trusted instead, an accepted
  quiet-miss trade-off for that configuration; see `INTEROP.md`). Interactive and non-opted-in
  sessions pay only a cheap env/state check and stay silent. Any plugin can name a checkpoint
  with a `<!--CHECKPOINT:...-->` comment without depending on focus-ux being installed; see
  `INTEROP.md`. The ack line becomes the session's last visible message each time it fires --
  documented in `README.md` and `INTEROP.md`.

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
