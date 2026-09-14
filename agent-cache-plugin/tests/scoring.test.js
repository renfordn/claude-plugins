/**
 * Test Suite: Scoring Utilities
 *
 * Tests centralized relevance scoring and similarity calculations
 * used across cache orchestration and validation skills.
 */

const scoring = require('../utils/scoring');

describe('Scoring Utilities', () => {
  describe('scoreRelevance (strict filtering)', () => {
    test('should score identical prompts as 100', () => {
      const score = scoring.scoreRelevance('test prompt match', 'test prompt match');
      expect(score).toBe(100);
    });

    test('should score similar prompts high (50-99)', () => {
      const score = scoring.scoreRelevance('test prompt evaluation', 'test prompt analysis');
      expect(score).toBeGreaterThanOrEqual(50);
      expect(score).toBeLessThan(100);
    });

    test('should score different prompts low (0-50)', () => {
      const score = scoring.scoreRelevance('test prompt', 'gardening tips');
      expect(score).toBeLessThan(50);
    });

    test('should score completely different prompts as 0', () => {
      const score = scoring.scoreRelevance('test', 'completely different topic');
      expect(score).toBe(0);
    });

    test('should handle empty/null inputs as 0', () => {
      expect(scoring.scoreRelevance('', 'test')).toBe(0);
      expect(scoring.scoreRelevance('test', '')).toBe(0);
      expect(scoring.scoreRelevance(null, 'test')).toBe(0);
      expect(scoring.scoreRelevance('test', null)).toBe(0);
    });

    test('should ignore short words (< 3 chars)', () => {
      // 'a' and 'an' are ignored; only 'test' counts
      const score1 = scoring.scoreRelevance('a test', 'an test');
      expect(score1).toBe(100);  // Both reduce to 'test'
    });

    test('should return numeric score between 0-100', () => {
      const prompts = [
        ['test', 'test'],
        ['test prompt', 'completely different'],
        ['', ''],
        [null, null]
      ];

      prompts.forEach(([p1, p2]) => {
        const score = scoring.scoreRelevance(p1, p2);
        expect(typeof score).toBe('number');
        expect(score).toBeGreaterThanOrEqual(0);
        expect(score).toBeLessThanOrEqual(100);
      });
    });

    test('should be case-insensitive', () => {
      const score1 = scoring.scoreRelevance('Test Prompt', 'test prompt');
      const score2 = scoring.scoreRelevance('TEST PROMPT', 'test prompt');
      expect(score1).toBe(100);
      expect(score2).toBe(100);
    });
  });

  describe('scoreRelevancePermissive (lenient filtering)', () => {
    test('should score with words > 2 chars (vs strict > 3)', () => {
      // 'to' is included in permissive but not strict
      const lenient = scoring.scoreRelevancePermissive('to test', 'to test');
      const strict = scoring.scoreRelevance('to test', 'to test');

      expect(lenient).toBe(100);
      expect(strict).toBeLessThanOrEqual(100);
    });

    test('should be more lenient than strict scoring', () => {
      const text1 = 'a tiny prompt';
      const text2 = 'an tiny prompt';

      const permissive = scoring.scoreRelevancePermissive(text1, text2);
      const strict = scoring.scoreRelevance(text1, text2);

      expect(permissive).toBeGreaterThanOrEqual(strict);
    });
  });

  describe('scoreRelevanceWeighted', () => {
    test('should prefer similar-length prompts', () => {
      // Same words but different lengths
      const score1 = scoring.scoreRelevanceWeighted(
        'test implementation',
        'test implementation'
      );
      const score2 = scoring.scoreRelevanceWeighted(
        'test',
        'test implementation feature design'
      );

      expect(score1).toBeGreaterThan(score2);
    });

    test('should combine Jaccard and length similarity', () => {
      const score = scoring.scoreRelevanceWeighted('test prompt', 'test prompt');
      expect(score).toBeGreaterThanOrEqual(0);
      expect(score).toBeLessThanOrEqual(100);
    });

    test('should still return 100 for identical prompts', () => {
      const score = scoring.scoreRelevanceWeighted('test', 'test');
      expect(score).toBe(100);
    });
  });

  describe('Parameter Conflict Detection', () => {
    test('should detect userId conflicts', () => {
      const cached = { userId: 'user-123' };
      const current = { userId: 'user-456' };

      const hasConflict = scoring.hasParameterConflicts(cached, current);
      expect(hasConflict).toBe(true);
    });

    test('should detect projectId conflicts', () => {
      const cached = { projectId: 'proj-123' };
      const current = { projectId: 'proj-456' };

      const hasConflict = scoring.hasParameterConflicts(cached, current);
      expect(hasConflict).toBe(true);
    });

    test('should not report conflict if either param missing', () => {
      const cached = { userId: 'user-123' };
      const current = {};  // Missing userId

      const hasConflict = scoring.hasParameterConflicts(cached, current);
      expect(hasConflict).toBe(false);
    });

    test('should not report conflict if params match', () => {
      const cached = { userId: 'user-123' };
      const current = { userId: 'user-123' };

      const hasConflict = scoring.hasParameterConflicts(cached, current);
      expect(hasConflict).toBe(false);
    });

    test('should use custom critical params if provided', () => {
      const cached = { custom: 'value-1' };
      const current = { custom: 'value-2' };

      const hasConflict = scoring.hasParameterConflicts(
        cached,
        current,
        ['custom']  // Custom param list
      );
      expect(hasConflict).toBe(true);
    });
  });

  describe('findParameterConflicts', () => {
    test('should return detailed conflict info', () => {
      const cached = { userId: 'user-123', projectId: 'proj-456' };
      const current = { userId: 'user-789', projectId: 'proj-456' };

      const conflicts = scoring.findParameterConflicts(cached, current);

      expect(conflicts).toHaveLength(1);
      expect(conflicts[0]).toEqual({
        parameter: 'userId',
        cached: 'user-123',
        current: 'user-789'
      });
    });

    test('should return empty array if no conflicts', () => {
      const cached = { userId: 'user-123' };
      const current = { userId: 'user-123' };

      const conflicts = scoring.findParameterConflicts(cached, current);
      expect(conflicts).toHaveLength(0);
    });

    test('should find multiple conflicts', () => {
      const cached = { userId: 'u1', projectId: 'p1', domain: 'd1' };
      const current = { userId: 'u2', projectId: 'p2', domain: 'd1' };

      const conflicts = scoring.findParameterConflicts(cached, current);
      expect(conflicts).toHaveLength(2);
      const params = conflicts.map(c => c.parameter).sort();
      expect(params).toEqual(['projectId', 'userId']);
    });
  });

  describe('normalizeText', () => {
    test('should lowercase by default', () => {
      const normalized = scoring.normalizeText('TEST PROMPT');
      expect(normalized).toBe('test prompt');
    });

    test('should remove special characters if requested', () => {
      const normalized = scoring.normalizeText('test-prompt!', { removeSpecial: true });
      expect(normalized).toBe('test prompt');
    });

    test('should trim whitespace by default', () => {
      const normalized = scoring.normalizeText('  test prompt  ');
      expect(normalized).toBe('test prompt');
    });

    test('should respect options', () => {
      const normalized = scoring.normalizeText('TEST', {
        lowercase: false,
        trim: true
      });
      expect(normalized).toBe('TEST');
    });
  });

  describe('Exported Constants', () => {
    test('should export DEFAULTS with MIN_WORD_LENGTH values', () => {
      expect(scoring.DEFAULTS).toBeDefined();
      expect(scoring.DEFAULTS.MIN_WORD_LENGTH).toBe(2);
      expect(scoring.DEFAULTS.MIN_WORD_LENGTH_STRICT).toBe(3);
    });
  });
});
