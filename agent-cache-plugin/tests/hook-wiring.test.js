/**
 * Test Suite: Hook Wiring Configuration (hooks.json)
 * Tests that hooks.json properly maps Claude Code hook events to hook scripts.
 *
 * Rewritten 2026-09-15: the previous version of this suite tested a file at
 * `hooks/hooks.json` (which has never existed in this plugin) against a flat
 * `{PreToolUse: {script, description}}` schema that Claude Code has never used.
 * The real config lives at `.claude-plugin/hooks.json` in Claude Code's actual
 * record format: `{"hooks": {"<Event>": [{"matcher"?, "hooks": [{"type","command"}]}]}}`.
 * Every test below was failing (or would have, the moment it ran) against the
 * real file; this rewrite validates the file that actually exists.
 */

const fs = require('fs');
const path = require('path');

describe('Hook Wiring Configuration', () => {
  const pluginRoot = path.join(__dirname, '..');
  const hooksJsonPath = path.join(pluginRoot, '.claude-plugin/hooks.json');
  let hooksConfig;

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
