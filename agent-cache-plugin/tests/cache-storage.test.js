/**
 * Test Suite: Persistent Cache Storage
 *
 * Comprehensive RED tests for PersistentCacheStorage class with in-memory backend.
 * Tests verify interface contract, TTL enforcement, search, invalidation, metrics,
 * and concurrent safety.
 */

const PersistentCacheStorage = require('../skills/cache-storage');

describe('PersistentCacheStorage', () => {
  let storage;

  beforeEach(async () => {
    storage = new PersistentCacheStorage({ backendType: 'memory' });
    await storage.initialize();
  });

  /**
   * Suite 1: Basic Store/Retrieve (5 assertions)
   */
  describe('Suite 1: Basic Store/Retrieve', () => {
    test('should store single entry and retrieve by ID', async () => {
      const entry = {
        prompt: 'What is the capital of France?',
        output: JSON.stringify({ answer: 'Paris' }),
        metadata: {
          agentType: 'research-agent',
          taskType: 'question-answering',
          tags: ['geography', 'capitals'],
          tokenCount: 45,
          inputTokens: 12,
          outputTokens: 8,
          executionTime: 234,
          timestamp: Date.now(),
          ttl: 24 * 60 * 60 * 1000,
          parameters: { model: 'claude-3', temperature: 0.7 }
        }
      };

      const storeResult = await storage.store(entry);
      expect(storeResult.success).toBe(true);
      expect(storeResult.entryId).toBeTruthy();
      expect(typeof storeResult.entryId).toBe('string');

      const retrieved = await storage.retrieve(storeResult.entryId);
      expect(retrieved).not.toBeNull();
      expect(retrieved.prompt).toBe(entry.prompt);
      expect(retrieved.output).toBe(entry.output);
    });

    test('should preserve all entry data fields exactly on round-trip', async () => {
      const originalEntry = {
        prompt: 'Test prompt with special chars: !@#$%^&*()',
        output: JSON.stringify({ nested: { data: [1, 2, 3], unicode: '你好世界' } }),
        metadata: {
          agentType: 'test-agent',
          taskType: 'data-processing',
          tags: ['test', 'unicode', 'special-chars'],
          tokenCount: 1234,
          inputTokens: 567,
          outputTokens: 890,
          executionTime: 5000,
          timestamp: 1692230400000,
          ttl: 3600000,
          parameters: {
            key1: 'value1',
            nested: { key2: 'value2' },
            array: [1, 'two', { three: 3 }]
          }
        }
      };

      const { entryId } = await storage.store(originalEntry);
      const retrieved = await storage.retrieve(entryId);

      expect(retrieved.prompt).toBe(originalEntry.prompt);
      expect(retrieved.output).toBe(originalEntry.output);
      expect(retrieved.metadata.agentType).toBe(originalEntry.metadata.agentType);
      expect(retrieved.metadata.taskType).toBe(originalEntry.metadata.taskType);
      expect(retrieved.metadata.tags).toEqual(originalEntry.metadata.tags);
      expect(retrieved.metadata.tokenCount).toBe(originalEntry.metadata.tokenCount);
      expect(retrieved.metadata.inputTokens).toBe(originalEntry.metadata.inputTokens);
      expect(retrieved.metadata.outputTokens).toBe(originalEntry.metadata.outputTokens);
      expect(retrieved.metadata.executionTime).toBe(originalEntry.metadata.executionTime);
      expect(retrieved.metadata.timestamp).toBe(originalEntry.metadata.timestamp);
      expect(retrieved.metadata.ttl).toBe(originalEntry.metadata.ttl);
      expect(retrieved.metadata.parameters).toEqual(originalEntry.metadata.parameters);
    });

    test('should return null for non-existent entry ID', async () => {
      const retrieved = await storage.retrieve('nonexistent-id-xyz-123');
      expect(retrieved).toBeNull();
    });

    test('should store and retrieve multiple entries independently', async () => {
      const entry1 = {
        prompt: 'Question 1',
        output: 'Answer 1',
        metadata: { agentType: 'agent-a', taskType: 'task-1', tags: [], timestamp: Date.now(), ttl: 3600000 }
      };
      const entry2 = {
        prompt: 'Question 2',
        output: 'Answer 2',
        metadata: { agentType: 'agent-b', taskType: 'task-2', tags: [], timestamp: Date.now(), ttl: 3600000 }
      };

      const result1 = await storage.store(entry1);
      const result2 = await storage.store(entry2);

      expect(result1.entryId).not.toBe(result2.entryId);

      const retrieved1 = await storage.retrieve(result1.entryId);
      const retrieved2 = await storage.retrieve(result2.entryId);

      expect(retrieved1.prompt).toBe('Question 1');
      expect(retrieved2.prompt).toBe('Question 2');
      expect(retrieved1.metadata.agentType).toBe('agent-a');
      expect(retrieved2.metadata.agentType).toBe('agent-b');
    });

    test('should update entry when storing with same ID (overwrite)', async () => {
      const entry1 = {
        prompt: 'Original prompt',
        output: 'Original output',
        metadata: { agentType: 'agent-x', taskType: 'task-x', tags: [], timestamp: Date.now(), ttl: 3600000 }
      };

      const { entryId } = await storage.store(entry1);
      let retrieved = await storage.retrieve(entryId);
      expect(retrieved.prompt).toBe('Original prompt');

      const entry2 = {
        id: entryId,
        prompt: 'Updated prompt',
        output: 'Updated output',
        metadata: { agentType: 'agent-y', taskType: 'task-y', tags: [], timestamp: Date.now(), ttl: 3600000 }
      };

      await storage.store(entry2);
      retrieved = await storage.retrieve(entryId);

      expect(retrieved.prompt).toBe('Updated prompt');
      expect(retrieved.output).toBe('Updated output');
      expect(retrieved.metadata.agentType).toBe('agent-y');
    });
  });

  /**
   * Suite 2: TTL Enforcement (4 assertions)
   */
  describe('Suite 2: TTL Enforcement', () => {
    test('should return null when entry TTL has expired', async () => {
      const entry = {
        prompt: 'Expiring prompt',
        output: 'Expiring output',
        metadata: {
          agentType: 'test-agent',
          taskType: 'test-task',
          tags: [],
          timestamp: Date.now() - 2000, // 2 seconds ago
          ttl: 1000 // Expired 1 second ago
        }
      };

      const { entryId } = await storage.store(entry);
      const retrieved = await storage.retrieve(entryId);

      expect(retrieved).toBeNull();
    });

    test('should return entry when TTL has not expired', async () => {
      const entry = {
        prompt: 'Non-expiring prompt',
        output: 'Non-expiring output',
        metadata: {
          agentType: 'test-agent',
          taskType: 'test-task',
          tags: [],
          timestamp: Date.now() - 500, // 500ms ago
          ttl: 10000 // Expires in ~9.5 seconds
        }
      };

      const { entryId } = await storage.store(entry);
      const retrieved = await storage.retrieve(entryId);

      expect(retrieved).not.toBeNull();
      expect(retrieved.prompt).toBe('Non-expiring prompt');
    });

    test('should persist indefinitely when TTL is null or not set', async () => {
      const entry1 = {
        prompt: 'No TTL prompt',
        output: 'No TTL output',
        metadata: {
          agentType: 'test-agent',
          taskType: 'test-task',
          tags: [],
          timestamp: Date.now() - 100000,
          ttl: null
        }
      };

      const entry2 = {
        prompt: 'Undefined TTL prompt',
        output: 'Undefined TTL output',
        metadata: {
          agentType: 'test-agent',
          taskType: 'test-task',
          tags: [],
          timestamp: Date.now() - 100000
          // ttl not set
        }
      };

      const result1 = await storage.store(entry1);
      const result2 = await storage.store(entry2);

      const retrieved1 = await storage.retrieve(result1.entryId);
      const retrieved2 = await storage.retrieve(result2.entryId);

      expect(retrieved1).not.toBeNull();
      expect(retrieved2).not.toBeNull();
    });

    test('should handle multiple entries with different TTLs correctly', async () => {
      const now = Date.now();
      const entryExpired = {
        prompt: 'Will expire',
        output: 'Expired output',
        metadata: { agentType: 'a', taskType: 't1', tags: [], timestamp: now - 3000, ttl: 1000 }
      };
      const entryValid = {
        prompt: 'Will not expire',
        output: 'Valid output',
        metadata: { agentType: 'b', taskType: 't2', tags: [], timestamp: now - 1000, ttl: 5000 }
      };
      const entryNoTTL = {
        prompt: 'No expiration',
        output: 'No expiration output',
        metadata: { agentType: 'c', taskType: 't3', tags: [], timestamp: now - 10000, ttl: null }
      };

      const resExpired = await storage.store(entryExpired);
      const resValid = await storage.store(entryValid);
      const resNoTTL = await storage.store(entryNoTTL);

      const retrievedExpired = await storage.retrieve(resExpired.entryId);
      const retrievedValid = await storage.retrieve(resValid.entryId);
      const retrievedNoTTL = await storage.retrieve(resNoTTL.entryId);

      expect(retrievedExpired).toBeNull();
      expect(retrievedValid).not.toBeNull();
      expect(retrievedNoTTL).not.toBeNull();
    });
  });

  /**
   * Suite 3: Search & Filter (5 assertions)
   */
  describe('Suite 3: Search & Filter', () => {
    beforeEach(async () => {
      // Populate storage with test data
      await storage.store({
        prompt: 'Research query 1',
        output: 'Output 1',
        metadata: {
          agentType: 'research-agent',
          taskType: 'web-search',
          tags: ['research', 'urgent'],
          timestamp: Date.now(),
          ttl: 3600000
        }
      });
      await storage.store({
        prompt: 'Research query 2',
        output: 'Output 2',
        metadata: {
          agentType: 'research-agent',
          taskType: 'data-analysis',
          tags: ['research', 'data'],
          timestamp: Date.now(),
          ttl: 3600000
        }
      });
      await storage.store({
        prompt: 'Code generation query',
        output: 'Output 3',
        metadata: {
          agentType: 'code-gen-agent',
          taskType: 'code-generation',
          tags: ['coding', 'python'],
          timestamp: Date.now(),
          ttl: 3600000
        }
      });
    });

    test('should search by agentType and return matching entries', async () => {
      const results = await storage.search({ agentType: 'research-agent' });

      expect(Array.isArray(results)).toBe(true);
      expect(results.length).toBe(2);
      results.forEach(entry => {
        expect(entry.metadata.agentType).toBe('research-agent');
      });
    });

    test('should search by taskType and return matching entries', async () => {
      const results = await storage.search({ taskType: 'code-generation' });

      expect(Array.isArray(results)).toBe(true);
      expect(results.length).toBe(1);
      expect(results[0].metadata.taskType).toBe('code-generation');
    });

    test('should search by tags (array match) and return matching entries', async () => {
      const results = await storage.search({ tags: ['research'] });

      expect(Array.isArray(results)).toBe(true);
      expect(results.length).toBe(2);
      results.forEach(entry => {
        expect(entry.metadata.tags).toContain('research');
      });
    });

    test('should return all entries when search criteria is empty', async () => {
      const results = await storage.search({});

      expect(Array.isArray(results)).toBe(true);
      expect(results.length).toBe(3);
    });

    test('should return empty array when no entries match search criteria', async () => {
      const results = await storage.search({ agentType: 'nonexistent-agent' });

      expect(Array.isArray(results)).toBe(true);
      expect(results.length).toBe(0);
    });
  });

  /**
   * Suite 4: Invalidation (4 assertions)
   */
  describe('Suite 4: Invalidation', () => {
    test('should invalidate single entry by ID and remove it', async () => {
      const entry = {
        prompt: 'To be deleted',
        output: 'Delete me',
        metadata: { agentType: 'test', taskType: 'test', tags: [], timestamp: Date.now(), ttl: 3600000 }
      };

      const { entryId } = await storage.store(entry);
      let retrieved = await storage.retrieve(entryId);
      expect(retrieved).not.toBeNull();

      const invalidateResult = await storage.invalidate(entryId);
      expect(invalidateResult.count).toBe(1);

      retrieved = await storage.retrieve(entryId);
      expect(retrieved).toBeNull();
    });

    test('should invalidate entries by sessionId and return count', async () => {
      const sessionId = 'session-xyz-123';
      const entry1 = {
        prompt: 'Entry 1',
        output: 'Output 1',
        metadata: {
          agentType: 'agent-a',
          taskType: 'task-1',
          tags: [],
          timestamp: Date.now(),
          ttl: 3600000,
          sessionId
        }
      };
      const entry2 = {
        prompt: 'Entry 2',
        output: 'Output 2',
        metadata: {
          agentType: 'agent-b',
          taskType: 'task-2',
          tags: [],
          timestamp: Date.now(),
          ttl: 3600000,
          sessionId
        }
      };

      const res1 = await storage.store(entry1);
      const res2 = await storage.store(entry2);

      const invalidateResult = await storage.invalidate({ sessionId });
      expect(invalidateResult.count).toBe(2);

      const retrieved1 = await storage.retrieve(res1.entryId);
      const retrieved2 = await storage.retrieve(res2.entryId);
      expect(retrieved1).toBeNull();
      expect(retrieved2).toBeNull();
    });

    test('should return count=0 when invalidating non-existent entry', async () => {
      const invalidateResult = await storage.invalidate('nonexistent-entry-id');

      expect(invalidateResult.count).toBe(0);
    });

    test('should invalidate by criteria object and return count', async () => {
      const entry1 = {
        prompt: 'Research entry',
        output: 'Output 1',
        metadata: { agentType: 'research-agent', taskType: 'search', tags: [], timestamp: Date.now(), ttl: 3600000 }
      };
      const entry2 = {
        prompt: 'Code entry',
        output: 'Output 2',
        metadata: { agentType: 'code-agent', taskType: 'generation', tags: [], timestamp: Date.now(), ttl: 3600000 }
      };

      const res1 = await storage.store(entry1);
      const res2 = await storage.store(entry2);

      const invalidateResult = await storage.invalidate({ agentType: 'research-agent' });
      expect(invalidateResult.count).toBe(1);

      const retrieved1 = await storage.retrieve(res1.entryId);
      const retrieved2 = await storage.retrieve(res2.entryId);
      expect(retrieved1).toBeNull();
      expect(retrieved2).not.toBeNull();
    });
  });

  /**
   * Suite 5: Metrics Recording (4 assertions)
   */
  describe('Suite 5: Metrics Recording', () => {
    test('should record hit event successfully', async () => {
      const event = {
        timestamp: Date.now(),
        type: 'hit',
        agentType: 'research-agent',
        taskType: 'web-search',
        tokensUsed: 150,
        relevanceScore: 0.92,
        cacheKey: 'cache-key-123'
      };

      const result = await storage.recordMetrics(event);
      expect(result.success).toBe(true);
    });

    test('should record miss event successfully', async () => {
      const event = {
        timestamp: Date.now(),
        type: 'miss',
        agentType: 'code-gen-agent',
        taskType: 'code-generation',
        tokensUsed: 200,
        relevanceScore: 0.0,
        cacheKey: 'cache-key-456'
      };

      const result = await storage.recordMetrics(event);
      expect(result.success).toBe(true);
    });

    test('should record store, evict, and invalidate events', async () => {
      const storeEvent = {
        timestamp: Date.now(),
        type: 'store',
        agentType: 'test-agent',
        taskType: 'test-task',
        tokensUsed: 100,
        relevanceScore: 1.0,
        cacheKey: 'key-1'
      };

      const evictEvent = {
        timestamp: Date.now(),
        type: 'evict',
        agentType: 'test-agent',
        taskType: 'test-task',
        tokensUsed: 50,
        relevanceScore: 0.5,
        cacheKey: 'key-2'
      };

      const invalidateEvent = {
        timestamp: Date.now(),
        type: 'invalidate',
        agentType: 'test-agent',
        taskType: 'test-task',
        tokensUsed: 0,
        relevanceScore: 0.0,
        cacheKey: 'key-3'
      };

      const storeResult = await storage.recordMetrics(storeEvent);
      const evictResult = await storage.recordMetrics(evictEvent);
      const invalidateResult = await storage.recordMetrics(invalidateEvent);

      expect(storeResult.success).toBe(true);
      expect(evictResult.success).toBe(true);
      expect(invalidateResult.success).toBe(true);
    });

    test('should not overwrite previous events when recording new metrics', async () => {
      const event1 = {
        timestamp: Date.now(),
        type: 'hit',
        agentType: 'agent-a',
        taskType: 'task-1',
        tokensUsed: 100,
        relevanceScore: 0.9,
        cacheKey: 'key-1'
      };

      const event2 = {
        timestamp: Date.now(),
        type: 'miss',
        agentType: 'agent-b',
        taskType: 'task-2',
        tokensUsed: 200,
        relevanceScore: 0.0,
        cacheKey: 'key-2'
      };

      await storage.recordMetrics(event1);
      await storage.recordMetrics(event2);

      const stats = await storage.stats();
      // Both events should be counted
      expect(stats.totalHits).toBeGreaterThan(0);
      expect(stats.totalMisses).toBeGreaterThan(0);
    });
  });

  /**
   * Suite 6: Stats Aggregation (5 assertions)
   */
  describe('Suite 6: Stats Aggregation', () => {
    test('should return stats object with all required fields', async () => {
      const stats = await storage.stats();

      expect(typeof stats).toBe('object');
      expect(stats).toHaveProperty('totalEntries');
      expect(stats).toHaveProperty('totalHits');
      expect(stats).toHaveProperty('totalMisses');
      expect(stats).toHaveProperty('avgTokensSaved');
    });

    test('should count hit events in totalHits', async () => {
      await storage.recordMetrics({
        timestamp: Date.now(),
        type: 'hit',
        agentType: 'test-agent',
        taskType: 'test-task',
        tokensUsed: 100,
        relevanceScore: 0.95,
        cacheKey: 'key-1'
      });

      await storage.recordMetrics({
        timestamp: Date.now(),
        type: 'hit',
        agentType: 'test-agent',
        taskType: 'test-task',
        tokensUsed: 150,
        relevanceScore: 0.90,
        cacheKey: 'key-2'
      });

      const stats = await storage.stats();
      expect(stats.totalHits).toBe(2);
    });

    test('should calculate avgTokensSaved from recorded metrics', async () => {
      await storage.recordMetrics({
        timestamp: Date.now(),
        type: 'hit',
        agentType: 'test-agent',
        taskType: 'test-task',
        tokensUsed: 1000,
        relevanceScore: 0.95,
        cacheKey: 'key-1'
      });

      await storage.recordMetrics({
        timestamp: Date.now(),
        type: 'hit',
        agentType: 'test-agent',
        taskType: 'test-task',
        tokensUsed: 2000,
        relevanceScore: 0.90,
        cacheKey: 'key-2'
      });

      const stats = await storage.stats();
      // Average of 1000 and 2000 = 1500
      expect(stats.avgTokensSaved).toBe(1500);
    });

    test('should update stats after new events are recorded', async () => {
      let stats = await storage.stats();
      const initialHits = stats.totalHits || 0;

      await storage.recordMetrics({
        timestamp: Date.now(),
        type: 'hit',
        agentType: 'test-agent',
        taskType: 'test-task',
        tokensUsed: 500,
        relevanceScore: 0.92,
        cacheKey: 'key-new'
      });

      stats = await storage.stats();
      expect(stats.totalHits).toBe(initialHits + 1);
    });

    test('should return zero/default values when no events recorded', async () => {
      const storage2 = new PersistentCacheStorage({ backendType: 'memory' });
      await storage2.initialize();
      const stats = await storage2.stats();

      expect(stats.totalHits).toBe(0);
      expect(stats.totalMisses).toBe(0);
      expect(stats.avgTokensSaved).toBe(0);
      expect(stats.totalEntries).toBe(0);
    });
  });

  /**
   * Suite 7: Configuration (3 assertions)
   */
  describe('Suite 7: Configuration', () => {
    test('should accept configuration options without error', async () => {
      const config = {
        maxSize: 100 * 1024 * 1024,
        maxEntries: 5000,
        defaultTTL: 7 * 24 * 60 * 60 * 1000,
        evictionPolicy: 'LRU'
      };

      await expect(storage.configure(config)).resolves.not.toThrow();
    });

    test('should modify behavior based on configuration', async () => {
      const entry = {
        prompt: 'Test prompt',
        output: 'x'.repeat(100 * 1024 * 1024),
        metadata: { agentType: 'test', taskType: 'test', tags: [], timestamp: Date.now(), ttl: 3600000 }
      };

      await storage.configure({ maxSize: 50 * 1024 * 1024 });

      // Store attempt should consider the new size limit
      const result = await storage.store(entry);
      expect(result.success).toBeDefined();
      expect(typeof result.success).toBe('boolean');
    });

    test('should allow configure() to be called multiple times', async () => {
      const config1 = { maxEntries: 1000 };
      const config2 = { maxEntries: 2000 };
      const config3 = { defaultTTL: 24 * 60 * 60 * 1000 };

      await expect(storage.configure(config1)).resolves.not.toThrow();
      await expect(storage.configure(config2)).resolves.not.toThrow();
      await expect(storage.configure(config3)).resolves.not.toThrow();
    });
  });

  /**
   * Suite 8: Edge Cases (4 assertions)
   */
  describe('Suite 8: Edge Cases', () => {
    test('should handle empty or null metadata fields gracefully', async () => {
      const entry = {
        prompt: 'Test',
        output: 'Output',
        metadata: {
          agentType: '',
          taskType: null,
          tags: [],
          timestamp: Date.now(),
          ttl: 3600000
        }
      };

      const result = await storage.store(entry);
      expect(result.success).toBe(true);

      const retrieved = await storage.retrieve(result.entryId);
      expect(retrieved).not.toBeNull();
      expect(retrieved.metadata.agentType).toBe('');
      expect(retrieved.metadata.taskType).toBeNull();
    });

    test('should store and retrieve very large entries (megabytes)', async () => {
      const largeOutput = JSON.stringify({
        data: 'x'.repeat(10 * 1024 * 1024) // 10 MB string
      });

      const entry = {
        prompt: 'Large query',
        output: largeOutput,
        metadata: { agentType: 'test', taskType: 'test', tags: [], timestamp: Date.now(), ttl: 3600000 }
      };

      const storeResult = await storage.store(entry);
      expect(storeResult.success).toBe(true);

      const retrieved = await storage.retrieve(storeResult.entryId);
      expect(retrieved).not.toBeNull();
      expect(retrieved.output).toBe(largeOutput);
      expect(retrieved.output.length).toBe(largeOutput.length);
    });

    test('should preserve special characters in strings', async () => {
      const entry = {
        prompt: 'Special chars: \n\t\r  "\'<>&',
        output: JSON.stringify({ emoji: '😀🎉🚀', chinese: '你好', arabic: 'مرحبا' }),
        metadata: {
          agentType: 'test',
          taskType: 'test',
          tags: ['🏷️', '特殊'],
          timestamp: Date.now(),
          ttl: 3600000
        }
      };

      const storeResult = await storage.store(entry);
      const retrieved = await storage.retrieve(storeResult.entryId);

      expect(retrieved.prompt).toBe(entry.prompt);
      expect(retrieved.output).toBe(entry.output);
      expect(retrieved.metadata.tags).toEqual(entry.metadata.tags);
    });

    test('should handle concurrent store calls without data corruption', async () => {
      const entries = Array.from({ length: 10 }, (_, i) => ({
        prompt: `Prompt ${i}`,
        output: `Output ${i}`,
        metadata: { agentType: `agent-${i}`, taskType: `task-${i}`, tags: [], timestamp: Date.now(), ttl: 3600000 }
      }));

      const storePromises = entries.map(entry => storage.store(entry));
      const results = await Promise.all(storePromises);

      expect(results).toHaveLength(10);
      results.forEach((result, idx) => {
        expect(result.success).toBe(true);
        expect(result.entryId).toBeTruthy();
      });

      const retrievePromises = results.map(r => storage.retrieve(r.entryId));
      const retrieved = await Promise.all(retrievePromises);

      retrieved.forEach((entry, idx) => {
        expect(entry).not.toBeNull();
        expect(entry.prompt).toBe(`Prompt ${idx}`);
      });
    });
  });

  /**
   * Suite 9: In-Memory Backend Specifics (3 assertions)
   */
  describe('Suite 9: In-Memory Backend Specifics', () => {
    test('should work with backendType=memory without requiring SQLite', async () => {
      const memoryStorage = new PersistentCacheStorage({ backendType: 'memory' });
      await memoryStorage.initialize();

      const entry = {
        prompt: 'Test',
        output: 'Output',
        metadata: { agentType: 'test', taskType: 'test', tags: [], timestamp: Date.now(), ttl: 3600000 }
      };

      const result = await memoryStorage.store(entry);
      expect(result.success).toBe(true);

      const retrieved = await memoryStorage.retrieve(result.entryId);
      expect(retrieved).not.toBeNull();
    });

    test('should persist data within process lifetime', async () => {
      const entry = {
        prompt: 'Persistent data',
        output: 'Stays in memory',
        metadata: { agentType: 'test', taskType: 'test', tags: [], timestamp: Date.now(), ttl: 3600000 }
      };

      const storeResult = await storage.store(entry);

      // Multiple retrieve calls should return same data
      const retrieved1 = await storage.retrieve(storeResult.entryId);
      const retrieved2 = await storage.retrieve(storeResult.entryId);
      const retrieved3 = await storage.retrieve(storeResult.entryId);

      expect(retrieved1).not.toBeNull();
      expect(retrieved2).not.toBeNull();
      expect(retrieved3).not.toBeNull();
      expect(retrieved1.prompt).toBe(retrieved2.prompt);
      expect(retrieved2.prompt).toBe(retrieved3.prompt);
    });

    test('should clear data on new PersistentCacheStorage instance', async () => {
      const entry = {
        prompt: 'Test entry',
        output: 'Test output',
        metadata: { agentType: 'test', taskType: 'test', tags: [], timestamp: Date.now(), ttl: 3600000 }
      };

      const storeResult = await storage.store(entry);
      let retrieved = await storage.retrieve(storeResult.entryId);
      expect(retrieved).not.toBeNull();

      // Create new instance
      const storage2 = new PersistentCacheStorage({ backendType: 'memory' });
      await storage2.initialize();
      retrieved = await storage2.retrieve(storeResult.entryId);

      // Data should not be available in new instance
      expect(retrieved).toBeNull();
    });
  });
});
