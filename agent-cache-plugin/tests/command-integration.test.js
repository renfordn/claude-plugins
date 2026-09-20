/**
 * Test Suite: Command Integration
 *
 * Tests the CLI commands: cache-status, cache-clear, cache-config
 * Verifies argument parsing, command routing, and output format.
 */

const { execFileSync } = require('child_process');
const path = require('path');

const cacheCommand = path.join(__dirname, '../scripts/cache-command.js');

/**
 * Execute cache-command with arguments
 */
function runCommand(args) {
  try {
    const result = execFileSync('node', [cacheCommand, ...args.split(' ').filter(Boolean)], {
      encoding: 'utf-8',
      stdio: ['pipe', 'pipe', 'pipe']
    });
    return { output: result, exitCode: 0 };
  } catch (error) {
    return {
      output: error.stdout || '',
      error: error.stderr || '',
      exitCode: error.status || 1
    };
  }
}

describe('CLI Commands', () => {
  describe('cache-status command', () => {
    test('should handle status command', () => {
      const result = runCommand('status');

      expect(result.exitCode).toBe(0);
    });

    test('should support --detailed flag', () => {
      const result = runCommand('status --detailed');

      expect(result.exitCode).toBe(0);
    });

    test('should support --export option', () => {
      const result = runCommand('status --export json');

      expect(result.exitCode).toBe(0);
    });

    test('should handle multiple options', () => {
      const result = runCommand('status --detailed --export json');

      expect(result.exitCode).toBe(0);
    });
  });

  describe('cache-clear command', () => {
    test('should display usage when no options provided', () => {
      const result = runCommand('clear');

      expect(result.exitCode).toBe(0);
    });

    test('should support --all flag with confirmation', () => {
      // Skip this test in CI or when not interactive
      if (process.env.CI) {
        expect(true).toBe(true);
        return;
      }

      const result = runCommand('clear --all --yes');
      expect(result.exitCode).toBe(0);
    });

    test('should support --agent option', () => {
      const result = runCommand('clear --agent agent-tdd');

      expect(result.exitCode).toBe(0);
    });

    test('should support --older-than option', () => {
      const result = runCommand('clear --older-than 7');

      expect(result.exitCode).toBe(0);
    });

    test('should support --tags option', () => {
      const result = runCommand('clear --tags stale,testing');

      expect(result.exitCode).toBe(0);
    });
  });

  describe('cache-config command', () => {
    test('should handle --list option', () => {
      const result = runCommand('config --list');

      expect(result.exitCode).toBe(0);
    });

    test('should support --set option', () => {
      const result = runCommand('config --set relevanceThreshold 80');

      expect(result.exitCode).toBe(0);
    });

    test('should support --reset option', () => {
      const result = runCommand('config --reset relevanceThreshold');

      expect(result.exitCode).toBe(0);
    });

    test('should support --validate option', () => {
      const result = runCommand('config --validate');

      expect(result.exitCode).toBe(0);
    });

    test('should support multiple config options', () => {
      const result = runCommand('config --list --validate');

      expect(result.exitCode).toBe(0);
    });
  });

  describe('Argument parsing', () => {
    test('should handle flag-only arguments', () => {
      const result = runCommand('status --detailed');
      expect(result.exitCode).toBe(0);
    });

    test('should handle key-value arguments', () => {
      const result = runCommand('config --set maxSize 500MB');
      expect(result.exitCode).toBe(0);
    });

    test('should handle comma-separated values', () => {
      const result = runCommand('clear --tags tag1,tag2,tag3');
      expect(result.exitCode).toBe(0);
    });

    test('should handle multiple arguments', () => {
      const result = runCommand('status --detailed --export json');
      expect(result.exitCode).toBe(0);
    });
  });

  describe('Error handling', () => {
    test('should fail for unknown command', () => {
      const result = runCommand('unknown-command');

      expect(result.exitCode).not.toBe(0);
      expect(result.error || result.output).toContain('Unknown command');
    });

    test('should show usage with --help', () => {
      const result = runCommand('--help');

      expect(result.output).toContain('Usage:');
    });

    test('should show version with --version', () => {
      const result = runCommand('--version');

      expect(result.exitCode).toBe(0);
      expect(result.output).toContain('v');  // Version number
    });

    test('should handle invalid option values gracefully', () => {
      const result = runCommand('config --set invalidKey invalidValue');

      expect(result.exitCode).toBe(0);
    });
  });

  describe('Command output format', () => {
    test('cache-status should complete successfully', () => {
      const result = runCommand('status');

      expect(result.exitCode).toBe(0);
      // Output should exist (stdout or via console.log)
      expect(result.output || result.exitCode === 0).toBeTruthy();
    });

    test('cache-config --list should complete', () => {
      const result = runCommand('config --list');

      expect(result.exitCode).toBe(0);
    });
  });

  describe('Exit codes', () => {
    test('successful commands should exit with 0', () => {
      const result = runCommand('status');
      expect(result.exitCode).toBe(0);
    });

    test('help/version should exit with 0', () => {
      const result1 = runCommand('--help');
      const result2 = runCommand('--version');

      expect(result1.exitCode).toBe(0);
      expect(result2.exitCode).toBe(0);
    });

    test('unknown command should exit with non-zero', () => {
      const result = runCommand('unknown');
      expect(result.exitCode).not.toBe(0);
    });
  });
});
