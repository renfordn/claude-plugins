'use strict';
/**
 * Test Suite: Plugin Manifest Validation
 *
 * Verifies .claude-plugin/plugin.json conforms to the v2 architecture:
 * - Required fields: name, version, description, author, license
 * - No inline "hooks" array (Claude Code never reads one there -- see
 *   hooks/hooks.json and hook-wiring.test.js for the real, F-03-fixed config)
 * - No commands array (unsupported by marketplace schema)
 * - No legacy map-singleton fields
 */

const fs = require('fs');
const path = require('path');

const manifestPath = path.resolve(__dirname, '..', '.claude-plugin', 'plugin.json');
const packageJsonPath = path.resolve(__dirname, '..', 'package.json');
const hooksJsonPath = path.resolve(__dirname, '..', 'hooks', 'hooks.json');

let manifest, pkg, hooksConfig;

beforeAll(() => {
  manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf-8'));
  pkg = JSON.parse(fs.readFileSync(packageJsonPath, 'utf-8'));
  hooksConfig = JSON.parse(fs.readFileSync(hooksJsonPath, 'utf-8')).hooks;
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
    // Claude Code auto-loads a plugin's hook config from hooks/hooks.json (in
    // Claude Code's record format, {"hooks": {"<Event>": [...]}}) -- it never
    // reads an inline "hooks" array from plugin.json itself (that shape is
    // silently ignored at runtime; see hook-wiring.test.js's "No Competing
    // Hook Config" suite and F-03 in the 2026-09-21 GTM review).
    test('plugin.json does not declare its own inline hooks array', () => {
      expect(manifest.hooks).toBeUndefined();
    });

    test('has PostToolUse hook for post-agent-completion scoped to Agent', () => {
      const commands = hooksConfig.PostToolUse.flatMap(e => e.hooks.map(h => h.command));
      expect(commands.some(c => c.includes('post-agent-completion'))).toBe(true);
      expect(hooksConfig.PostToolUse[0].matcher).toBe('Agent');
    });

    test('has SessionEnd hook for cache-invalidation', () => {
      const commands = hooksConfig.SessionEnd.flatMap(e => e.hooks.map(h => h.command));
      expect(commands.some(c => c.includes('cache-invalidation'))).toBe(true);
    });

    test('has a PreToolUse hook wired to pre-agent-spawn.js scoped to Agent', () => {
      const commands = hooksConfig.PreToolUse.flatMap(e => e.hooks.map(h => h.command));
      expect(commands.some(c => c.includes('pre-agent-spawn.js'))).toBe(true);
      expect(hooksConfig.PreToolUse[0].matcher).toBe('Agent');
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
