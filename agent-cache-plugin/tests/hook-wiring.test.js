/**
 * Test Suite: Hook Wiring Configuration (hooks.json)
 * Tests that hooks.json properly maps Claude Code hook events to hook scripts
 */

const fs = require('fs');
const path = require('path');

describe('Hook Wiring Configuration', () => {
  const hooksJsonPath = path.join(__dirname, '../hooks/hooks.json');
  let hooksConfig;

  describe('File and JSON Validity', () => {
    test('hooks.json file should exist', () => {
      expect(fs.existsSync(hooksJsonPath)).toBe(true);
    });

    test('hooks.json should be valid JSON', () => {
      const fileContent = fs.readFileSync(hooksJsonPath, 'utf8');
      expect(() => {
        hooksConfig = JSON.parse(fileContent);
      }).not.toThrow();
    });
  });

  describe('Event Mappings', () => {
    beforeEach(() => {
      const fileContent = fs.readFileSync(hooksJsonPath, 'utf8');
      hooksConfig = JSON.parse(fileContent);
    });

    test('should contain PreToolUse event mapping', () => {
      expect(hooksConfig).toHaveProperty('PreToolUse');
      expect(hooksConfig.PreToolUse).toBeDefined();
    });

    test('should contain PostToolUse event mapping', () => {
      expect(hooksConfig).toHaveProperty('PostToolUse');
      expect(hooksConfig.PostToolUse).toBeDefined();
    });

    test('should contain SessionEnd event mapping', () => {
      expect(hooksConfig).toHaveProperty('SessionEnd');
      expect(hooksConfig.SessionEnd).toBeDefined();
    });

    test('PreToolUse should map to pre-agent-spawn.js', () => {
      expect(hooksConfig.PreToolUse.script).toBe('hooks/pre-agent-spawn.js');
    });

    test('PostToolUse should map to post-agent-completion.js', () => {
      expect(hooksConfig.PostToolUse.script).toBe('hooks/post-agent-completion.js');
    });

    test('SessionEnd should map to cache-invalidation.js', () => {
      expect(hooksConfig.SessionEnd.script).toBe('hooks/cache-invalidation.js');
    });
  });

  describe('Script References', () => {
    beforeEach(() => {
      const fileContent = fs.readFileSync(hooksJsonPath, 'utf8');
      hooksConfig = JSON.parse(fileContent);
    });

    test('PreToolUse script should reference existing file', () => {
      const scriptPath = path.join(
        __dirname,
        '../' + hooksConfig.PreToolUse.script
      );
      expect(fs.existsSync(scriptPath)).toBe(true);
    });

    test('PostToolUse script should reference existing file', () => {
      const scriptPath = path.join(
        __dirname,
        '../' + hooksConfig.PostToolUse.script
      );
      expect(fs.existsSync(scriptPath)).toBe(true);
    });

    test('SessionEnd script should reference existing file', () => {
      const scriptPath = path.join(
        __dirname,
        '../' + hooksConfig.SessionEnd.script
      );
      expect(fs.existsSync(scriptPath)).toBe(true);
    });
  });

  describe('Documentation', () => {
    beforeEach(() => {
      const fileContent = fs.readFileSync(hooksJsonPath, 'utf8');
      hooksConfig = JSON.parse(fileContent);
    });

    test('PreToolUse should have description field', () => {
      expect(hooksConfig.PreToolUse).toHaveProperty('description');
      expect(typeof hooksConfig.PreToolUse.description).toBe('string');
      expect(hooksConfig.PreToolUse.description.length).toBeGreaterThan(0);
    });

    test('PostToolUse should have description field', () => {
      expect(hooksConfig.PostToolUse).toHaveProperty('description');
      expect(typeof hooksConfig.PostToolUse.description).toBe('string');
      expect(hooksConfig.PostToolUse.description.length).toBeGreaterThan(0);
    });

    test('SessionEnd should have description field', () => {
      expect(hooksConfig.SessionEnd).toHaveProperty('description');
      expect(typeof hooksConfig.SessionEnd.description).toBe('string');
      expect(hooksConfig.SessionEnd.description.length).toBeGreaterThan(0);
    });

    test('PreToolUse description should relate to cache lookup', () => {
      const desc = hooksConfig.PreToolUse.description.toLowerCase();
      expect(desc).toMatch(/cache|lookup|search/);
    });

    test('PostToolUse description should relate to storage/metrics', () => {
      const desc = hooksConfig.PostToolUse.description.toLowerCase();
      expect(desc).toMatch(/store|cache|metric|completion|result/);
    });

    test('SessionEnd description should relate to cleanup/invalidation', () => {
      const desc = hooksConfig.SessionEnd.description.toLowerCase();
      expect(desc).toMatch(/cleanup|invalidat|evict|session|close|ttl/);
    });
  });

  describe('Schema Validation', () => {
    beforeEach(() => {
      const fileContent = fs.readFileSync(hooksJsonPath, 'utf8');
      hooksConfig = JSON.parse(fileContent);
    });

    test('each event should have script property as string', () => {
      const events = ['PreToolUse', 'PostToolUse', 'SessionEnd'];
      events.forEach((event) => {
        expect(typeof hooksConfig[event].script).toBe('string');
        expect(hooksConfig[event].script.length).toBeGreaterThan(0);
      });
    });

    test('each event should have description property as string', () => {
      const events = ['PreToolUse', 'PostToolUse', 'SessionEnd'];
      events.forEach((event) => {
        expect(typeof hooksConfig[event].description).toBe('string');
        expect(hooksConfig[event].description.length).toBeGreaterThan(0);
      });
    });

    test('scripts should end with .js extension', () => {
      const events = ['PreToolUse', 'PostToolUse', 'SessionEnd'];
      events.forEach((event) => {
        expect(hooksConfig[event].script).toMatch(/\.js$/);
      });
    });

    test('should not have extra properties beyond script and description', () => {
      const events = ['PreToolUse', 'PostToolUse', 'SessionEnd'];
      const allowedProps = ['script', 'description'];
      events.forEach((event) => {
        const props = Object.keys(hooksConfig[event]);
        props.forEach((prop) => {
          expect(allowedProps).toContain(prop);
        });
      });
    });

    test('config should only contain expected event keys', () => {
      const expectedKeys = ['PreToolUse', 'PostToolUse', 'SessionEnd'];
      const actualKeys = Object.keys(hooksConfig);
      actualKeys.forEach((key) => {
        expect(expectedKeys).toContain(key);
      });
    });
  });

  describe('Event Payload Documentation', () => {
    beforeEach(() => {
      const fileContent = fs.readFileSync(hooksJsonPath, 'utf8');
      hooksConfig = JSON.parse(fileContent);
    });

    test('should document PreToolUse event payload expectations', () => {
      // PreToolUse should have payload documentation in the config
      const event = hooksConfig.PreToolUse;
      expect(event).toBeDefined();
      expect(event.description).toContain('cache lookup');
    });

    test('should document PostToolUse event payload expectations', () => {
      // PostToolUse should have payload documentation
      const event = hooksConfig.PostToolUse;
      expect(event).toBeDefined();
      expect(event.description).toContain('tool completion');
    });

    test('should document SessionEnd event payload expectations', () => {
      // SessionEnd should have payload documentation
      const event = hooksConfig.SessionEnd;
      expect(event).toBeDefined();
      expect(event.description).toContain('session close');
    });
  });
});
