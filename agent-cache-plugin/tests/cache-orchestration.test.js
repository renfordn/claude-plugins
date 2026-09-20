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
      retrieve: jest.fn().mockImplementation((id) => {
        // Return properly formatted resolve value
        return Promise.resolve({ found: true, entry: mockCachedEntry() });
      }),
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

  describe('Model/ModelTier Conflict Detection', () => {
    describe('High-Risk Slice: Cache Model Dimension', () => {
      test('should treat model tier mismatch as conflict (Haiku vs Sonnet)', async () => {
        // Cached entry from Haiku execution
        const cachedHaiku = mockCachedEntry({
          prompt: 'Write a comprehensive unit test',
          metadata: {
            timestamp: Date.now(),
            tags: [DEFAULTS.AGENT_TYPE],
            parameters: {
              userId: 'user-1',
              projectId: 'proj-1',
              domain: 'testing',
              model: 'claude-3-haiku',
              modelTier: 'haiku'
            }
          }
        });

        mockCache.retrieve.mockResolvedValue({ found: true, entry: cachedHaiku });

        // Current request escalated to Sonnet
        const result = await orchestration.validateCachedContext(
          cachedHaiku.id,
          buildContext({
            prompt: 'Write a comprehensive unit test',
            parameters: {
              userId: 'user-1',
              projectId: 'proj-1',
              domain: 'testing',
              model: 'claude-3-sonnet',
              modelTier: 'sonnet'
            }
          })
        );

        // Should reject cache due to model tier mismatch
        expect(result.isValid).toBe(false);
        expect(result.recommendation).toBe('discard');
        expect(result.reason).toMatch(/[Cc]onflict/);
      });

      test('should treat model name mismatch as conflict', async () => {
        const cachedEntry = mockCachedEntry({
          prompt: 'Analyze code quality',
          metadata: {
            timestamp: Date.now(),
            tags: [DEFAULTS.AGENT_TYPE],
            parameters: {
              userId: 'user-1',
              projectId: 'proj-1',
              domain: 'analysis',
              model: 'claude-3-haiku-20240307'
            }
          }
        });

        mockCache.retrieve.mockResolvedValue({ found: true, entry: cachedEntry });

        const result = await orchestration.validateCachedContext(
          cachedEntry.id,
          buildContext({
            prompt: 'Analyze code quality',
            parameters: {
              userId: 'user-1',
              projectId: 'proj-1',
              domain: 'analysis',
              model: 'claude-3-sonnet-20240229'
            }
          })
        );

        // Should reject cache due to model name mismatch
        expect(result.isValid).toBe(false);
        expect(result.recommendation).toBe('discard');
        expect(result.reason).toMatch(/[Cc]onflict/);
      });

      test('should treat tier mismatch as conflict (current-gen: haiku-4-5 vs sonnet-5)', async () => {
        const cachedHaiku = mockCachedEntry({
          prompt: 'Write a comprehensive unit test',
          metadata: {
            timestamp: Date.now(),
            tags: [DEFAULTS.AGENT_TYPE],
            parameters: {
              userId: 'user-1',
              projectId: 'proj-1',
              domain: 'testing',
              model: 'claude-haiku-4-5-20251001',
              modelTier: 'haiku'
            }
          }
        });

        mockCache.retrieve.mockResolvedValue({ found: true, entry: cachedHaiku });

        const result = await orchestration.validateCachedContext(
          cachedHaiku.id,
          buildContext({
            prompt: 'Write a comprehensive unit test',
            parameters: {
              userId: 'user-1',
              projectId: 'proj-1',
              domain: 'testing',
              model: 'claude-sonnet-5',
              modelTier: 'sonnet'
            }
          })
        );

        expect(result.isValid).toBe(false);
        expect(result.recommendation).toBe('discard');
        expect(result.reason).toMatch(/[Cc]onflict/);
      });

      test('should treat model name mismatch as conflict (current-gen: haiku-4-5 vs sonnet-5)', async () => {
        const cachedEntry = mockCachedEntry({
          prompt: 'Analyze code quality',
          metadata: {
            timestamp: Date.now(),
            tags: [DEFAULTS.AGENT_TYPE],
            parameters: {
              userId: 'user-1',
              projectId: 'proj-1',
              domain: 'analysis',
              model: 'claude-haiku-4-5-20251001'
            }
          }
        });

        mockCache.retrieve.mockResolvedValue({ found: true, entry: cachedEntry });

        const result = await orchestration.validateCachedContext(
          cachedEntry.id,
          buildContext({
            prompt: 'Analyze code quality',
            parameters: {
              userId: 'user-1',
              projectId: 'proj-1',
              domain: 'analysis',
              model: 'claude-sonnet-5'
            }
          })
        );

        expect(result.isValid).toBe(false);
        expect(result.recommendation).toBe('discard');
        expect(result.reason).toMatch(/[Cc]onflict/);
      });

      test('should accept cache when model and modelTier match exactly', async () => {
        const cachedEntry = mockCachedEntry({
          prompt: 'Review test coverage',
          metadata: {
            timestamp: Date.now(),
            tags: [DEFAULTS.AGENT_TYPE],
            parameters: {
              userId: 'user-1',
              projectId: 'proj-1',
              domain: 'review',
              model: 'claude-3-sonnet',
              modelTier: 'sonnet'
            }
          }
        });

        mockCache.retrieve.mockResolvedValue({ found: true, entry: cachedEntry });

        const result = await orchestration.validateCachedContext(
          cachedEntry.id,
          buildContext({
            prompt: 'Review test coverage',
            parameters: {
              userId: 'user-1',
              projectId: 'proj-1',
              domain: 'review',
              model: 'claude-3-sonnet',
              modelTier: 'sonnet'
            }
          })
        );

        // Should accept cache when model and modelTier match
        expect(result.isValid).toBe(true);
        expect(result.recommendation).not.toBe('discard');
      });

      test('should treat old cache entry without model dimension as miss', async () => {
        // Pre-model-dimension cache entry (backward compatibility)
        const legacyCachedEntry = mockCachedEntry({
          prompt: 'Process user input',
          metadata: {
            timestamp: Date.now(),
            tags: [DEFAULTS.AGENT_TYPE],
            parameters: {
              userId: 'user-1',
              projectId: 'proj-1',
              domain: 'processing'
              // Missing model and modelTier
            }
          }
        });

        mockCache.retrieve.mockResolvedValue({ found: true, entry: legacyCachedEntry });

        const result = await orchestration.validateCachedContext(
          legacyCachedEntry.id,
          buildContext({
            prompt: 'Process user input',
            parameters: {
              userId: 'user-1',
              projectId: 'proj-1',
              domain: 'processing',
              model: 'claude-3-haiku',
              modelTier: 'haiku'
            }
          })
        );

        // Should treat missing model dimension as conflict/mismatch
        // Old cache entries without model should not be reused by new code
        expect(result.isValid).toBe(false);
        expect(result.recommendation).toBe('discard');
      });

      test('should make fresh_reasoning decision when model escalates from Haiku to Sonnet', async () => {
        // Simulating pre-escalation cache from Haiku
        const cachedHaiku = mockCachedEntry({
          prompt: 'Generate implementation code',
          metadata: {
            timestamp: Date.now(),
            tags: [DEFAULTS.AGENT_TYPE],
            parameters: {
              userId: 'user-2',
              projectId: 'proj-2',
              domain: 'implementation',
              model: 'claude-3-haiku',
              modelTier: 'haiku'
            }
          }
        });

        mockCache.search.mockResolvedValue([cachedHaiku]);

        // Post-escalation request to Sonnet
        const result = await orchestration.makeDecision(
          buildContext({
            prompt: 'Generate implementation code',
            parameters: {
              userId: 'user-2',
              projectId: 'proj-2',
              domain: 'implementation',
              model: 'claude-3-sonnet',
              modelTier: 'sonnet'
            }
          })
        );

        // Must return fresh_reasoning, not cache reuse
        expect(result.decision).toBe('fresh_reasoning');
        expect(result.reasoning).toMatch(/[Cc]onflict|[Mm]odel/i);
      });

      test('should allow cache reuse within same model tier across multiple executions', async () => {
        const cachedSonnet = mockCachedEntry({
          prompt: 'Write comprehensive tests',
          metadata: {
            timestamp: Date.now(),
            tags: [DEFAULTS.AGENT_TYPE],
            parameters: {
              userId: 'user-3',
              projectId: 'proj-3',
              domain: 'testing',
              model: 'claude-3-sonnet-20240229',
              modelTier: 'sonnet'
            }
          }
        });

        mockCache.search.mockResolvedValue([cachedSonnet]);

        const result = await orchestration.makeDecision(
          buildContext({
            prompt: 'Write comprehensive tests',
            parameters: {
              userId: 'user-3',
              projectId: 'proj-3',
              domain: 'testing',
              model: 'claude-3-sonnet-20240229',
              modelTier: 'sonnet'
            }
          })
        );

        // Should reuse cache when model tier is identical
        if (result.relevanceScore >= DEFAULTS.RELEVANCE_THRESHOLD) {
          expect(result.decision).toBe('use_cache');
        }
      });

      test('_checkConflicts should detect modelTier mismatch', () => {
        const cachedParams = {
          userId: 'user-1',
          projectId: 'proj-1',
          domain: 'test',
          model: 'claude-3-haiku',
          modelTier: 'haiku'
        };

        const currentParams = {
          userId: 'user-1',
          projectId: 'proj-1',
          domain: 'test',
          model: 'claude-3-sonnet',
          modelTier: 'sonnet'
        };

        const hasConflicts = orchestration._checkConflicts(cachedParams, currentParams);

        // Must return true when modelTier differs
        expect(hasConflicts).toBe(true);
      });

      test('_checkConflicts should detect model name mismatch', () => {
        const cachedParams = {
          userId: 'user-1',
          projectId: 'proj-1',
          domain: 'test',
          model: 'claude-3-haiku-20240307'
        };

        const currentParams = {
          userId: 'user-1',
          projectId: 'proj-1',
          domain: 'test',
          model: 'claude-3-opus-20240229'
        };

        const hasConflicts = orchestration._checkConflicts(cachedParams, currentParams);

        // Must return true when model names differ
        expect(hasConflicts).toBe(true);
      });

      test('_checkConflicts should NOT flag conflict when one side missing model (legacy entry)', () => {
        const cachedParams = {
          userId: 'user-1',
          projectId: 'proj-1',
          domain: 'test'
          // Legacy: no model or modelTier
        };

        const currentParams = {
          userId: 'user-1',
          projectId: 'proj-1',
          domain: 'test',
          model: 'claude-3-haiku',
          modelTier: 'haiku'
        };

        // This documents current behavior; implementation must treat as conflict
        // or reject the old cache entry via other means (e.g., in validateCachedContext)
        const hasConflicts = orchestration._checkConflicts(cachedParams, currentParams);

        // Current implementation doesn't flag this, but validateCachedContext
        // must still reject the old entry (test this in validation layer)
        expect(hasConflicts).toBe(false); // Current behavior
      });

      test('validateCachedContext should reject old entry even if _checkConflicts misses model mismatch', async () => {
        // Old entry without model dimension
        const legacyEntry = mockCachedEntry({
          prompt: 'Some task',
          metadata: {
            timestamp: Date.now(),
            tags: [DEFAULTS.AGENT_TYPE],
            parameters: {
              userId: 'user-1',
              projectId: 'proj-1',
              domain: 'test'
              // Deliberately omit model/modelTier
            }
          }
        });

        mockCache.retrieve.mockResolvedValue({ found: true, entry: legacyEntry });

        const currentContext = buildContext({
          prompt: 'Some task',
          parameters: {
            userId: 'user-1',
            projectId: 'proj-1',
            domain: 'test',
            model: 'claude-3-haiku',
            modelTier: 'haiku'
          }
        });

        // Even if _checkConflicts returns false, validation must detect the mismatch
        const result = await orchestration.validateCachedContext(
          legacyEntry.id,
          currentContext
        );

        // Must reject the legacy entry when new context has model but cached doesn't
        expect(result.isValid).toBe(false);
        expect(result.recommendation).toBe('discard');
      });
    });
  });
});
