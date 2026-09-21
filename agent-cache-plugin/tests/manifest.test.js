'use strict';
/**
 * Test Suite: Plugin Manifest Validation
 *
 * Verifies .claude-plugin/plugin.json conforms to the v2 architecture:
 * - Required fields: name, version, description, author, license
 * - hooks array: PreToolUse (Agent matcher) + PostToolUse (Agent matcher) + SessionEnd
 * - No commands array (unsupported by marketplace schema)
 * - No legacy map-singleton fields
 */

const fs = require('fs');
const path = require('path');

const manifestPath = path.resolve(__dirname, '..', '.claude-plugin', 'plugin.json');
const packageJsonPath = path.resolve(__dirname, '..', 'package.json');

let manifest, pkg;

beforeAll(() => {
  manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf-8'));
  pkg = JSON.parse(fs.readFileSync(packageJsonPath, 'utf-8'));
});

describe('Plugin Manifest (.claude-plugin/plugin.json)', () => {
  test('file exists and is valid JSON', () => {
    expect(fs.existsSync(manifestPath)).toBe(true);
    expect(manifest).toBeDefined();
  });

  describe('Required Fields', () => {
    test('has name', () => { expect(typeof manifest.name).toBe('string'); });
    test('has version matching semver', () => {
      expect(manifest.version).toMatch(/^\d+\.\d+\.\d+/);
    });
    test('has description', () => { expect(typeof manifest.description).toBe('string'); });
    test('has author.name', () => { expect(manifest.author.name.length).toBeGreaterThan(0); });
    test('has license', () => { expect(typeof manifest.license).toBe('string'); });
  });

  describe('Hooks (v2 architecture)', () => {
    test('hooks array exists', () => {
      expect(Array.isArray(manifest.hooks)).toBe(true);
    });

    test('has PostToolUse hook for post-agent-completion scoped to Agent', () => {
      const hook = manifest.hooks.find(
        h => h.event === 'PostToolUse' && h.script.includes('post-agent-completion')
      );
      expect(hook).toBeDefined();
      expect(hook.matcher).toBe('Agent');
    });

    test('has SessionEnd hook for cache-invalidation', () => {
      const hook = manifest.hooks.find(
        h => h.event === 'SessionEnd' && h.script.includes('cache-invalidation')
      );
      expect(hook).toBeDefined();
    });

    test('has a PreToolUse hook wired to pre-agent-spawn.js (M1 cleared)', () => {
      const preHook = manifest.hooks.find(h => h.event === 'PreToolUse');
      expect(preHook).toBeDefined();
      expect(preHook.script).toBe('hooks/pre-agent-spawn.js');
      expect(preHook.matcher).toBe('Agent');
    });
  });

  describe('Commands', () => {
    test('commands array is absent (unsupported by marketplace schema)', () => {
      expect(manifest.commands).toBeUndefined();
    });
  });

  describe('No legacy fields', () => {
    test('does NOT contain "agents" array', () => {
      expect(manifest).not.toHaveProperty('agents');
    });
    test('does NOT contain "skills" array', () => {
      expect(manifest).not.toHaveProperty('skills');
    });
  });
});
