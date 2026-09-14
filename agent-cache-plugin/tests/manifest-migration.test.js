/**
 * Test Suite: Plugin Manifest Migration
 *
 * Verifies deprecation of root plugin.json and documentation of the migration
 * to .claude-plugin/plugin.json as the canonical manifest.
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

describe('Manifest Migration (root plugin.json → .claude-plugin/plugin.json)', () => {
  const rootPluginJsonPath = path.resolve(__dirname, '..', 'plugin.json');
  const canonicalPluginJsonPath = path.resolve(__dirname, '..', '.claude-plugin', 'plugin.json');
  const structureMdPath = path.resolve(__dirname, '..', 'STRUCTURE.md');
  const projectRoot = path.resolve(__dirname, '..');

  describe('Root plugin.json Deprecation', () => {
    test('root plugin.json should either be deleted OR contain deprecation comment', () => {
      const fileExists = fs.existsSync(rootPluginJsonPath);

      if (fileExists) {
        const content = fs.readFileSync(rootPluginJsonPath, 'utf-8');
        // If file exists, it should start with a deprecation comment
        expect(content).toMatch(/DEPRECATED|deprecated/i);
      }

      // If file exists, verify it's actually deprecated (not full manifest being used)
      // This allows either deletion or comment-only version
      expect(true).toBe(true); // This passes if file is deleted OR contains deprecation
    });

    test('canonical manifest should exist at .claude-plugin/plugin.json', () => {
      expect(fs.existsSync(canonicalPluginJsonPath)).toBe(true);
    });

    test('.claude-plugin/plugin.json should be valid JSON', () => {
      expect(() => {
        JSON.parse(fs.readFileSync(canonicalPluginJsonPath, 'utf-8'));
      }).not.toThrow();
    });
  });

  describe('Migration Documentation in STRUCTURE.md', () => {
    let structureContent;

    beforeAll(() => {
      structureContent = fs.readFileSync(structureMdPath, 'utf-8');
    });

    test('STRUCTURE.md should contain reference to .claude-plugin/plugin.json', () => {
      expect(structureContent).toMatch(/\.claude-plugin\/plugin\.json/);
    });

    test('STRUCTURE.md should mention manifest migration', () => {
      expect(structureContent).toMatch(/[Mm]igration|[Mm]igrated/);
    });

    test('STRUCTURE.md should explain why migration happened', () => {
      expect(structureContent).toMatch(/[Cc]laude [Cc]ode|discovery|canonical/i);
    });

    test('STRUCTURE.md should clarify .claude-plugin/plugin.json is canonical', () => {
      expect(structureContent).toMatch(/canonical.*\.claude-plugin|\.claude-plugin.*canonical/i);
    });
  });

  describe('Code Import Verification', () => {
    test('no code files should import root plugin.json', () => {
      let output;
      try {
        // Search for actual require/import statements (not comments) importing plugin.json
        // Exclude test files and .claude-plugin directory
        output = execSync(`grep -r "^[^/]*require\\|^[^/]*import" --include="*.js" --include="*.ts" "${projectRoot}" | grep "plugin\\.json" | grep -v "\.claude-plugin" | grep -v "test\\.js" | grep -v "tests/" 2>&1`, { encoding: 'utf-8' });
      } catch (e) {
        // grep returns exit code 1 if no matches found
        output = '';
      }

      // Should be empty - no production code should import root plugin.json
      const lines = output.trim().split('\n').filter(l => l.length > 0);

      expect(lines).toEqual([]);
    });
  });
});
