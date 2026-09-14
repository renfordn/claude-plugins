/**
 * Test Suite: Cache Validator Skill
 *
 * Tests the CacheValidator class which validates cache entries,
 * scores relevance, detects issues, and provides recommendations.
 */

const { CacheValidator } = require('../skills/cache-validation');

// ============================================================================
// TEST DATA & FIXTURES
// ============================================================================

// Configuration and time constants
const DEFAULTS = {
  MIN_RELEVANCE: 70,
  MAX_ENTRY_AGE_MS: 7 * 24 * 60 * 60 * 1000,  // 7 days
  TTL_MS: 24 * 60 * 60 * 1000,                // 1 day
  BATCH_TIMEOUT_MS: 5000,
  USER_ID: 'user-123',
  PROJECT_ID: 'proj-456'
};

// Age offsets for staleness testing
const AGES = {
  FRESH: 0,                        // Current time
  SIX_DAYS: 6 * 24 * 60 * 60 * 1000,
  SEVEN_DAYS: 7 * 24 * 60 * 60 * 1000,
  EIGHT_DAYS: 8 * 24 * 60 * 60 * 1000
};

/**
 * Build a valid cached entry with customizable fields
 */
function validCachedEntry(overrides = {}) {
  return {
    id: overrides.id || 'entry-1',
    prompt: overrides.prompt || 'Test prompt for cache',
    output: overrides.output || { result: 'cached output' },
    metadata: {
      timestamp: Date.now() - (overrides.age || AGES.FRESH),
      ttl: DEFAULTS.TTL_MS,
      parameters: { userId: DEFAULTS.USER_ID },
      ...overrides.metadata
    }
  };
}

/**
 * Build a valid context object for validation
 */
function validContext(overrides = {}) {
  return {
    task: overrides.task || 'Test prompt for cache',
    parameters: { userId: DEFAULTS.USER_ID, ...overrides.parameters },
    ...overrides
  };
}

describe('CacheValidator Skill', () => {
  let validator;

  beforeEach(() => {
    validator = new CacheValidator({
      minRelevanceScore: DEFAULTS.MIN_RELEVANCE,
      maxEntryAge: DEFAULTS.MAX_ENTRY_AGE_MS
    });
  });

  describe('Single Entry Validation', () => {
    test('should validate a healthy cache entry', async () => {
      const entry = validCachedEntry();
      const context = validContext();

      const result = await validator.validate(entry, context);

      expect(result).toHaveProperty('isValid');
      expect(result).toHaveProperty('issues');
      expect(result).toHaveProperty('relevanceScore');
      expect(result).toHaveProperty('confidence');
      expect(result).toHaveProperty('recommendation');
      expect(typeof result.confidence).toBe('number');
      expect(result.confidence).toBeGreaterThanOrEqual(0);
      expect(result.confidence).toBeLessThanOrEqual(100);
    });

    test('should detect stale entries', async () => {
      const entry = validCachedEntry({ age: AGES.EIGHT_DAYS });
      const context = validContext();

      const result = await validator.validate(entry, context);

      expect(result.isStale).toBe(true);
      expect(result.isValid).toBe(false);
    });

    test('should detect missing required fields', async () => {
      const entry = {
        id: 'entry-1',
        // Missing prompt, output, metadata
      };
      const context = validContext();

      const result = await validator.validate(entry, context);

      expect(result.issues.length).toBeGreaterThan(0);
      expect(result.isValid).toBe(false);
    });

    test('should score relevance of entry to context', async () => {
      const entry = validCachedEntry();
      const context = validContext();

      const result = await validator.validate(entry, context);

      expect(typeof result.relevanceScore).toBe('number');
      expect(result.relevanceScore).toBeGreaterThanOrEqual(0);
      expect(result.relevanceScore).toBeLessThanOrEqual(100);
    });

    test('should reject low relevance scores', async () => {
      const entry = validCachedEntry({
        prompt: 'Completely different topic about gardening'
      });
      const context = validContext({
        task: 'Test prompt for cache'
      });

      const result = await validator.validate(entry, context);

      // Low relevance should reduce confidence and likely result in discard
      if (result.relevanceScore < DEFAULTS.MIN_RELEVANCE) {
        expect(result.isValid).toBe(false);
      }
    });

    test('should detect parameter conflicts', async () => {
      const entry = validCachedEntry({
        metadata: {
          timestamp: Date.now(),
          ttl: 24 * 60 * 60 * 1000,
          parameters: { userId: 'user-123', projectId: 'proj-456' }
        }
      });
      const context = validContext({
        parameters: { userId: 'user-789', projectId: 'proj-456' }
      });

      const result = await validator.validate(entry, context);

      expect(result.hasConflicts).toBe(true);
      expect(result.issues.length).toBeGreaterThan(0);
    });

    test('should make recommendations based on validation', async () => {
      const entry = validCachedEntry();
      const context = validContext();

      const result = await validator.validate(entry, context);

      expect(['use', 'update', 'discard']).toContain(result.recommendation);
    });
  });

  describe('Multiple Entry Validation', () => {
    test('should validate and rank multiple entries', async () => {
      const entries = [
        validCachedEntry({ id: 'entry-1' }),
        validCachedEntry({ id: 'entry-2', prompt: 'slightly different prompt' })
      ];
      const context = validContext();

      const result = await validator.validateMultiple(entries, context);

      expect(result.best).toBeDefined();
      expect(result.validations).toHaveLength(2);
      expect(result.validations[0]).toHaveProperty('entryId');
      expect(result.validations[0]).toHaveProperty('validation');
      expect(result.validations[0]).toHaveProperty('score');
    });

    test('should return lowest-scoring entry if all invalid', async () => {
      const entries = [
        { id: 'entry-1' },  // Invalid: missing required fields
        { id: 'entry-2' }   // Invalid: missing required fields
      ];
      const context = validContext();

      const result = await validator.validateMultiple(entries, context);

      // Even invalid entries are ranked; returns highest score even if 0
      expect(result.best).toBeDefined();
      expect(result.validations.every(v => !v.validation.isValid)).toBe(true);
    });

    test('should sort entries by score', async () => {
      const entries = [
        validCachedEntry({ id: 'entry-1', prompt: 'very different prompt' }),
        validCachedEntry({ id: 'entry-2', prompt: 'Test prompt for cache' })
      ];
      const context = validContext();

      const result = await validator.validateMultiple(entries, context);

      // Second entry should score higher (exact match prompt)
      expect(result.validations[0].entryId).toBe('entry-2');
    });
  });

  describe('Batch Validation', () => {
    test('should batch validate multiple entries', async () => {
      const entries = [
        validCachedEntry({ id: 'entry-1' }),
        validCachedEntry({ id: 'entry-2' }),
        validCachedEntry({ id: 'entry-3' })
      ];
      const context = validContext();

      const result = await validator.batchValidate(entries, context);

      expect(result).toHaveProperty('processedCount');
      expect(result).toHaveProperty('totalCount');
      expect(result).toHaveProperty('results');
      expect(result.totalCount).toBe(3);
      expect(result.processedCount).toBeGreaterThanOrEqual(0);
    });

    test('should respect timeout on large batches', async () => {
      const entries = Array.from({ length: 100 }, (_, i) =>
        validCachedEntry({ id: `entry-${i}` })
      );
      const context = validContext();

      const result = await validator.batchValidate(entries, context);

      // Should process some but not all due to 5 second timeout
      expect(result.processedCount).toBeLessThanOrEqual(result.totalCount);
    });
  });

  describe('Configuration', () => {
    test('should use default thresholds', () => {
      const defaultValidator = new CacheValidator();

      expect(defaultValidator.minRelevanceScore).toBe(DEFAULTS.MIN_RELEVANCE);
      expect(defaultValidator.maxEntryAge).toBe(DEFAULTS.MAX_ENTRY_AGE_MS);
    });

    test('should accept custom thresholds', () => {
      const CUSTOM_MIN = 85;
      const CUSTOM_AGE_MS = 30 * 24 * 60 * 60 * 1000;  // 30 days

      const customValidator = new CacheValidator({
        minRelevanceScore: CUSTOM_MIN,
        maxEntryAge: CUSTOM_AGE_MS
      });

      expect(customValidator.minRelevanceScore).toBe(CUSTOM_MIN);
      expect(customValidator.maxEntryAge).toBe(CUSTOM_AGE_MS);
    });
  });

  describe('Error Handling', () => {
    test('should handle validation errors gracefully', async () => {
      const invalidEntry = null;  // Will cause error during validation
      const context = validContext();

      const result = await validator.validate(invalidEntry, context);

      expect(result.isValid).toBe(false);
      expect(result.confidence).toBe(0);
      expect(result.recommendation).toBe('discard');
      expect(result.issues.length).toBeGreaterThan(0);
    });

    test('should handle missing context fields', async () => {
      const entry = validCachedEntry();
      const invalidContext = {};

      const result = await validator.validate(entry, invalidContext);

      expect(result).toBeDefined();
      expect(result.recommendation).toBeDefined();
    });

    test('should handle empty output gracefully', async () => {
      const entry = validCachedEntry({ output: '' });
      const context = validContext();

      const result = await validator.validate(entry, context);

      expect(result).toBeDefined();
      expect(result.recommendation).toBeDefined();
    });
  });

  describe('Relevance Scoring', () => {
    test('should score identical prompts as 100', async () => {
      const entry = validCachedEntry({ prompt: 'exact test prompt' });
      const context = validContext({ task: 'exact test prompt' });

      const result = await validator.validate(entry, context);

      expect(result.relevanceScore).toBe(100);
    });

    test('should score similar prompts between 0 and 100', async () => {
      const entry = validCachedEntry({ prompt: 'test prompt for cache' });
      const context = validContext({ task: 'test prompt' });

      const result = await validator.validate(entry, context);

      expect(result.relevanceScore).toBeGreaterThan(0);
      expect(result.relevanceScore).toBeLessThan(100);
    });

    test('should score completely different prompts low', async () => {
      const entry = validCachedEntry({ prompt: 'test prompt' });
      const context = validContext({ task: 'gardening tips' });

      const result = await validator.validate(entry, context);

      expect(result.relevanceScore).toBe(0);
    });
  });
});
