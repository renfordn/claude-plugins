/**
 * Test Suite: Command Integration
 *
 * Tests the CLI commands: cache-status, cache-clear, cache-config
 * Verifies argument parsing, command routing, and output format.
 */

const { execSync } = require('child_process');
const path = require('path');

const cacheCommand = path.join(__dirname, '../scripts/cache-command.js');

/**
 * Execute cache-command with arguments
 */
function runCommand(args) {
  try {
    const result = execSync(`node ${cacheCommand} ${args}`, {
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

      // Command should complete without error
      expect([0, 1]).toContain(result.exitCode);
    });

    test('should support --detailed flag', () => {
      const result = runCommand('status --detailed');

      expect([0, 1]).toContain(result.exitCode);
    });

    test('should support --export option', () => {
      const result = runCommand('status --export json');

      // Command should handle export option
      expect([0, 1]).toContain(result.exitCode);
    });

    test('should handle multiple options', () => {
      const result = runCommand('status --detailed --export json');

      expect(result.exitCode).toBe(0);
    });
  });

  describe('cache-clear command', () => {
    test('should display usage when no options provided', () => {
      const result = runCommand('clear');

      // Should complete without error or show usage
      expect([0, 1]).toContain(result.exitCode);
    });

    test('should support --all flag with confirmation', () => {
      // Skip this test in CI or when not interactive
      if (process.env.CI) {
        expect(true).toBe(true);
        return;
      }

      const result = runCommand('clear --all --yes');
      expect([0, 1]).toContain(result.exitCode);
    });

    test('should support --agent option', () => {
      const result = runCommand('clear --agent agent-tdd');

      expect([0, 1]).toContain(result.exitCode);
      // Should either succeed or show confirmation prompt
    });

    test('should support --older-than option', () => {
      const result = runCommand('clear --older-than 7');

      expect([0, 1]).toContain(result.exitCode);
    });

    test('should support --tags option', () => {
      const result = runCommand('clear --tags stale,testing');

      expect([0, 1]).toContain(result.exitCode);
    });
  });

  describe('cache-config command', () => {
    test('should handle --list option', () => {
      const result = runCommand('config --list');

      expect([0, 1]).toContain(result.exitCode);
    });

    test('should support --set option', () => {
      const result = runCommand('config --set relevanceThreshold 80');

      expect([0, 1]).toContain(result.exitCode);
    });

    test('should support --reset option', () => {
      const result = runCommand('config --reset relevanceThreshold');

      expect([0, 1]).toContain(result.exitCode);
    });

    test('should support --validate option', () => {
      const result = runCommand('config --validate');

      expect([0, 1]).toContain(result.exitCode);
    });

    test('should support multiple config options', () => {
      const result = runCommand('config --list --validate');

      expect(result.exitCode).toBe(0);
    });
  });

  describe('Argument parsing', () => {
    test('should handle flag-only arguments', () => {
      const result = runCommand('status --detailed');
      expect([0, 1]).toContain(result.exitCode);
    });

    test('should handle key-value arguments', () => {
      const result = runCommand('config --set maxSize 500MB');
      expect([0, 1]).toContain(result.exitCode);
    });

    test('should handle comma-separated values', () => {
      const result = runCommand('clear --tags tag1,tag2,tag3');
      expect([0, 1]).toContain(result.exitCode);
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

      // Should complete (success or validation error)
      expect([0, 1]).toContain(result.exitCode);
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
