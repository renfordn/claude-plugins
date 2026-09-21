<!-- TDD-SKIP -->
## [Unreleased]

## [0.1.1] - 2026-09-21

- **Trim**: shortened the `plugin-validator` agent's frontmatter `description` from ~600 to ~290 chars so it doesn't get truncated in plugin/agent pickers; full trigger phrasing stays in the "When this triggers" body section.

## [0.1.0] - 2026-09-21

- **Initial release**: extracted the `plugin-validator` agent from a standalone `~/.claude/skills/plugin-validator.md` file into a first-class plugin in this marketplace.
- **Fix**: the source file's YAML frontmatter was invalid — its `description` scalar was left unquoted and un-indented while embedding `<example>`/`user:`/`assistant:` blocks at column 0, which a YAML parser reads as sibling top-level keys rather than as part of the `description` value. Rewrote `description` as a single-line plain scalar and moved the example content into a "When this triggers" section in the agent body, matching this repo's existing agent conventions (see `agent-tdd/agents/agent-TDD.md`).
