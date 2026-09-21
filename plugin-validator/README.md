# Plugin Validator

A standalone Claude Code agent that validates plugin structure, manifest correctness, and component files (commands, agents, skills, hooks, MCP config) before publishing.

## What's in this plugin

- **`plugin-validator`** agent — checks `.claude-plugin/plugin.json`, `commands/`, `agents/`, `skills/`, `hooks/hooks.json`, and MCP configuration for structural correctness, naming conventions, and common anti-patterns (including the malformed-YAML-frontmatter failure mode this plugin itself was extracted from — see CHANGELOG). Returns a categorized report (critical / warning / positive findings) with fix suggestions.

## Usage

Ask Claude to validate a plugin ("validate my plugin", "check plugin structure before I publish"), or just create/edit a plugin component — the agent is written to trigger proactively after you add or change a command, agent, skill, or hook file.

## License

See [LICENSE](LICENSE).
