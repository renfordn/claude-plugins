/**
 * Test Suite: Storage Backends
 *
 * Tests for different storage backend implementations
 * (memory, SQLite, etc.) to ensure they implement the StorageBackend interface correctly.
 */

const path = require('path');
const fs = require('fs');
const MemoryBackend = require('../skills/cache-storage/backends/MemoryBackend');
const SQLiteBackend = require('../skills/cache-storage/backends/SQLiteBackend');
const { createBackend, listBackends } = require('../skills/cache-storage/backends');

// Test utilities
const testDbPath = path.join(__dirname, 'test-cache.db');
const cleanupDb = () => {
  if (fs.existsSync(testDbPath)) {
    fs.unlinkSync(testDbPath);
  }
};

const testEntry = {
  prompt: 'Test prompt',
  output: JSON.stringify({ result: 'test' }),
  metadata: {
    agentType: 'test-agent',
    taskType: 'test-task',
    tags: ['test'],
    timestamp: Date.now(),
    ttl: 24 * 60 * 60 * 1000
  }
};

// Shared test suite for any backend
async function runBackendTests(BackendClass, config = {}) {
  let backend;

  beforeEach(async () => {
    backend = new BackendClass(config);
    await backend.initialize(config);
  });

  afterEach(async () => {
    await backend.shutdown();
  });

  test('should store and retrieve entry', async () => {
    const result = await backend.store(testEntry);
    expect(result.success).toBe(true);
    expect(result.entryId).toBeTruthy();

    const retrieved = await backend.retrieve(result.entryId);
    expect(retrieved).not.toBeNull();
    expect(retrieved.prompt).toBe(testEntry.prompt);
    expect(retrieved.output).toBe(testEntry.output);
  });

  test('should return null for non-existent entry', async () => {
    const retrieved = await backend.retrieve('non-existent-id');
    expect(retrieved).toBeNull();
  });

  test('should invalidate by ID', async () => {
    const stored = await backend.store(testEntry);
    const invalidated = await backend.invalidate(stored.entryId);
    expect(invalidated.count).toBe(1);

    const retrieved = await backend.retrieve(stored.entryId);
    expect(retrieved).toBeNull();
  });

  test('should search entries by criteria', async () => {
    const entry1 = { ...testEntry, metadata: { ...testEntry.metadata, agentType: 'agent-a' } };
    const entry2 = { ...testEntry, metadata: { ...testEntry.metadata, agentType: 'agent-b' } };

    await backend.store(entry1);
    await backend.store(entry2);

    const results = await backend.search({ agentType: 'agent-a' });
    expect(results.length).toBeGreaterThan(0);
    expect(results.some(e => e.metadata.agentType === 'agent-a')).toBe(true);
  });

  test('should record metrics', async () => {
    const event = {
      type: 'hit',
      tokensUsed: 100
    };

    const result = await backend.recordMetrics(event);
    expect(result.success).toBe(true);
  });

  test('should return stats', async () => {
    await backend.store(testEntry);
    await backend.recordMetrics({ type: 'hit', tokensUsed: 100 });

    const stats = await backend.stats();
    expect(stats.totalEntries).toBeGreaterThan(0);
    expect(typeof stats.totalHits).toBe('number');
    expect(typeof stats.totalMisses).toBe('number');
    expect(typeof stats.avgTokensSaved).toBe('number');
  });

  test('should support configuration', async () => {
    const newConfig = { maxSize: 1000 };
    await backend.configure(newConfig);
    expect(backend.config.maxSize).toBe(1000);
  });

  test('should track access on retrieve', async () => {
    const stored = await backend.store(testEntry);
    const retrieved1 = await backend.retrieve(stored.entryId);
    expect(retrieved1.accessCount).toBe(1);

    const retrieved2 = await backend.retrieve(stored.entryId);
    expect(retrieved2.accessCount).toBe(2);
  });

  test('should handle expired entries', async () => {
    const expiredEntry = {
      ...testEntry,
      metadata: {
        ...testEntry.metadata,
        timestamp: Date.now() - (48 * 60 * 60 * 1000),
        ttl: 24 * 60 * 60 * 1000
      }
    };

    const stored = await backend.store(expiredEntry);
    const retrieved = await backend.retrieve(stored.entryId);
    expect(retrieved).toBeNull();
  });
}

// Test Memory Backend
describe('MemoryBackend', () => {
  runBackendTests(MemoryBackend);

  test('should lose data on shutdown', async () => {
    const backend = new MemoryBackend();
    await backend.initialize({});

    const stored = await backend.store(testEntry);
    await backend.shutdown();

    expect(await backend.isReady()).toBe(false);
  });
});

// Test SQLite Backend
describe('SQLiteBackend', () => {
  afterEach(cleanupDb);

  runBackendTests(SQLiteBackend, { dbPath: testDbPath });

  test('should persist data across instances', async () => {
    const backend1 = new SQLiteBackend({ dbPath: testDbPath });
    await backend1.initialize({ dbPath: testDbPath });

    const stored = await backend1.store(testEntry);
    const entryId = stored.entryId;
    await backend1.shutdown();

    const backend2 = new SQLiteBackend({ dbPath: testDbPath });
    await backend2.initialize({ dbPath: testDbPath });

    const retrieved = await backend2.retrieve(entryId);
    expect(retrieved).not.toBeNull();
    expect(retrieved.prompt).toBe(testEntry.prompt);

    await backend2.shutdown();
  });

  test('should create database directory if not exists', async () => {
    const nestedPath = path.join(__dirname, 'nested', 'dir', 'cache.db');
    const backend = new SQLiteBackend({ dbPath: nestedPath });

    expect(() => backend.initialize({ dbPath: nestedPath })).not.toThrow();

    await backend.shutdown();
    if (fs.existsSync(nestedPath)) {
      fs.unlinkSync(nestedPath);
    }
  });
});

// Test backend factory
describe('Backend Factory', () => {
  test('should list available backends', () => {
    const backends = listBackends();
    expect(backends).toContain('memory');
    expect(backends).toContain('sqlite');
  });

  test('should create memory backend', () => {
    const backend = createBackend('memory');
    expect(backend).toBeInstanceOf(MemoryBackend);
  });

  test('should create SQLite backend', () => {
    const backend = createBackend('sqlite', { dbPath: testDbPath });
    expect(backend).toBeInstanceOf(SQLiteBackend);
  });

  test('should throw error for unknown backend', () => {
    expect(() => createBackend('unknown')).toThrow();
  });

  afterEach(cleanupDb);
});
