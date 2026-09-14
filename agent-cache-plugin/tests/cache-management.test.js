/**
 * Test Suite: Cache Management Skill
 *
 * Tests the real CacheManager implementation from skills/cache-management
 * using the actual storage and retrieval logic (not mocks).
 */

const cacheManagement = require('../skills/cache-management');

describe('Cache Management Skill (Real Implementation)', () => {
  beforeEach(() => {
    // Reset singleton instance for test isolation
    cacheManagement.resetSingleton();
  });

  describe('store()', () => {
    test('should store cache entry with generated ID', async () => {
      const entry = {
        prompt: 'Test prompt',
        output: { result: 'Test output' },
        metadata: { agentType: 'test-agent', ttl: 24 * 60 * 60 * 1000 }
      };

      const result = await cacheManagement.store(entry);

      expect(result.success).toBe(true);
      expect(result.entryId).toBeTruthy();
      expect(typeof result.entryId).toBe('string');
    });

    test('should accept entry with custom ID', async () => {
      const customId = 'custom-test-id-' + Date.now();
      const entry = {
        id: customId,
        prompt: 'Test prompt',
        output: { result: 'Test output' },
        metadata: { agentType: 'test-agent', ttl: 24 * 60 * 60 * 1000 }
      };

      const result = await cacheManagement.store(entry);

      expect(result.success).toBe(true);
      expect(result.entryId).toBe(customId);
    });

    test('should accept entries with parameters', async () => {
      const entry = {
        prompt: 'Test prompt',
        output: { result: 'Test output' },
        metadata: {
          agentType: 'test-agent',
          ttl: 24 * 60 * 60 * 1000,
          parameters: {
            taskType: 'research',
            userId: 'user-123'
          }
        }
      };

      const result = await cacheManagement.store(entry);

      expect(result.success).toBe(true);
      expect(result.entryId).toBeTruthy();
    });
  });

  describe('retrieve()', () => {
    test('should retrieve stored entry', async () => {
      const entry = {
        prompt: 'Test prompt for retrieval',
        output: { result: 'Test output' },
        metadata: { agentType: 'test-agent', ttl: 24 * 60 * 60 * 1000 }
      };

      const storeResult = await cacheManagement.store(entry);
      const retrieveResult = await cacheManagement.retrieve(storeResult.entryId);

      expect(retrieveResult).toBeTruthy();
      expect(retrieveResult.found).toBe(true);
      expect(retrieveResult.entry).toBeTruthy();
      expect(retrieveResult.entry.prompt).toBe('Test prompt for retrieval');
    });

    test('should return found=false for missing entry', async () => {
      const result = await cacheManagement.retrieve('nonexistent-id-xyz');

      expect(result.found).toBe(false);
      expect(result.entry).toBeNull();
    });

    test('should return found=false for expired entry', async () => {
      const entry = {
        prompt: 'Short-lived entry',
        output: { result: 'Output' },
        metadata: { agentType: 'test-agent', ttl: 1 }
      };

      const storeResult = await cacheManagement.store(entry);

      // Wait for entry to expire
      await new Promise(r => setTimeout(r, 10));
      const result = await cacheManagement.retrieve(storeResult.entryId);

      expect(result.found).toBe(false);
      expect(result.entry).toBeNull();
    });
  });

  describe('search()', () => {
    test('should search by tag', async () => {
      await cacheManagement.store({
        prompt: 'First prompt',
        output: { result: 'output1' },
        metadata: { agentType: 'search-test-agent', ttl: 24 * 60 * 60 * 1000 }
      });

      // agentType is automatically added as a tag during store()
      const results = await cacheManagement.search({ tags: ['search-test-agent'] });

      expect(Array.isArray(results)).toBe(true);
      expect(results.length).toBeGreaterThanOrEqual(1);
    });

    test('should return empty array for no matches', async () => {
      const results = await cacheManagement.search({ tags: ['nonexistent-tag-xyz'] });

      expect(Array.isArray(results)).toBe(true);
      expect(results).toHaveLength(0);
    });
  });

  describe('invalidate()', () => {
    test('should invalidate entry by ID', async () => {
      const storeResult = await cacheManagement.store({
        prompt: 'To be invalidated',
        output: { result: 'output' },
        metadata: { agentType: 'test-agent', ttl: 24 * 60 * 60 * 1000 }
      });

      const result = await cacheManagement.invalidate(storeResult.entryId);

      expect(result.count).toBe(1);
    });

    test('should return count=0 for nonexistent ID', async () => {
      const result = await cacheManagement.invalidate('nonexistent-id-xyz');

      expect(result.count).toBe(0);
    });
  });

  describe('stats()', () => {
    test('should return cache statistics', async () => {
      const stats = await cacheManagement.stats();

      expect(stats).toBeTruthy();
      expect(typeof stats.totalEntries).toBe('number');
      expect(typeof stats.totalHits).toBe('number');
      expect(typeof stats.totalMisses).toBe('number');
    });
  });

  describe('configure()', () => {
    test('should accept cache configuration', async () => {
      const config = {
        maxSize: 500 * 1024 * 1024,
        maxEntries: 50000
      };

      const result = await cacheManagement.configure(config);

      expect(result).toBeTruthy();
      expect(result.success).toBe(true);
    });
  });
});
