/**
 * Test Suite: Hook Wiring Configuration (hooks.json)
 * Tests that hooks.json properly maps Claude Code hook events to hook scripts.
 *
 * Rewritten 2026-09-21 (F-03): the 2026-09-15 rewrite asserted `.claude-plugin/hooks.json`
 * as canonical, but Claude Code only auto-loads a plugin's hook config from `hooks/hooks.json`
 * (or a path/object under `plugin.json`'s own `hooks` key) -- it never reads
 * `.claude-plugin/hooks.json`. Combined with `plugin.json`'s now-removed inline `hooks` array
 * (a shape `claude plugin validate` flagged as "unknown hook event; entry ignored at runtime"),
 * this meant none of this plugin's hooks were ever wired up in a real install, while this
 * suite stayed green because it validated the wrong file. The record-format config itself was
 * already correct; only its location (and plugin.json's competing array) were wrong. See
 * STRUCTURE.md and https://github.com/renfordn/claude-plugins -- agent-isdd, agent-tdd, and
 * plugin-orchestrator all use the same `hooks/hooks.json` convention this now matches.
 */

const fs = require('fs');
const path = require('path');

describe('Hook Wiring Configuration', () => {
  const pluginRoot = path.join(__dirname, '..');
  const hooksJsonPath = path.join(pluginRoot, 'hooks/hooks.json');
  let hooksConfig;

  describe('No Competing Hook Config', () => {
    test('.claude-plugin/hooks.json should not exist (Claude Code never reads it)', () => {
      expect(fs.existsSync(path.join(pluginRoot, '.claude-plugin/hooks.json'))).toBe(false);
    });

    test('plugin.json should not declare its own inline "hooks" array', () => {
      const manifest = JSON.parse(
        fs.readFileSync(path.join(pluginRoot, '.claude-plugin/plugin.json'), 'utf8')
      );
      expect(manifest.hooks).toBeUndefined();
    });
  });

  describe('File and JSON Validity', () => {
    test('.claude-plugin/hooks.json file should exist', () => {
      expect(fs.existsSync(hooksJsonPath)).toBe(true);
    });

    test('hooks.json should be valid JSON', () => {
      const fileContent = fs.readFileSync(hooksJsonPath, 'utf8');
      expect(() => {
        hooksConfig = JSON.parse(fileContent);
      }).not.toThrow();
    });

    test('hooks.json should use the record format ({"hooks": {...}}), not a bare array', () => {
      const fileContent = fs.readFileSync(hooksJsonPath, 'utf8');
      const parsed = JSON.parse(fileContent);
      expect(Array.isArray(parsed)).toBe(false);
      expect(parsed).toHaveProperty('hooks');
      expect(Array.isArray(parsed.hooks)).toBe(false);
    });
  });

  describe('Event Mappings', () => {
    beforeEach(() => {
      const fileContent = fs.readFileSync(hooksJsonPath, 'utf8');
      hooksConfig = JSON.parse(fileContent).hooks;
    });

    test('should contain PreToolUse event mapping', () => {
      expect(hooksConfig).toHaveProperty('PreToolUse');
      expect(Array.isArray(hooksConfig.PreToolUse)).toBe(true);
    });

    test('should contain PostToolUse event mapping', () => {
      expect(hooksConfig).toHaveProperty('PostToolUse');
      expect(Array.isArray(hooksConfig.PostToolUse)).toBe(true);
    });

    test('should contain SessionEnd event mapping', () => {
      expect(hooksConfig).toHaveProperty('SessionEnd');
      expect(Array.isArray(hooksConfig.SessionEnd)).toBe(true);
    });
  });

  describe('Matcher Scoping', () => {
    beforeEach(() => {
      const fileContent = fs.readFileSync(hooksJsonPath, 'utf8');
      hooksConfig = JSON.parse(fileContent).hooks;
    });

    // pre-agent-spawn.js / post-agent-completion.js only make sense for agent
    // spawns (they key cache lookups on toolName='Agent') -- an unscoped
    // matcher would fire on every single tool call in every session.
    test('PreToolUse should be scoped to the Agent tool', () => {
      expect(hooksConfig.PreToolUse[0].matcher).toBe('Agent');
    });

    test('PostToolUse should be scoped to the Agent tool', () => {
      expect(hooksConfig.PostToolUse[0].matcher).toBe('Agent');
    });
  });

  describe('Script References', () => {
    function commandsFor(event) {
      return hooksConfig[event].flatMap((entry) => entry.hooks.map((h) => h.command));
    }

    beforeEach(() => {
      const fileContent = fs.readFileSync(hooksJsonPath, 'utf8');
      hooksConfig = JSON.parse(fileContent).hooks;
    });

    test('PreToolUse should invoke pre-agent-spawn.js', () => {
      expect(commandsFor('PreToolUse').some((c) => c.includes('pre-agent-spawn.js'))).toBe(true);
    });

    test('PostToolUse should invoke post-agent-completion.js', () => {
      expect(commandsFor('PostToolUse').some((c) => c.includes('post-agent-completion.js'))).toBe(true);
    });

    test('SessionEnd should invoke cache-invalidation.js', () => {
      expect(commandsFor('SessionEnd').some((c) => c.includes('cache-invalidation.js'))).toBe(true);
    });

    test('every referenced script should exist on disk', () => {
      const scriptNames = ['pre-agent-spawn.js', 'post-agent-completion.js', 'cache-invalidation.js'];
      scriptNames.forEach((name) => {
        expect(fs.existsSync(path.join(pluginRoot, 'hooks', name))).toBe(true);
      });
    });
  });

  describe('Schema Validation', () => {
    beforeEach(() => {
      const fileContent = fs.readFileSync(hooksJsonPath, 'utf8');
      hooksConfig = JSON.parse(fileContent).hooks;
    });

    test('config should only contain expected event keys', () => {
      const expectedKeys = ['PreToolUse', 'PostToolUse', 'SessionEnd'];
      Object.keys(hooksConfig).forEach((key) => {
        expect(expectedKeys).toContain(key);
      });
    });

    test('every hook entry should have type "command" and a non-empty command string', () => {
      Object.values(hooksConfig).forEach((entries) => {
        entries.forEach((entry) => {
          entry.hooks.forEach((h) => {
            expect(h.type).toBe('command');
            expect(typeof h.command).toBe('string');
            expect(h.command.length).toBeGreaterThan(0);
          });
        });
      });
    });
  });
});
