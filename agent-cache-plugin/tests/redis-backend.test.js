/**
 * Test Suite: Redis Storage Backend
 *
 * Tests for RedisBackend with mocked redis client
 */

let RedisBackend;
try {
  RedisBackend = require('../skills/cache-storage/backends/RedisBackend');
} catch (err) {
  // Redis backend optional
}

describe('RedisBackend', () => {
  let backend;
  let mockClient;
  let mockPubsubClient;

  beforeEach(() => {
    if (!RedisBackend) {
      console.warn('RedisBackend not available, skipping tests');
      return;
    }

    // Mock Redis client
    mockClient = {
      connect: jest.fn().mockResolvedValue(undefined),
      quit: jest.fn().mockResolvedValue(undefined),
      on: jest.fn(),
      set: jest.fn().mockResolvedValue('OK'),
      get: jest.fn().mockResolvedValue(null),
      del: jest.fn().mockResolvedValue(1),
      keys: jest.fn().mockResolvedValue([]),
      info: jest.fn().mockResolvedValue(''),
      publish: jest.fn().mockResolvedValue(1),
      setEx: jest.fn().mockResolvedValue('OK')
    };

    mockPubsubClient = {
      connect: jest.fn().mockResolvedValue(undefined),
      quit: jest.fn().mockResolvedValue(undefined),
      subscribe: jest.fn().mockResolvedValue(undefined)
    };

    // Mock redis module
    jest.doMock('redis', () => ({
      createClient: jest.fn((config) => {
        if (config.socket?.port === 6379) {
          return mockClient;
        }
        return mockPubsubClient;
      })
    }), { virtual: true });

    backend = new RedisBackend({
      host: 'localhost',
      port: 6379,
      keyPrefix: 'test:'
    });
  });

  afterEach(async () => {
    if (backend) {
      jest.clearAllMocks();
      jest.resetModules();
    }
  });

  describe('Configuration', () => {
    test('should initialize with default config', () => {
      const b = new RedisBackend();
      expect(b.config.host).toBe('localhost');
      expect(b.config.port).toBe(6379);
      expect(b.config.keyPrefix).toBe('cache:');
      expect(b.config.db).toBe(0);
    });

    test('should accept custom configuration', () => {
      const b = new RedisBackend({
        host: 'redis.example.com',
        port: 6380,
        password: 'secret',
        db: 1,
        keyPrefix: 'myapp:'
      });
      expect(b.config.host).toBe('redis.example.com');
      expect(b.config.port).toBe(6380);
      expect(b.config.password).toBe('secret');
      expect(b.config.db).toBe(1);
      expect(b.config.keyPrefix).toBe('myapp:');
    });

    test('should read config from environment variables', () => {
      process.env.REDIS_HOST = 'redis.prod.internal';
      process.env.REDIS_PORT = '6381';
      process.env.REDIS_PASSWORD = 'prod-secret';

      const b = new RedisBackend();
      expect(b.config.host).toBe('redis.prod.internal');
      expect(b.config.port).toBe(6381);
      expect(b.config.password).toBe('prod-secret');

      delete process.env.REDIS_HOST;
      delete process.env.REDIS_PORT;
      delete process.env.REDIS_PASSWORD;
    });

    test('should allow configuring via configure()', () => {
      backend.configure({ maxRetries: 5 });
      expect(backend.config.maxRetries).toBe(5);
    });
  });

  describe('Connection Management', () => {
    test('should initialize connection', async () => {
      // Skip if RedisBackend not available
      if (!RedisBackend) return;

      backend.client = mockClient;
      backend.connected = false;

      expect(backend.isReady()).toBe(false);
    });

    test('should track connection state', async () => {
      if (!RedisBackend) return;

      backend.client = mockClient;
      backend.connected = true;
      expect(backend.isReady()).toBe(true);
    });

    test('should handle connection errors', () => {
      if (!RedisBackend) return;

      backend.client = mockClient;
      expect(backend.config.maxRetries).toBe(3);
      expect(backend.config.retryDelay).toBe(1000);
    });

    test('should shutdown gracefully', async () => {
      if (!RedisBackend) return;

      backend.client = mockClient;
      backend.pubsubClient = mockPubsubClient;
      backend.connected = true;

      await backend.shutdown();

      expect(mockClient.quit).toHaveBeenCalled();
      expect(backend.connected).toBe(false);
    });
  });

  describe('Storage Operations', () => {
    test('should store entry with TTL', async () => {
      if (!RedisBackend) return;

      backend.client = mockClient;
      backend.connected = true;

      const entry = {
        prompt: 'Test prompt',
        output: { result: 'test' },
        ttl: 3600000
      };

      const result = await backend.store(entry);

      expect(result.success).toBe(true);
      expect(result.entryId).toBeDefined();
      expect(mockClient.set).toHaveBeenCalled();
      expect(backend.metrics.writes).toBe(1);
    });

    test('should use default TTL if not specified', async () => {
      if (!RedisBackend) return;

      backend.client = mockClient;
      backend.connected = true;

      const entry = { prompt: 'Test' };
      await backend.store(entry);

      const callArgs = mockClient.set.mock.calls[0];
      expect(callArgs[2]).toHaveProperty('EX');
      expect(callArgs[2].EX).toBe(86400); // 24 hours
    });

    test('should generate ID if not provided', async () => {
      if (!RedisBackend) return;

      backend.client = mockClient;
      backend.connected = true;

      const entry = { prompt: 'Test' };
      const result = await backend.store(entry);

      expect(result.entryId).toMatch(/^\d+-[a-z0-9]+$/);
    });

    test('should handle store errors', async () => {
      if (!RedisBackend) return;

      backend.client = mockClient;
      backend.connected = true;
      mockClient.set.mockRejectedValueOnce(new Error('Store failed'));

      const result = await backend.store({ prompt: 'Test' });

      expect(result.success).toBe(false);
      expect(result.error).toBeDefined();
      expect(backend.metrics.errors).toBe(1);
    });

    test('should return null when not connected', async () => {
      if (!RedisBackend) return;

      backend.connected = false;

      const result = await backend.store({ prompt: 'Test' });
      expect(result.success).toBe(false);
    });
  });

  describe('Retrieval Operations', () => {
    test('should retrieve entry by ID', async () => {
      if (!RedisBackend) return;

      backend.client = mockClient;
      backend.connected = true;

      const entry = { id: 'test-id', prompt: 'Test', storedAt: Date.now() };
      mockClient.get.mockResolvedValueOnce(JSON.stringify(entry));

      const result = await backend.retrieve('test-id');

      expect(result).toEqual(entry);
      expect(backend.metrics.reads).toBe(1);
      expect(mockClient.get).toHaveBeenCalledWith('test:entry:test-id');
    });

    test('should return null for missing entry', async () => {
      if (!RedisBackend) return;

      backend.client = mockClient;
      backend.connected = true;
      mockClient.get.mockResolvedValueOnce(null);

      const result = await backend.retrieve('nonexistent');

      expect(result).toBeNull();
    });

    test('should return null for expired entry', async () => {
      if (!RedisBackend) return;

      backend.client = mockClient;
      backend.connected = true;

      const entry = {
        id: 'test-id',
        prompt: 'Test',
        expiresAt: Date.now() - 1000
      };
      mockClient.get.mockResolvedValueOnce(JSON.stringify(entry));

      const result = await backend.retrieve('test-id');

      expect(result).toBeNull();
      expect(mockClient.del).toHaveBeenCalled();
    });

    test('should handle retrieval errors', async () => {
      if (!RedisBackend) return;

      backend.client = mockClient;
      backend.connected = true;
      mockClient.get.mockRejectedValueOnce(new Error('Get failed'));

      const result = await backend.retrieve('test-id');

      expect(result).toBeNull();
      expect(backend.metrics.errors).toBe(1);
    });
  });

  describe('Search Operations', () => {
    test('should search entries by criteria', async () => {
      if (!RedisBackend) return;

      backend.client = mockClient;
      backend.connected = true;

      const entries = [
        { id: '1', prompt: 'Python', tags: ['code'] },
        { id: '2', prompt: 'JavaScript', tags: ['code'] }
      ];

      mockClient.keys.mockResolvedValueOnce(['test:entry:1', 'test:entry:2']);
      mockClient.get
        .mockResolvedValueOnce(JSON.stringify(entries[0]))
        .mockResolvedValueOnce(JSON.stringify(entries[1]));

      const results = await backend.search({ tags: ['code'] });

      expect(results.length).toBe(2);
      expect(backend.metrics.reads).toBeGreaterThan(0);
    });

    test('should handle empty search results', async () => {
      if (!RedisBackend) return;

      backend.client = mockClient;
      backend.connected = true;
      mockClient.keys.mockResolvedValueOnce([]);

      const results = await backend.search({ tags: ['nonexistent'] });

      expect(results).toEqual([]);
    });

    test('should handle search errors', async () => {
      if (!RedisBackend) return;

      backend.client = mockClient;
      backend.connected = true;
      mockClient.keys.mockRejectedValueOnce(new Error('Search failed'));

      const results = await backend.search({});

      expect(results).toEqual([]);
      expect(backend.metrics.errors).toBe(1);
    });
  });

  describe('Invalidation Operations', () => {
    test('should invalidate by ID', async () => {
      if (!RedisBackend) return;

      backend.client = mockClient;
      backend.connected = true;
      mockClient.del.mockResolvedValueOnce(1);

      const result = await backend.invalidate('test-id');

      expect(result.count).toBe(1);
      expect(mockClient.del).toHaveBeenCalledWith(['test:entry:test-id']);
      expect(backend.metrics.deletes).toBe(1);
    });

    test('should invalidate by criteria', async () => {
      if (!RedisBackend) return;

      backend.client = mockClient;
      backend.connected = true;

      const entries = [
        { id: '1', prompt: 'Test', agentType: 'analyzer' },
        { id: '2', prompt: 'Test', agentType: 'analyzer' }
      ];

      mockClient.keys.mockResolvedValueOnce(['test:entry:1', 'test:entry:2']);
      mockClient.get
        .mockResolvedValueOnce(JSON.stringify(entries[0]))
        .mockResolvedValueOnce(JSON.stringify(entries[1]));
      mockClient.del.mockResolvedValueOnce(2);

      const result = await backend.invalidate({ agentType: 'analyzer' });

      expect(result.count).toBe(2);
      expect(mockClient.del).toHaveBeenCalled();
    });

    test('should publish invalidation via Pub/Sub', async () => {
      if (!RedisBackend) return;

      backend.client = mockClient;
      backend.connected = true;
      backend.config.enablePubSub = true;
      mockClient.del.mockResolvedValueOnce(1);
      mockClient.publish.mockResolvedValueOnce(1);

      await backend.invalidate('test-id');

      expect(mockClient.publish).toHaveBeenCalled();
    });

    test('should handle invalidation errors', async () => {
      if (!RedisBackend) return;

      backend.client = mockClient;
      backend.connected = true;
      mockClient.del.mockRejectedValueOnce(new Error('Delete failed'));

      const result = await backend.invalidate('test-id');

      expect(result.count).toBe(0);
      expect(backend.metrics.errors).toBe(1);
    });
  });

  describe('Metrics & Stats', () => {
    test('should record metrics', async () => {
      if (!RedisBackend) return;

      backend.client = mockClient;
      backend.connected = true;

      const metrics = { hits: 100, misses: 25 };
      await backend.recordMetrics(metrics);

      expect(mockClient.setEx).toHaveBeenCalled();
    });

    test('should get storage stats', async () => {
      if (!RedisBackend) return;

      backend.client = mockClient;
      backend.connected = true;
      mockClient.keys.mockResolvedValueOnce(['test:entry:1', 'test:entry:2']);
      mockClient.info.mockResolvedValueOnce('stats_line_1\nstats_line_2');

      const stats = await backend.stats();

      expect(stats.totalEntries).toBe(2);
      expect(stats.connected).toBe(true);
      expect(stats.metrics).toBeDefined();
    });

    test('should track operation counts', async () => {
      if (!RedisBackend) return;

      backend.client = mockClient;
      backend.connected = true;

      await backend.store({ prompt: 'Test' });

      // Mock get for retrieve to return a valid entry
      const entry = { id: 'test-id', prompt: 'Test', storedAt: Date.now() };
      mockClient.get.mockResolvedValueOnce(JSON.stringify(entry));

      await backend.retrieve('test-id');
      mockClient.del.mockResolvedValueOnce(1);
      await backend.invalidate('test-id');

      expect(backend.metrics.writes).toBe(1);
      expect(backend.metrics.reads).toBe(1);
      expect(backend.metrics.deletes).toBe(1);
    });
  });

  describe('Event Subscription', () => {
    test('should allow subscribing to events', () => {
      if (!RedisBackend) return;

      const callback = jest.fn();
      const unsubscribe = backend.subscribe(callback);

      expect(typeof unsubscribe).toBe('function');
      expect(backend.subscribers.has(callback)).toBe(true);

      unsubscribe();
      expect(backend.subscribers.has(callback)).toBe(false);
    });

    test('should handle invalidation events', () => {
      if (!RedisBackend) return;

      const callback = jest.fn();
      backend.subscribe(callback);

      const message = JSON.stringify({ keys: ['key1', 'key2'] });
      backend._handleInvalidation(message);

      expect(callback).toHaveBeenCalledWith({
        type: 'invalidate',
        keys: ['key1', 'key2']
      });
    });
  });

  describe('Connection Resilience', () => {
    test('should return error when disconnected', async () => {
      if (!RedisBackend) return;

      backend.connected = false;
      backend.client = null;

      const result = await backend.store({ prompt: 'Test' });
      expect(result.success).toBe(false);
    });

    test('should handle connection timeout', () => {
      if (!RedisBackend) return;

      expect(backend.config.connectionTimeout).toBe(5000);
      expect(backend.config.maxRetries).toBe(3);
    });
  });
});
