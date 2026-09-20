/**
 * Test Suite: Plugin Hooks (stdin/stdout I/O Contract Tests)
 *
 * Validates hook scripts via CLI subprocess execution.
 * Each hook is a standalone Node.js script that:
 * - Reads stdin as JSON
 * - Writes stdout as JSON
 * - Uses exit code 0 for success, 1 for errors
 *
 * This test suite validates the CLI I/O contract and input validation.
 * Behavioral tests (TTL, LRU, sanitization, relevance) are at skill level.
 */

const { spawnSync } = require('child_process');
const path = require('path');

const hookDir = path.join(__dirname, '../hooks');

// ============================================================================
// UTILITIES
// ============================================================================

/**
 * Spawn a hook script as subprocess with stdin JSON input.
 * Provides consistent interface for testing CLI hooks.
 *
 * @param {string} hookFile - Hook script filename (e.g., 'pre-agent-spawn.js')
 * @param {object} inputData - JSON object to pass via stdin
 * @returns {object} Result with stdout, stderr, exitCode, signal, parsed
 */
function runHookWithInput(hookFile, inputData) {
  const hookPath = path.join(hookDir, hookFile);

  const result = spawnSync('node', [hookPath], {
    input: JSON.stringify(inputData),
    encoding: 'utf-8',
    maxBuffer: 10 * 1024 * 1024
  });

  return {
    stdout: result.stdout || '',
    stderr: result.stderr || '',
    exitCode: result.status,
    signal: result.signal,
    parsed: tryParseJSON(result.stdout)
  };
}

/**
 * Safely parse JSON string.
 * @returns {object|null} Parsed JSON or null if invalid
 */
function tryParseJSON(str) {
  try {
    return str ? JSON.parse(str) : null;
  } catch (e) {
    return null;
  }
}

/**
 * Build complete input object with required and optional fields.
 * Useful for test parametrization.
 */
function buildInput(toolName, sessionId, inputObj, outputObj) {
  const input = {};
  if (toolName !== undefined) input.toolName = toolName;
  if (inputObj !== undefined) input.input = inputObj;
  if (outputObj !== undefined) input.output = outputObj;
  if (sessionId !== undefined) input.sessionId = sessionId;
  return input;
}

describe('Pre-Agent-Spawn Hook (stdin/stdout I/O)', () => {
  const hookFile = 'pre-agent-spawn.js';

  describe('Success Cases', () => {
    test('should allow (PreToolUse) on valid input with no cache match', () => {
      const input = buildInput('agent-tdd', 'sess-123', { prompt: 'Test prompt' });
      const result = runHookWithInput(hookFile, input);

      expect(result.exitCode).toBe(0);
      expect(result.parsed).not.toBeNull();
      expect(result.parsed.hookSpecificOutput.permissionDecision).toBe('allow');
    });

    test('should output valid JSON with hookSpecificOutput.permissionDecision field', () => {
      const input = buildInput('some-tool', 'sess-456', { prompt: 'test prompt' });
      const result = runHookWithInput(hookFile, input);

      expect(result.exitCode).toBe(0);
      expect(result.parsed).toHaveProperty('hookSpecificOutput');
      expect(result.parsed.hookSpecificOutput.hookEventName).toBe('PreToolUse');
      expect(typeof result.parsed.hookSpecificOutput.permissionDecision).toBe('string');
    });
  });

  describe('Validation: Required Fields', () => {
    test('should still allow when toolName missing (informational-only, never blocks)', () => {
      const input = buildInput(undefined, 'sess-789', { prompt: 'test' });
      const result = runHookWithInput(hookFile, input);

      expect(result.exitCode).toBe(0);
      expect(result.parsed.hookSpecificOutput.permissionDecision).toBe('allow');
    });

    test('should still allow when sessionId missing (informational-only, never blocks)', () => {
      const input = buildInput('test-tool', undefined, { prompt: 'test' });
      const result = runHookWithInput(hookFile, input);

      expect(result.exitCode).toBe(0);
      expect(result.parsed.hookSpecificOutput.permissionDecision).toBe('allow');
    });

    test('should still allow when input object missing (informational-only, never blocks)', () => {
      const input = buildInput('test-tool', 'sess-123', undefined);
      const result = runHookWithInput(hookFile, input);

      expect(result.exitCode).toBe(0);
      expect(result.parsed.hookSpecificOutput.permissionDecision).toBe('allow');
    });
  });
});

describe('Post-Agent-Completion Hook (stdin/stdout I/O)', () => {
  const hookFile = 'post-agent-completion.js';

  describe('Success Cases', () => {
    test('should cache agent output on completion', () => {
      const input = buildInput(
        'agent-tdd',
        'sess-123',
        { prompt: 'Test prompt' },
        { result: 'success' }
      );

      const result = runHookWithInput(hookFile, input);

      expect(result.exitCode).toBe(0);
      expect(result.parsed).not.toBeNull();
      expect(result.parsed).toHaveProperty('hookSpecificOutput');
      expect(result.parsed.hookSpecificOutput.hookEventName).toBe('PostToolUse');
    });

    test('should handle complex output objects', () => {
      const input = buildInput(
        'agent-orchestrator',
        'sess-456',
        { prompt: 'Complex test' },
        { result: 'completed', data: [1, 2, 3], nested: { value: 'test' } }
      );

      const result = runHookWithInput(hookFile, input);

      expect(result.exitCode).toBe(0);
      expect(result.parsed.hookSpecificOutput).toBeDefined();
    });
  });

  describe('Validation: Required Fields', () => {
    test('should still succeed (exit 0) when toolName missing (never blocks)', () => {
      const input = buildInput(
        undefined,
        'sess-789',
        { prompt: 'test' },
        { result: 'success' }
      );

      const result = runHookWithInput(hookFile, input);

      expect(result.exitCode).toBe(0);
      expect(result.parsed.hookSpecificOutput.hookEventName).toBe('PostToolUse');
    });

    test('should still succeed (exit 0) when sessionId missing (never blocks)', () => {
      const input = buildInput(
        'test-tool',
        undefined,
        { prompt: 'test' },
        { result: 'success' }
      );

      const result = runHookWithInput(hookFile, input);

      expect(result.exitCode).toBe(0);
      expect(result.parsed.hookSpecificOutput.hookEventName).toBe('PostToolUse');
    });

    test('should still succeed (exit 0) when output object missing (never blocks)', () => {
      const input = buildInput(
        'test-tool',
        'sess-123',
        { prompt: 'test' },
        undefined
      );

      const result = runHookWithInput(hookFile, input);

      expect(result.exitCode).toBe(0);
      expect(result.parsed.hookSpecificOutput.hookEventName).toBe('PostToolUse');
    });

    test('should still succeed (exit 0) when input object missing (never blocks)', () => {
      const input = buildInput(
        'test-tool',
        'sess-123',
        undefined,
        { result: 'success' }
      );

      const result = runHookWithInput(hookFile, input);

      expect(result.exitCode).toBe(0);
      expect(result.parsed.hookSpecificOutput.hookEventName).toBe('PostToolUse');
    });
  });
});

describe('Cache-Invalidation Hook (stdin/stdout I/O)', () => {
  const hookFile = 'cache-invalidation.js';

  describe('Success Cases: Trigger Types', () => {
    const triggers = ['periodic', 'threshold', 'session-end'];

    test.each(triggers)('should process invalidation on %s trigger', (trigger) => {
      const input = {
        trigger,
        sessionId: `sess-${Math.random()}`
      };

      const result = runHookWithInput(hookFile, input);

      expect(result.exitCode).toBe(0);
      expect(result.parsed).not.toBeNull();
      expect(typeof result.parsed).toBe('object');
    });
  });

  describe('Output Validation', () => {
    test('should output valid JSON on all triggers', () => {
      const input = {
        trigger: 'periodic',
        sessionId: 'sess-test-json'
      };

      const result = runHookWithInput(hookFile, input);

      expect(result.exitCode).toBe(0);
      // Verify stdout is not empty and is valid JSON
      expect(result.stdout.trim()).not.toBe('');
      expect(result.parsed).not.toBeNull();
    });

    test('should return object with expected structure', () => {
      const input = {
        trigger: 'threshold',
        sessionId: 'sess-struct-test'
      };

      const result = runHookWithInput(hookFile, input);

      expect(result.exitCode).toBe(0);
      expect(typeof result.parsed).toBe('object');
      // Should have some output fields (specific fields determined by hook implementation)
      expect(Object.keys(result.parsed).length).toBeGreaterThan(0);
    });
  });
});
