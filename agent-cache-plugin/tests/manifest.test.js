/**
 * Test Suite: Plugin Manifest Validation
 *
 * Verifies that .claude-plugin/plugin.json conforms to Claude Code plugin spec:
 * - File exists and is valid JSON
 * - Contains required fields: name, version, description, author, license
 * - Version matches package.json version
 * - Excludes non-standard fields: agents[], skills[], hooks{}
 * - Validates against Claude Code plugin schema
 */

const fs = require('fs');
const path = require('path');

describe('Plugin Manifest (.claude-plugin/plugin.json)', () => {
  const manifestPath = path.resolve(__dirname, '..', '.claude-plugin', 'plugin.json');
  const packageJsonPath = path.resolve(__dirname, '..', 'package.json');

  let manifestContent;
  let packageContent;

  // Parse package.json to get expected version
  beforeAll(() => {
    const packageData = fs.readFileSync(packageJsonPath, 'utf-8');
    packageContent = JSON.parse(packageData);
  });

  describe('File Existence and Format', () => {
    test('should exist at .claude-plugin/plugin.json', () => {
      expect(fs.existsSync(manifestPath)).toBe(true);
    });

    test('should be valid JSON', () => {
      expect(() => {
        manifestContent = JSON.parse(fs.readFileSync(manifestPath, 'utf-8'));
      }).not.toThrow();
    });
  });

  describe('Required Fields', () => {
    beforeAll(() => {
      if (fs.existsSync(manifestPath)) {
        manifestContent = JSON.parse(fs.readFileSync(manifestPath, 'utf-8'));
      }
    });

    test('should contain "name" field', () => {
      expect(manifestContent).toHaveProperty('name');
      expect(typeof manifestContent.name).toBe('string');
      expect(manifestContent.name.length).toBeGreaterThan(0);
    });

    test('should contain "version" field', () => {
      expect(manifestContent).toHaveProperty('version');
      expect(typeof manifestContent.version).toBe('string');
      expect(manifestContent.version).toMatch(/^\d+\.\d+\.\d+/);
    });

    test('should contain "description" field', () => {
      expect(manifestContent).toHaveProperty('description');
      expect(typeof manifestContent.description).toBe('string');
      expect(manifestContent.description.length).toBeGreaterThan(0);
    });

    test('should contain "author" field', () => {
      expect(manifestContent).toHaveProperty('author');
      expect(typeof manifestContent.author).toBe('object');
      expect(manifestContent.author.name.length).toBeGreaterThan(0);
    });

    test('should contain "license" field', () => {
      expect(manifestContent).toHaveProperty('license');
      expect(typeof manifestContent.license).toBe('string');
      expect(manifestContent.license.length).toBeGreaterThan(0);
    });
  });

  describe('Version Synchronization', () => {
    beforeAll(() => {
      if (fs.existsSync(manifestPath)) {
        manifestContent = JSON.parse(fs.readFileSync(manifestPath, 'utf-8'));
      }
    });

    test('version should match package.json version', () => {
      expect(manifestContent.version).toBe(packageContent.version);
    });
  });

  describe('Non-Standard Fields Exclusion', () => {
    beforeAll(() => {
      if (fs.existsSync(manifestPath)) {
        manifestContent = JSON.parse(fs.readFileSync(manifestPath, 'utf-8'));
      }
    });

    test('should NOT contain "agents" field', () => {
      expect(manifestContent).not.toHaveProperty('agents');
    });

    test('should NOT contain "skills" field', () => {
      expect(manifestContent).not.toHaveProperty('skills');
    });

    test('should NOT contain "hooks" field', () => {
      expect(manifestContent).not.toHaveProperty('hooks');
    });
  });

  describe('Schema Validation', () => {
    beforeAll(() => {
      if (fs.existsSync(manifestPath)) {
        manifestContent = JSON.parse(fs.readFileSync(manifestPath, 'utf-8'));
      }
    });

    test('should only contain valid fields from Claude Code plugin spec', () => {
      const validFields = ['name', 'version', 'description', 'author', 'license', 'homepage', 'keywords'];
      const manifestFields = Object.keys(manifestContent);
      const invalidFields = manifestFields.filter(field => !validFields.includes(field));

      expect(invalidFields).toEqual([]);
    });

    test('should conform to Claude Code plugin manifest structure', () => {
      const manifest = manifestContent;

      // Verify structure matches spec
      expect(manifest).toEqual({
        name: expect.any(String),
        version: expect.any(String),
        description: expect.any(String),
        author: expect.any(Object),
        license: expect.any(String),
        homepage: expect.any(String),
        keywords: expect.any(Array)
      });
    });
  });

  describe('Field Content Validation', () => {
    beforeAll(() => {
      if (fs.existsSync(manifestPath)) {
        manifestContent = JSON.parse(fs.readFileSync(manifestPath, 'utf-8'));
      }
    });

    test('name should be a valid plugin identifier', () => {
      expect(manifestContent.name).toBeTruthy();
      // Plugin names should not contain agents[], skills[], or hooks references
      expect(manifestContent.name).not.toMatch(/agents|skills|hooks/i);
    });

    test('version should be semantic versioning format', () => {
      expect(manifestContent.version).toMatch(/^\d+\.\d+\.\d+/);
    });

    test('license should be a recognized SPDX identifier or valid format', () => {
      expect(['MIT', 'Apache-2.0', 'GPL-3.0', 'ISC', 'BSD-2-Clause', 'BSD-3-Clause'].includes(manifestContent.license) ||
             manifestContent.license.length > 0).toBe(true);
    });
  });
});
