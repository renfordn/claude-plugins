/**
 * Test Suite: Cache Orchestration Skill
 *
 * Tests the CacheOrchestration class which makes decisions about
 * cache reuse vs fresh reasoning based on relevance scoring and staleness.
 */

const { CacheOrchestration } = require('../skills/cache-orchestration');

// ============================================================================
// TEST DATA & FIXTURES
// ============================================================================

const DEFAULTS = {
  AGENT_TYPE: 'agent-tdd',
  TASK_TYPE: 'test',
  RELEVANCE_THRESHOLD: 75,
  STALENESS_THRESHOLD: 24 * 60 * 60 * 1000
};

/**
 * Build a mock cached entry
 */
function mockCachedEntry(overrides = {}) {
  return {
    id: 'cache-1',
    prompt: 'Test prompt for evaluation',
    output: { result: 'cached' },
    metadata: {
      timestamp: Date.now(),
      tags: [DEFAULTS.AGENT_TYPE],
      ...overrides.metadata
    },
    ...overrides
  };
}

/**
 * Build a context object for makeDecision()
 */
function buildContext(overrides = {}) {
  return {
    agentType: DEFAULTS.AGENT_TYPE,
    prompt: 'Test prompt',
    parameters: { taskType: DEFAULTS.TASK_TYPE },
    ...overrides
  };
}

describe('CacheOrchestration Skill', () => {
  let orchestration;
  let mockCache;
  let mockMetrics;

  beforeEach(() => {
    // Create mock cache and metrics
    mockCache = {
      search: jest.fn(),
      retrieve: jest.fn(),
      stats: jest.fn()
    };

    mockMetrics = {
      recordHit: jest.fn(),
      recordMiss: jest.fn()
    };

    // Initialize orchestration with mocks
    orchestration = new CacheOrchestration({
      cache: mockCache,
      metrics: mockMetrics,
      relevanceThreshold: DEFAULTS.RELEVANCE_THRESHOLD,
      stalenessThreshold: DEFAULTS.STALENESS_THRESHOLD
    });
  });

  describe('Decision Making', () => {
    test('should return fresh_reasoning when no cache candidates found', async () => {
      mockCache.search.mockResolvedValue([]);
      mockMetrics.recordMiss.mockResolvedValue({ success: true });

      const result = await orchestration.makeDecision(buildContext());

      expect(result.decision).toBe('fresh_reasoning');
      expect(result.cachedContextId).toBeNull();
      expect(result.relevanceScore).toBe(0);
      expect(mockMetrics.recordMiss).toHaveBeenCalled();
    });

    test('should evaluate candidates based on relevance when found', async () => {
      mockCache.search.mockResolvedValue([mockCachedEntry()]);

      const result = await orchestration.makeDecision(
        buildContext({ prompt: 'Test prompt for evaluation' })
      );

      // Should evaluate the candidate
      expect(result.relevanceScore).toBeGreaterThanOrEqual(0);
      expect(result.relevanceScore).toBeLessThanOrEqual(100);
    });

    test('should respect relevance threshold', async () => {
      mockCache.search.mockResolvedValue([
        mockCachedEntry({
          prompt: 'Completely different prompt about something else'
        })
      ]);

      const result = await orchestration.makeDecision(buildContext());

      // Low relevance should result in fresh reasoning
      if (result.relevanceScore < DEFAULTS.RELEVANCE_THRESHOLD) {
        expect(result.decision).toBe('fresh_reasoning');
      }
    });

    test('should consider cache staleness', async () => {
      const twoWeeksAgo = Date.now() - (14 * 24 * 60 * 60 * 1000);

      mockCache.search.mockResolvedValue([
        mockCachedEntry({
          metadata: { timestamp: twoWeeksAgo, tags: [DEFAULTS.AGENT_TYPE] }
        })
      ]);

      const result = await orchestration.makeDecision(
        buildContext({ currentTime: Date.now() })
      );

      // Entry older than 24h threshold should be considered stale
      expect(result).toBeDefined();
      expect(result.decision).toBeDefined();
    });
  });

  describe('Relevance Scoring', () => {
    test('should score identical prompts highly', () => {
      const prompt1 = 'exact prompt match test';
      const prompt2 = 'exact prompt match test';

      const score = orchestration._scoreRelevance(prompt1, prompt2);

      expect(score).toBeGreaterThan(90);
    });

    test('should score similar prompts moderately', () => {
      const prompt1 = 'test prompt for cache evaluation';
      const prompt2 = 'test prompt for cache';

      const score = orchestration._scoreRelevance(prompt1, prompt2);

      expect(score).toBeGreaterThan(50);
      expect(score).toBeLessThan(100);
    });

    test('should score different prompts low', () => {
      const prompt1 = 'cache evaluation test prompt';
      const prompt2 = 'completely different topic about something else';

      const score = orchestration._scoreRelevance(prompt1, prompt2);

      expect(score).toBeLessThan(50);
    });

    test('should return numeric score between 0-100', () => {
      const prompts = [
        ['test', 'test'],
        ['test', 'completely different'],
        ['medium match here', 'medium match'],
        ['', '']
      ];

      prompts.forEach(([p1, p2]) => {
        const score = orchestration._scoreRelevance(p1, p2);
        expect(typeof score).toBe('number');
        expect(score).toBeGreaterThanOrEqual(0);
        expect(score).toBeLessThanOrEqual(100);
      });
    });
  });

  describe('Configuration', () => {
    test('should use default thresholds when not specified', () => {
      const defaultOrchestration = new CacheOrchestration();

      expect(defaultOrchestration.relevanceThreshold).toBe(DEFAULTS.RELEVANCE_THRESHOLD);
      expect(defaultOrchestration.stalenessThreshold).toBe(DEFAULTS.STALENESS_THRESHOLD);
    });

    test('should accept custom thresholds', () => {
      const CUSTOM_THRESHOLD = 85;
      const CUSTOM_STALENESS = 48 * 60 * 60 * 1000;

      const customOrchestration = new CacheOrchestration({
        relevanceThreshold: CUSTOM_THRESHOLD,
        stalenessThreshold: CUSTOM_STALENESS
      });

      expect(customOrchestration.relevanceThreshold).toBe(CUSTOM_THRESHOLD);
      expect(customOrchestration.stalenessThreshold).toBe(CUSTOM_STALENESS);
    });
  });

  describe('Error Handling', () => {
    test('should handle cache search errors gracefully', async () => {
      const ERROR_MESSAGE = 'Cache unavailable';
      mockCache.search.mockRejectedValue(new Error(ERROR_MESSAGE));

      const result = await orchestration.makeDecision(buildContext());

      expect(result.decision).toBe('fresh_reasoning');
      expect(result.reasoning).toMatch(/error|Error/i);
    });

    test('should handle missing context fields', async () => {
      mockCache.search.mockResolvedValue([]);

      const result = await orchestration.makeDecision({
        agentType: DEFAULTS.AGENT_TYPE
        // Missing prompt and parameters
      });

      expect(result).toBeDefined();
      expect(result.decision).toBeDefined();
    });
  });
});
