/**
 * Integration Tests for Agent-Cache Plugin
 *
 * Covers full workflows: cache operations, metrics tracking, and CLI commands
 */

const cacheManagement = require('../skills/cache-management');
const metricsTracker = require('../skills/metrics-tracker');
const cacheOrchestrator = require('../agents/agent-cache-orchestrator');
const cacheValidator = require('../agents/cache-validator');
const cacheStatusCmd = require('../commands/cache-status');
const cacheClearCmd = require('../commands/cache-clear');
const cacheConfigCmd = require('../commands/cache-config');

describe('Agent-Cache Plugin Integration Tests', () => {
  let cache, metrics, orchestrator, validator;

  beforeEach(() => {
    cache = cacheManagement.resetSingleton();
    metrics = metricsTracker.resetSingleton();
    orchestrator = cacheOrchestrator.create();
    validator = cacheValidator.create();
  });

  describe('Full Cache Workflow', () => {
    test('should complete store-retrieve-hit cycle', async () => {
      // Store entry
      const entry = {
        prompt: 'Test prompt for workflow',
        output: 'Test output result',
        metadata: {
          agentType: 'agent-tdd',
          taskType: 'research',
          tags: ['test', 'workflow'],
          tokenCount: 250
        }
      };

      const stored = await cache.store(entry);
      expect(stored.success).toBe(true);
      expect(stored.entryId).toBeDefined();

      // Retrieve entry
      const retrieved = await cache.retrieve(stored.entryId);
      expect(retrieved.found).toBe(true);
      expect(retrieved.entry.prompt).toBe(entry.prompt);

      // Make cache decision using orchestrator
      const decision = await orchestrator.makeDecision({
        agentType: 'agent-tdd',
        prompt: 'Test prompt for workflow',
        parameters: { taskType: 'research' }
      });

      expect(decision.decision).toBe('use_cache');
      expect(decision.relevanceScore).toBeGreaterThan(70);
      expect(decision.cachedContextId).toBe(stored.entryId);
    });

    test('should invalidate and track misses', async () => {
      // Store entry
      const entry = {
        prompt: 'Test prompt',
        output: 'Result',
        metadata: {
          agentType: 'test-agent',
          taskType: 'test',
          tags: ['test']
        }
      };

      const stored = await cache.store(entry);

      // Invalidate
      const invalidated = await cache.invalidate(stored.entryId);
      expect(invalidated.count).toBe(1);

      // Try to retrieve - should fail
      const retrieved = await cache.retrieve(stored.entryId);
      expect(retrieved.found).toBe(false);

      // Record miss
      const miss = await metrics.recordMiss({
        query: 'Test prompt',
        taskType: 'test'
      });
      expect(miss.success).toBe(true);
    });

    test('should enforce cache size limits', async () => {
      // Configure small cache
      await cache.configure({
        maxSize: 10 * 1024, // 10 KB
        maxEntries: 5
      });

      // Add multiple entries
      const entries = [];
      for (let i = 0; i < 10; i++) {
        const entry = {
          prompt: `Prompt ${i}`,
          output: 'X'.repeat(1000),
          metadata: {
            agentType: 'test-agent',
            tags: ['test']
          }
        };
        const stored = await cache.store(entry);
        if (stored.success) {
          entries.push(stored.entryId);
        }
      }

      // Verify size limits enforced
      const stats = await cache.getStats();
      expect(stats.totalEntries).toBeLessThanOrEqual(5);
      expect(stats.cacheSize).toBeLessThanOrEqual(10 * 1024);
    });
  });

  describe('Metrics Tracking', () => {
    test('should track hits and misses', async () => {
      // Record multiple events
      await metrics.recordHit({
        cachedEntryId: 'entry-1',
        taskType: 'research',
        agentType: 'agent-tdd',
        tokensSaved: 300
      });

      await metrics.recordMiss({
        query: 'test query',
        taskType: 'research'
      });

      await metrics.recordHit({
        cachedEntryId: 'entry-2',
        taskType: 'implementation',
        agentType: 'agent-tdd',
        tokensSaved: 200
      });

      // Check hit rate
      const hitRate = await metrics.getHitRate();
      expect(hitRate.hitRate).toBeCloseTo(0.67, 1); // 2 hits / 3 queries
      expect(hitRate.totalHits).toBe(2);
      expect(hitRate.totalMisses).toBe(1);
    });

    test('should calculate token savings', async () => {
      // Record hits with varying savings
      await metrics.recordHit({
        cachedEntryId: 'entry-1',
        tokensSaved: 500
      });

      await metrics.recordHit({
        cachedEntryId: 'entry-2',
        tokensSaved: 300
      });

      const savings = await metrics.getTokenSavings();
      expect(savings.totalTokensSaved).toBe(800);
      expect(savings.avgPerHit).toBe(400);
      expect(savings.maxSingleSave).toBe(500);
      expect(savings.estimatedCostReduction).toContain('$');
    });

    test('should generate performance metrics', async () => {
      // Record events with timing
      await metrics.recordHit({
        cachedEntryId: 'entry-1',
        taskType: 'research',
        agentType: 'agent-tdd',
        retrievalTimeMs: 5
      });

      await metrics.recordHit({
        cachedEntryId: 'entry-2',
        taskType: 'implementation',
        agentType: 'agent-isdd',
        retrievalTimeMs: 8
      });

      const perf = await metrics.getPerformanceMetrics();
      expect(perf.cacheRetrievalTime.avg).toBeLessThan(10);
      expect(perf.taskBreakdown).toBeDefined();
      expect(perf.agentBreakdown).toBeDefined();
    });

    test('should provide recommendations', async () => {
      // Setup for low hit rate scenario
      for (let i = 0; i < 10; i++) {
        await metrics.recordMiss({ query: `query-${i}` });
      }
      await metrics.recordHit({ cachedEntryId: 'entry-1', tokensSaved: 100 });

      const recommendations = await metrics.getRecommendations();
      expect(recommendations.suggestions).toBeDefined();
      // Low hit rate should trigger recommendation
      const hasLowHitRateRecommendation = recommendations.suggestions.some(
        s => s.area === 'relevance-scoring'
      );
      expect(hasLowHitRateRecommendation).toBe(true);
    });
  });

  describe('Agent Orchestration', () => {
    test('should make cache reuse decision', async () => {
      // Setup cached entry
      const entry = {
        prompt: 'Implement user authentication',
        output: 'Auth implementation details',
        metadata: {
          agentType: 'agent-tdd',
          taskType: 'implementation',
          tags: ['agent-tdd', 'implementation'],
          tokenCount: 500
        }
      };

      const stored = await cache.store(entry);

      // Make decision with similar prompt
      const decision = await orchestrator.makeDecision({
        agentType: 'agent-tdd',
        prompt: 'Implement user authentication module',
        parameters: { taskType: 'implementation' }
      });

      expect(decision.decision).toBe('use_cache');
      expect(decision.relevanceScore).toBeGreaterThanOrEqual(60);
    });

    test('should detect conflicts in cached contexts', async () => {
      const cached = {
        id: 'entry-1',
        prompt: 'Process user data',
        output: 'User processing logic',
        metadata: {
          timestamp: Date.now(),
          ttl: 24 * 60 * 60 * 1000,
          parameters: { userId: 'user-123', projectId: 'proj-1' }
        }
      };

      const validation = await orchestrator.validateCachedContext(
        cached.id,
        {
          prompt: 'Process user data',
          parameters: { userId: 'user-456', projectId: 'proj-1' }
        }
      );

      expect(validation.isValid).toBe(false);
      expect(validation.recommendation).toBe('discard');
    });
  });

  describe('Entry Validation', () => {
    test('should validate cache entry integrity', async () => {
      const validEntry = {
        id: 'test-123',
        prompt: 'Test prompt',
        output: 'Test output',
        metadata: {
          timestamp: Date.now(),
          ttl: 24 * 60 * 60 * 1000,
          agentType: 'test-agent'
        }
      };

      const validation = await validator.validate(
        validEntry,
        { task: 'Test prompt', parameters: {} }
      );

      expect(validation.isValid).toBe(true);
      expect(validation.confidence).toBeGreaterThan(50);
    });

    test('should detect stale entries', async () => {
      const staleEntry = {
        id: 'stale-1',
        prompt: 'Old prompt',
        output: 'Old output',
        metadata: {
          timestamp: Date.now() - (10 * 24 * 60 * 60 * 1000), // 10 days ago
          ttl: 7 * 24 * 60 * 60 * 1000, // 7 day TTL
          agentType: 'test-agent'
        }
      };

      const validation = await validator.validate(
        staleEntry,
        { task: 'New task', parameters: {} }
      );

      expect(validation.isStale).toBe(true);
      expect(validation.isValid).toBe(false);
    });

    test('should score relevance correctly', async () => {
      const entry = {
        id: 'rel-1',
        prompt: 'Implement authentication module',
        output: 'Auth implementation',
        metadata: {
          timestamp: Date.now(),
          ttl: 24 * 60 * 60 * 1000,
          agentType: 'test-agent'
        }
      };

      // High relevance
      let validation = await validator.validate(
        entry,
        { task: 'Implement authentication', parameters: {} }
      );
      expect(validation.relevanceScore).toBeGreaterThan(65);

      // Low relevance
      validation = await validator.validate(
        entry,
        { task: 'Unrelated task completely different', parameters: {} }
      );
      expect(validation.relevanceScore).toBeLessThan(50);
    });
  });

  describe('CLI Commands', () => {
    test('should execute cache-status command', async () => {
      // Add some data
      await cache.store({
        prompt: 'Test',
        output: 'Result',
        metadata: { agentType: 'test' }
      });

      const result = await cacheStatusCmd.execute({ list: true });
      expect(result.status).toBe('success');
      expect(result.metrics).toBeDefined();
      expect(result.report).toContain('Cache Status Report');
    });

    test('should execute cache-clear command', async () => {
      // Add entries
      const entry1 = await cache.store({
        prompt: 'Prompt 1',
        output: 'Output 1',
        metadata: { agentType: 'agent-tdd', tags: ['test'] }
      });

      const entry2 = await cache.store({
        prompt: 'Prompt 2',
        output: 'Output 2',
        metadata: { agentType: 'other-agent', tags: ['other'] }
      });

      // Clear agent-tdd entries
      const result = await cacheClearCmd.execute({
        agent: 'agent-tdd'
      });

      expect(result.status).toBe('success');
      expect(result.summary.entriesRemoved).toBeGreaterThan(0);
    });

    test('should execute cache-config command', async () => {
      // List config
      let result = await cacheConfigCmd.execute({ list: true });
      expect(result.status).toBe('success');
      expect(result.config).toBeDefined();

      // Get specific config
      result = await cacheConfigCmd.execute({ get: 'maxSize' });
      expect(result.status).toBe('success');
      expect(result.value).toBeDefined();

      // Validate config
      result = await cacheConfigCmd.execute({ validate: true });
      expect(result.status).toBe('success');
      expect(result.validation).toBeDefined();
    });
  });

  describe('End-to-End Workflow', () => {
    test('should complete full cache workflow with metrics', async () => {
      // 1. Store agent output
      const agentOutput = {
        prompt: 'Design user authentication system',
        output: 'Comprehensive auth design with OAuth2 and JWT',
        metadata: {
          agentType: 'agent-isdd',
          taskType: 'design',
          tags: ['design', 'auth', 'agent-isdd'],
          tokenCount: 1200
        }
      };

      const stored = await cache.store(agentOutput);
      expect(stored.success).toBe(true);

      // 2. Make cache decision for similar task
      const decision = await orchestrator.makeDecision({
        agentType: 'agent-isdd',
        prompt: 'Design authentication system using OAuth',
        parameters: { taskType: 'design' }
      });

      if (decision.decision === 'use_cache') {
        // 3. Record hit
        await metrics.recordHit({
          cachedEntryId: decision.cachedContextId,
          taskType: 'design',
          agentType: 'agent-isdd',
          tokensSaved: decision.tokenSavings,
          relevanceScore: decision.relevanceScore
        });
      }

      // 4. Get status
      const status = await cacheStatusCmd.execute({ list: true });
      expect(status.status).toBe('success');
      expect(status.metrics.entries).toBeGreaterThan(0);
    });
  });

  describe('Error Handling', () => {
    test('should handle invalid cache operations', async () => {
      // Try to retrieve non-existent entry
      const result = await cache.retrieve('non-existent-id');
      expect(result.found).toBe(false);
    });

    test('should validate configuration values', async () => {
      // Try to set invalid TTL
      const result = await cacheConfigCmd.execute({
        set: true,
        key: 'defaultTTL',
        value: '100ms' // Too short
      });

      expect(result.status).toBe('error');
    });

    test('should handle concurrent operations', async () => {
      const promises = [];

      for (let i = 0; i < 5; i++) {
        promises.push(
          cache.store({
            prompt: `Prompt ${i}`,
            output: `Output ${i}`,
            metadata: { agentType: 'test' }
          })
        );
      }

      const results = await Promise.all(promises);
      expect(results.every(r => r.success)).toBe(true);
      expect(results).toHaveLength(5);
    });
  });
});
