<!-- TDD-SKIP -->
## [Unreleased]

## [0.1.11] - 2026-09-22

- **Docs**: added a `## Quickstart` section, replacing a stale "will be added once published to a
  marketplace" placeholder (the `renfordn-plugins` marketplace already exists and is documented in
  `docs/install-and-verify.md`); clarifies this plugin's skill is distinct from Claude Code's own
  built-in `/code-review` command.
- **Chore**: `.claude-plugin/plugin.json`'s `first_class.declared_absent` extended to include
  `commands` and `agents` (was just `hooks`) — this plugin is deliberately a skill, not an agent
  (see README's "Why this is a skill, not an agent"), and adding its own slash command would
  collide with Claude Code's built-in `/code-review`.

## [0.1.10] - 2026-09-22

- **Fix**: `tests/test_interop_review_level.py` and `tests/test_skill_review_levels.py` hardcoded an absolute `/Users/jay.nelson/...` path to read `INTEROP.md`/`SKILL.md`, so both failed with `FileNotFoundError` on any other machine — confirmed breaking on GitHub Actions' CI runner. Made both paths relative to `Path(__file__)`.

## [0.1.9] - 2026-09-20

- **Docs**: promote unpromoted Unreleased CHANGELOG section to versioned [0.1.8] entry.

## [0.1.8] - 2026-09-20

- **Release**: bump version for public release pass.

## [0.1.1] - 2026-08-16

- Re-added `agent-ux:ux-agent` delegation for the review-dashboard, this time genuinely optional
  and not SDD-specific scaffolding (0.1.0 removed the prior, SDD-coupled version of this for
  exactly that reason — see its entry below; this doesn't reopen that decision). Delegates only
  when a caller supplies the new optional `phase_state` invocation parameter (a compact phase
  token like `agent-isdd`'s `Design`, or `TDD:green` — this skill has no phase concept of its own
  and never invents one) **and** `agent-ux:ux-agent` is installed this session; otherwise opens
  the Artifact directly, exactly as before, with identical findings and identical threshold logic
  either way. Marked `code-reviewer/skills/code-reviewer/SKILL.md`'s "Visual Review" section as
  the canonical definition of the 5-finding/1-file dashboard threshold that `agent-ux` and
  `agent-isdd`'s `doc-consistency-auditor` both mirror, closing a prior three-way duplication with
  no shared source. Added `Agent` to the skill's tool references, used only for this delegation.

## [0.1.0] - 2026-08-11

- Extracted from `spec-driven-development`'s internal `code-reviewer` skill into a standalone
  plugin, mirroring how `agent-nelly` (memory) and `agent-tdd` (implementer agents) were already
  pulled out of SDD.
- Replaced the hardcoded `~/.claude/sdd-memory/<project-slug>/spec/<feature-slug>/` persistence
  path with an optional caller-supplied **review state directory**. When omitted, the skill stays
  ephemeral for a single pass (same tier/decision rules, no persistence) instead of assuming SDD's
  memory tree exists.
- Removed the `ux-agent` delegation for the review-dashboard Artifact and for out-of-scope
  `spawn_task` flags — since this skill runs in the main thread (not an isolated subagent), it
  can call `Artifact`/`spawn_task` directly itself, so the delegation was SDD-specific
  scaffolding, not a hard requirement.
- Replaced the reference to `workflow-manager`'s Review State Repair rules with a self-contained
  staleness check the skill owns itself (diff-fingerprint mismatch → downgrade to
  `needs_detailed_review`), since no `workflow-manager` exists standalone.
- SDD's own internal copy of `code-reviewer` is unchanged for now — this plugin ships standalone
  alongside it rather than replacing it, matching the same migration decision already made for
  `agent-tdd` (full cutover deferred).
