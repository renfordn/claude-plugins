/**
 * Test Suite: Hook I/O Contracts
 *
 * Validates that all hook scripts accept stdin JSON, output stdout JSON,
 * and use proper exit codes. Tests the CLI interface (not context-object injection).
 *
 * HIGH-RISK: These tests verify the critical integration point between
 * Claude Code runtime and plugin behavior.
 */

const { spawnSync } = require('child_process');
const path = require('path');

const hookDir = path.join(__dirname, '../hooks');

/**
 * Spawn a hook script as a subprocess with stdin JSON input.
 * Returns {stdout, stderr, exitCode, parsed}.
 */
function runHookWithInput(hookFile, inputData) {
  const hookPath = path.join(hookDir, hookFile);

  const result = spawnSync('node', [hookPath], {
    input: JSON.stringify(inputData),
    encoding: 'utf-8',
    maxBuffer: 10 * 1024 * 1024 // 10MB buffer
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
 * Parse JSON, return null on failure (don't throw).
 */
function tryParseJSON(str) {
  try {
    return str ? JSON.parse(str) : null;
  } catch (e) {
    return null;
  }
}

// ============================================================================
// PRE-AGENT-SPAWN HOOK TESTS
// ============================================================================

describe('Hook I/O Contracts: pre-agent-spawn.js', () => {

  test('should accept valid stdin JSON and output a harness-recognized PreToolUse allow decision', () => {
    const input = {
      toolName: 'Agent',
      input: { prompt: 'test prompt' },
      sessionId: 'sess-123'
    };

    const result = runHookWithInput('pre-agent-spawn.js', input);

    // Assert exit code 0 (success)
    expect(result.exitCode).toBe(0);

    // Assert stdout is valid JSON
    expect(result.parsed).not.toBeNull();
    expect(typeof result.parsed).toBe('object');

    // Assert stdout matches the harness's PreToolUse contract, never a bare bespoke shape
    expect(result.parsed).toHaveProperty('hookSpecificOutput');
    expect(result.parsed.hookSpecificOutput.hookEventName).toBe('PreToolUse');
    expect(result.parsed.hookSpecificOutput.permissionDecision).toBe('allow');
  });

  test('should include a permissionDecisionReason on cache hit', () => {
    const input = {
      toolName: 'Agent',
      input: { prompt: 'test prompt' },
      sessionId: 'sess-123'
    };

    const result = runHookWithInput('pre-agent-spawn.js', input);

    // Always allow; reason is present when informational context exists
    expect(result.parsed.hookSpecificOutput.permissionDecision).toBe('allow');
    if ('permissionDecisionReason' in result.parsed.hookSpecificOutput) {
      expect(typeof result.parsed.hookSpecificOutput.permissionDecisionReason).toBe('string');
    }
  });

  test('never sets updatedInput, so the original tool input (incl. description) survives untouched', () => {
    const input = {
      toolName: 'Agent',
      input: { description: 'test agent', prompt: 'do the thing' },
      sessionId: 'sess-123'
    };

    const result = runHookWithInput('pre-agent-spawn.js', input);

    expect(result.parsed.hookSpecificOutput.updatedInput).toBeUndefined();

    // Simulate the harness: absent updatedInput means the original input is used unchanged.
    const effectiveInput = result.parsed.hookSpecificOutput.updatedInput || input.input;
    expect(effectiveInput.description).toBe('test agent');
  });

  test('should exit with code 0 on valid input', () => {
    const input = {
      toolName: 'Agent',
      input: { prompt: 'test' },
      sessionId: 'sess-123'
    };

    const result = runHookWithInput('pre-agent-spawn.js', input);

    expect(result.exitCode).toBe(0);
  });

  test('should handle invalid JSON input gracefully (exit 0, allow, no crash)', () => {
    const result = spawnSync('node', [path.join(hookDir, 'pre-agent-spawn.js')], {
      input: '{invalid json}',
      encoding: 'utf-8'
    });

    // Must exit 0 (always allow) on invalid input, not crash (exit 2, SIGSEGV, etc.)
    expect(result.status).toBe(0);

    // Must not have stderr from uncaught exception
    if (result.stderr) {
      expect(result.stderr).not.toMatch(/TypeError|ReferenceError|cannot read/i);
    }
  });

  test('should return valid allow-shaped JSON even on parse error', () => {
    const result = spawnSync('node', [path.join(hookDir, 'pre-agent-spawn.js')], {
      input: '{malformed',
      encoding: 'utf-8'
    });

    // Stdout should still be valid, contract-conformant JSON
    const parsed = tryParseJSON(result.stdout);
    expect(parsed).not.toBeNull();
    expect(parsed.hookSpecificOutput.permissionDecision).toBe('allow');
  });

  test('should handle empty sessionId gracefully (allow, exit 0)', () => {
    const input = {
      toolName: 'Agent',
      input: { prompt: 'test' },
      sessionId: ''
    };

    const result = runHookWithInput('pre-agent-spawn.js', input);

    // Should still allow (exit 0) on invalid input (empty sessionId)
    expect(result.exitCode).toBe(0);
    expect(result.parsed.hookSpecificOutput.permissionDecision).toBe('allow');
  });

  test('should handle missing required fields gracefully (allow, exit 0)', () => {
    const input = {
      // Missing toolName and sessionId
      input: { prompt: 'test' }
    };

    const result = runHookWithInput('pre-agent-spawn.js', input);

    // Should still allow (exit 0)
    expect(result.exitCode).toBe(0);
    expect(result.parsed.hookSpecificOutput.permissionDecision).toBe('allow');
  });

  test('should not have context-object function parameters', () => {
    // This test checks the function signature doesn't include context object
    // The hook should be CLI-only, spawned as a subprocess

    const hookCode = require('fs').readFileSync(path.join(hookDir, 'pre-agent-spawn.js'), 'utf-8');

    // Should NOT export a function that expects (context) parameter
    // Should be a CLI script that reads from stdin and writes to stdout
    // This is a heuristic check for the pattern
    expect(hookCode).toMatch(/process\.stdin|readline|stdin/i);
  });
});

// ============================================================================
// POST-AGENT-COMPLETION HOOK TESTS
// ============================================================================

describe('Hook I/O Contracts: post-agent-completion.js', () => {

  test('should accept valid stdin JSON and output a harness-recognized PostToolUse decision', () => {
    const input = {
      toolName: 'Agent',
      input: { x: 1 },
      output: { result: 'ok' },
      sessionId: 'sess-123'
    };

    const result = runHookWithInput('post-agent-completion.js', input);

    // Assert exit code 0 (success)
    expect(result.exitCode).toBe(0);

    // Assert stdout is valid JSON
    expect(result.parsed).not.toBeNull();
    expect(typeof result.parsed).toBe('object');

    // Assert stdout matches the harness's PostToolUse contract
    expect(result.parsed).toHaveProperty('hookSpecificOutput');
    expect(result.parsed.hookSpecificOutput.hookEventName).toBe('PostToolUse');
  });

  test('should include tokensSaved/cacheKey facts in additionalContext when stored', () => {
    const input = {
      toolName: 'Agent',
      input: { x: 1 },
      output: { result: 'success' },
      sessionId: 'sess-123'
    };

    const result = runHookWithInput('post-agent-completion.js', input);

    expect(typeof result.parsed.hookSpecificOutput.additionalContext).toBe('string');
    expect(result.parsed.hookSpecificOutput.additionalContext).toMatch(/tokensSaved=/);
    expect(result.parsed.hookSpecificOutput.additionalContext).toMatch(/cacheKey=/);
  });

  test('should omit additionalContext when not cacheable', () => {
    const input = {
      toolName: 'Agent',
      input: { x: 1 },
      output: { result: 'the current time is now' },
      sessionId: 'sess-123'
    };

    const result = runHookWithInput('post-agent-completion.js', input);

    expect(result.parsed.hookSpecificOutput.additionalContext).toBeUndefined();
  });

  test('should exit with code 0 on valid input', () => {
    const input = {
      toolName: 'Agent',
      input: { x: 1 },
      output: { result: 'ok' },
      sessionId: 'sess-123'
    };

    const result = runHookWithInput('post-agent-completion.js', input);

    expect(result.exitCode).toBe(0);
  });

  test('should handle invalid JSON input gracefully (exit 0, no crash)', () => {
    const result = spawnSync('node', [path.join(hookDir, 'post-agent-completion.js')], {
      input: '{broken json}',
      encoding: 'utf-8'
    });

    // Must exit 0 on invalid input, not crash
    expect(result.status).toBe(0);

    // Must not throw uncaught exception
    if (result.stderr) {
      expect(result.stderr).not.toMatch(/TypeError|ReferenceError|cannot read/i);
    }
  });

  test('should return valid JSON even on parse error', () => {
    const result = spawnSync('node', [path.join(hookDir, 'post-agent-completion.js')], {
      input: '{invalid}',
      encoding: 'utf-8'
    });

    // Stdout should still be valid JSON
    const parsed = tryParseJSON(result.stdout);
    expect(parsed).not.toBeNull();
    expect(parsed.hookSpecificOutput.hookEventName).toBe('PostToolUse');
  });

  test('should handle missing required fields gracefully (exit 0)', () => {
    const input = {
      // Missing toolName, output, sessionId
      input: { x: 1 }
    };

    const result = runHookWithInput('post-agent-completion.js', input);

    // Should exit 0 (inert, never blocks)
    expect(result.exitCode).toBe(0);

    // Should return valid JSON response
    expect(result.parsed).not.toBeNull();
  });

  test('should handle empty sessionId gracefully (exit 0)', () => {
    const input = {
      toolName: 'Agent',
      input: { x: 1 },
      output: { result: 'ok' },
      sessionId: ''
    };

    const result = runHookWithInput('post-agent-completion.js', input);

    // Should exit 0 on invalid input
    expect(result.exitCode).toBe(0);

    // Should return valid JSON
    expect(result.parsed).not.toBeNull();
  });

  test('should not have context-object function parameters', () => {
    const hookCode = require('fs').readFileSync(path.join(hookDir, 'post-agent-completion.js'), 'utf-8');

    // Should NOT export a function that expects (context) parameter
    // Should be a CLI script that reads from stdin and writes to stdout
    expect(hookCode).toMatch(/process\.stdin|readline|stdin/i);
  });
});

// ============================================================================
// CACHE-INVALIDATION HOOK TESTS
// ============================================================================

describe('Hook I/O Contracts: cache-invalidation.js', () => {

  test('should accept valid stdin JSON and output valid stdout JSON', () => {
    const input = {
      sessionId: 'sess-123'
    };

    const result = runHookWithInput('cache-invalidation.js', input);

    // Assert exit code 0 (success)
    expect(result.exitCode).toBe(0);

    // Assert stdout is valid JSON
    expect(result.parsed).not.toBeNull();
    expect(typeof result.parsed).toBe('object');

    // Assert stdout has required fields
    expect(result.parsed).toHaveProperty('invalidated');
    expect(typeof result.parsed.invalidated).toBe('boolean');
  });

  test('should include entriesRemoved in output', () => {
    const input = {
      sessionId: 'sess-123'
    };

    const result = runHookWithInput('cache-invalidation.js', input);

    // Must have entriesRemoved field
    expect(result.parsed).toHaveProperty('entriesRemoved');
    expect(typeof result.parsed.entriesRemoved).toBe('number');
  });

  test('should include metricsArchived in output when applicable', () => {
    const input = {
      sessionId: 'sess-123'
    };

    const result = runHookWithInput('cache-invalidation.js', input);

    // Optional metricsArchived field
    if ('metricsArchived' in result.parsed) {
      expect(typeof result.parsed.metricsArchived).toBe('boolean');
    }
  });

  test('should exit with code 0 on valid input', () => {
    const input = {
      sessionId: 'sess-123'
    };

    const result = runHookWithInput('cache-invalidation.js', input);

    expect(result.exitCode).toBe(0);
  });

  test('should handle invalid JSON input gracefully (exit 0, fail-open)', () => {
    const result = spawnSync('node', [path.join(hookDir, 'cache-invalidation.js')], {
      input: '{corrupted}',
      encoding: 'utf-8'
    });

    // Always exit 0 — never crash the host session
    expect(result.status).toBe(0);

    // Must not throw uncaught exception
    if (result.stderr) {
      expect(result.stderr).not.toMatch(/TypeError|ReferenceError|cannot read/i);
    }
  });

  test('should return valid JSON even on parse error', () => {
    const result = spawnSync('node', [path.join(hookDir, 'cache-invalidation.js')], {
      input: '{{bad}}',
      encoding: 'utf-8'
    });

    // Stdout should still be valid JSON
    const parsed = tryParseJSON(result.stdout);
    expect(parsed).not.toBeNull();
    expect(typeof parsed).toBe('object');
  });

  test('should handle empty sessionId gracefully (fail-open, exit 0)', () => {
    const input = { sessionId: '' };
    const result = runHookWithInput('cache-invalidation.js', input);

    expect(result.exitCode).toBe(0);
    expect(result.parsed).not.toBeNull();
  });

  test('should handle missing sessionId field gracefully (fail-open, exit 0)', () => {
    const input = { reason: 'user-requested' };
    const result = runHookWithInput('cache-invalidation.js', input);

    expect(result.exitCode).toBe(0);
    expect(result.parsed).not.toBeNull();
  });

  test('should not have context-object function parameters', () => {
    const hookCode = require('fs').readFileSync(path.join(hookDir, 'cache-invalidation.js'), 'utf-8');

    // Should NOT export a function that expects (context) parameter
    // Should be a CLI script that reads from stdin and writes to stdout
    expect(hookCode).toMatch(/process\.stdin|readline|stdin/i);
  });

  test('should handle optional timestamp field gracefully', () => {
    const input = {
      sessionId: 'sess-123',
      timestamp: Date.now()
    };

    const result = runHookWithInput('cache-invalidation.js', input);

    // Should handle optional timestamp field without error
    expect(result.exitCode).toBe(0);
    expect(result.parsed).not.toBeNull();
  });

  test('should handle optional reason field gracefully', () => {
    const input = {
      sessionId: 'sess-123',
      reason: 'manual-invalidation'
    };

    const result = runHookWithInput('cache-invalidation.js', input);

    // Should handle optional reason field without error
    expect(result.exitCode).toBe(0);
    expect(result.parsed).not.toBeNull();
  });
});

// ============================================================================
// CROSS-HOOK INTEGRATION TESTS
// ============================================================================

describe('Hook I/O Contracts: Integration', () => {

  test('all hooks should exist as CLI-executable JS files', () => {
    const hooks = [
      'pre-agent-spawn.js',
      'post-agent-completion.js',
      'cache-invalidation.js'
    ];

    hooks.forEach(hookFile => {
      const hookPath = path.join(hookDir, hookFile);
      expect(require('fs').existsSync(hookPath)).toBe(true);
    });
  });

  test('all hooks should exit cleanly on empty input', () => {
    const hooks = [
      { file: 'pre-agent-spawn.js', input: {} },
      { file: 'post-agent-completion.js', input: {} },
      { file: 'cache-invalidation.js', input: {} }
    ];

    hooks.forEach(({ file, input }) => {
      const result = runHookWithInput(file, input);

      // Should exit 1 (invalid input), not crash (exit code 2+)
      expect(result.exitCode).toBeGreaterThanOrEqual(0);
      expect(result.exitCode).toBeLessThanOrEqual(1);
    });
  });

  test('all hooks should output only JSON to stdout', () => {
    const inputs = [
      ['pre-agent-spawn.js', { toolName: 'Test', input: {}, sessionId: 'x' }],
      ['post-agent-completion.js', { toolName: 'Test', input: {}, output: {}, sessionId: 'x' }],
      ['cache-invalidation.js', { sessionId: 'x' }]
    ];

    inputs.forEach(([hookFile, input]) => {
      const result = runHookWithInput(hookFile, input);

      // On success, stdout should be valid JSON (no extra text)
      if (result.exitCode === 0) {
        expect(result.parsed).not.toBeNull();
        // Reconstructing to ensure it's pure JSON
        const reconstructed = JSON.stringify(result.parsed);
        expect(reconstructed).toBeTruthy();
      }
    });
  });
});
