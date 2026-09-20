'use strict';
/**
 * Test Suite: Plugin Manifest Validation
 *
 * Verifies .claude-plugin/plugin.json conforms to the v2 architecture:
 * - Required fields: name, version, description, author, license
 * - hooks array: PostToolUse entries present; no PreToolUse entry
 * - commands array: cache-status, cache-clear, cache-config present
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

    test('has PostToolUse hook for post-agent-completion', () => {
      const hook = manifest.hooks.find(
        h => h.event === 'PostToolUse' && h.script.includes('post-agent-completion')
      );
      expect(hook).toBeDefined();
    });

    test('has PostToolUse hook for cache-invalidation', () => {
      const hook = manifest.hooks.find(
        h => h.event === 'PostToolUse' && h.script.includes('cache-invalidation')
      );
      expect(hook).toBeDefined();
    });

    test('does NOT have a PreToolUse hook (M1 gate not cleared)', () => {
      const preHook = manifest.hooks.find(h => h.event === 'PreToolUse');
      expect(preHook).toBeUndefined();
    });
  });

  describe('Commands', () => {
    test('commands array exists', () => {
      expect(Array.isArray(manifest.commands)).toBe(true);
    });

    test('includes cache-status', () => {
      expect(manifest.commands.some(c => c.name === 'cache-status')).toBe(true);
    });

    test('includes cache-clear', () => {
      expect(manifest.commands.some(c => c.name === 'cache-clear')).toBe(true);
    });

    test('includes cache-config', () => {
      expect(manifest.commands.some(c => c.name === 'cache-config')).toBe(true);
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
