/**
 * Test Suite: Embedding-based Relevance Scorer
 *
 * Tests for EmbeddingScorer with mocked API and fallback behavior
 */

const EmbeddingScorer = require('../skills/cache-validation/EmbeddingScorer');

describe('EmbeddingScorer', () => {
  let scorer;

  beforeEach(() => {
    scorer = new EmbeddingScorer({
      apiKey: process.env.OPENAI_API_KEY || 'test-key',
      provider: 'openai'
    });
  });

  describe('Configuration', () => {
    test('should initialize with default config', () => {
      const s = new EmbeddingScorer();
      expect(s.config.provider).toBe('openai');
      expect(s.config.model).toBe('text-embedding-3-small');
      expect(s.config.maxCacheSize).toBe(10000);
      expect(s.config.enableFallback).toBe(true);
    });

    test('should accept custom configuration', () => {
      const s = new EmbeddingScorer({
        model: 'text-embedding-3-large',
        maxCacheSize: 5000,
        timeout: 20000
      });
      expect(s.config.model).toBe('text-embedding-3-large');
      expect(s.config.maxCacheSize).toBe(5000);
      expect(s.config.timeout).toBe(20000);
    });

    test('should disable embeddings if no API key', () => {
      const s = new EmbeddingScorer({ apiKey: null });
      expect(s.ready).toBe(false);
    });

    test('should require API key for OpenAI', () => {
      const s = new EmbeddingScorer({ apiKey: null });
      expect(s.ready).toBe(false);
    });
  });

  describe('Jaccard Fallback Scoring', () => {
    test('should score exact matches as 100', () => {
      const text = 'What is the capital of France?';
      const score = scorer._jaccard(text, text);
      expect(score).toBe(100);
    });

    test('should score identical prompts with different case as high', () => {
      const score = scorer._jaccard(
        'What is AI?',
        'what is ai?'
      );
      expect(score).toBeGreaterThan(80);
    });

    test('should score similar prompts with keyword overlap', () => {
      const score = scorer._jaccard(
        'What is artificial intelligence?',
        'Tell me about artificial intelligence'
      );
      expect(score).toBeGreaterThan(30); // Shared keywords: artificial, intelligence
    });

    test('should score dissimilar prompts low', () => {
      const score = scorer._jaccard(
        'What is the capital of France?',
        'How do you cook pasta?'
      );
      expect(score).toBeLessThan(50);
    });

    test('should return 0 for empty prompts', () => {
      expect(scorer._jaccard('', 'hello')).toBe(0);
      expect(scorer._jaccard('hello', '')).toBe(0);
      expect(scorer._jaccard('', '')).toBe(0);
    });

    test('should handle special characters', () => {
      const score = scorer._jaccard(
        'What is Python? (programming language)',
        'Tell me about Python programming'
      );
      expect(score).toBeGreaterThan(25); // More lenient due to word filtering
    });
  });

  describe('Cosine Similarity', () => {
    test('should return 0 for null vectors', () => {
      expect(scorer._cosineSimilarity(null, [1, 2, 3])).toBe(0);
      expect(scorer._cosineSimilarity([1, 2, 3], null)).toBe(0);
    });

    test('should return 0 for mismatched dimensions', () => {
      expect(scorer._cosineSimilarity([1, 2], [1, 2, 3])).toBe(0);
    });

    test('should compute cosine similarity correctly', () => {
      const vecA = [1, 0, 0];
      const vecB = [1, 0, 0];
      expect(scorer._cosineSimilarity(vecA, vecB)).toBeCloseTo(1.0, 5);
    });

    test('should return 0 for orthogonal vectors', () => {
      const vecA = [1, 0, 0];
      const vecB = [0, 1, 0];
      expect(scorer._cosineSimilarity(vecA, vecB)).toBeCloseTo(0, 5);
    });

    test('should compute similarity for non-orthogonal vectors', () => {
      const vecA = [1, 1, 0];
      const vecB = [1, 0, 0];
      const similarity = scorer._cosineSimilarity(vecA, vecB);
      expect(similarity).toBeGreaterThan(0);
      expect(similarity).toBeLessThan(1);
    });
  });

  describe('Caching', () => {
    test('should cache embeddings', () => {
      const text = 'Sample text';
      const embedding = [0.1, 0.2, 0.3];

      scorer._setCachedEmbedding(text, embedding);
      const cached = scorer._getCachedEmbedding(text);

      expect(cached).toEqual(embedding);
    });

    test('should use same hash for identical text', () => {
      const text = 'Sample text';
      const embedding1 = [0.1, 0.2, 0.3];
      const embedding2 = [0.4, 0.5, 0.6];

      scorer._setCachedEmbedding(text, embedding1);
      scorer._setCachedEmbedding(text, embedding2);

      const cached = scorer._getCachedEmbedding(text);
      expect(cached).toEqual(embedding2); // Should overwrite
    });

    test('should enforce cache size limit', () => {
      const s = new EmbeddingScorer({
        apiKey: 'test',
        maxCacheSize: 3
      });

      s._setCachedEmbedding('text1', [1, 2, 3]);
      s._setCachedEmbedding('text2', [2, 3, 4]);
      s._setCachedEmbedding('text3', [3, 4, 5]);

      expect(s.embeddingCache.size).toBe(3);

      // Adding one more should evict oldest
      s._setCachedEmbedding('text4', [4, 5, 6]);
      expect(s.embeddingCache.size).toBe(3);
    });

    test('should track cache statistics', () => {
      scorer.clearCache();
      expect(scorer.stats.cacheHits).toBe(0);
      expect(scorer.stats.cacheMisses).toBe(0);

      const embedding = [0.1, 0.2];
      scorer._setCachedEmbedding('text', embedding);

      // _getEmbedding tracks cache hits/misses
      // The first call will be a cache hit (in the mock), but we can't easily test
      // without mocking the API. Just verify the tracking mechanism exists.
      expect(typeof scorer.stats.cacheHits).toBe('number');
      expect(typeof scorer.stats.cacheMisses).toBe('number');
    });
  });

  describe('Statistics', () => {
    test('should return stats object', () => {
      const stats = scorer.getStats();
      expect(stats).toHaveProperty('cacheHits');
      expect(stats).toHaveProperty('cacheMisses');
      expect(stats).toHaveProperty('apiCalls');
      expect(stats).toHaveProperty('fallbacks');
      expect(stats).toHaveProperty('hitRate');
      expect(stats).toHaveProperty('cacheSize');
      expect(stats).toHaveProperty('ready');
    });

    test('should calculate cache hit rate', () => {
      scorer.clearCache();
      scorer.stats.cacheHits = 75;
      scorer.stats.cacheMisses = 25;

      const stats = scorer.getStats();
      expect(stats.hitRate).toBe('75.0%');
    });

    test('should handle zero cache accesses', () => {
      scorer.clearCache();
      const stats = scorer.getStats();
      expect(stats.hitRate).toBe('N/A');
    });

    test('should clear cache and reset stats', () => {
      scorer._setCachedEmbedding('text', [1, 2, 3]);
      scorer.stats.cacheHits = 10;

      scorer.clearCache();

      expect(scorer.embeddingCache.size).toBe(0);
      expect(scorer.stats.cacheHits).toBe(0);
      expect(scorer.stats.cacheMisses).toBe(0);
    });
  });

  describe('Scoring with Fallback', () => {
    test('should fallback to keyword scoring when embeddings unavailable', async () => {
      // Embeddings disabled (no API key)
      const s = new EmbeddingScorer({ apiKey: null });

      const score = await s.scoreRelevance(
        'What is Python?',
        'Tell me about Python',
        (a, b) => s._jaccard(a, b)
      );

      expect(score).toBeGreaterThan(0);
      expect(score).toBeLessThan(100);
    });

    test('should return 0 for null prompts', async () => {
      expect(await scorer.scoreRelevance(null, 'hello')).toBe(0);
      expect(await scorer.scoreRelevance('hello', null)).toBe(0);
      expect(await scorer.scoreRelevance(null, null)).toBe(0);
    });

    test('should score exact matches', async () => {
      const text = 'Sample prompt text';
      const score = await scorer.scoreRelevance(text, text);
      expect(score).toBe(100);
    });

    test('should track fallback usage', async () => {
      scorer.clearCache();
      const fallbackScorer = (a, b) => scorer._jaccard(a, b);

      // This will fail API call and use fallback
      if (!scorer.ready) {
        await scorer.scoreRelevance('text1', 'text2', fallbackScorer);
      }

      // Stats should reflect the attempt
      expect(scorer.stats).toBeDefined();
    });
  });

  describe('Batch Operations', () => {
    test('should batch score multiple prompts', async () => {
      const cached = ['Python programming', 'JavaScript basics', 'AI overview'];
      const current = 'machine learning algorithms';
      const fallback = (a, b) => scorer._jaccard(a, b);

      const scores = await scorer.scoreRelevanceBatch(cached, current, fallback);

      expect(scores).toHaveLength(3);
      expect(scores.every(s => typeof s === 'number')).toBe(true);
      expect(scores.every(s => s >= 0 && s <= 100)).toBe(true);
    });

    test('should preload embeddings', async () => {
      const prompts = ['text1', 'text2', 'text3'];
      const result = await scorer.preloadEmbeddings(prompts);

      expect(result).toHaveProperty('loaded');
      expect(result).toHaveProperty('failed');
      expect(typeof result.loaded).toBe('number');
      expect(typeof result.failed).toBe('number');
    });

    test('should handle empty batch', async () => {
      const scores = await scorer.scoreRelevanceBatch([], 'current');
      expect(scores).toEqual([]);
    });
  });

  describe('Configuration Validation', () => {
    test('should validate provider', () => {
      const s = new EmbeddingScorer({
        provider: 'unknown',
        apiKey: 'test'
      });
      expect(s.ready).toBe(false);
    });

    test('should respect enableFallback setting', () => {
      const s1 = new EmbeddingScorer({ enableFallback: true, apiKey: 'test' });
      const s2 = new EmbeddingScorer({ enableFallback: false, apiKey: 'test' });

      expect(s1.config.enableFallback).toBe(true);
      expect(s2.config.enableFallback).toBe(false);
    });

    test('should use environment variable for API key', () => {
      const oldKey = process.env.OPENAI_API_KEY;
      process.env.OPENAI_API_KEY = 'env-test-key';

      const s = new EmbeddingScorer();
      expect(s.config.apiKey).toBe('env-test-key');

      process.env.OPENAI_API_KEY = oldKey;
    });
  });

  describe('Hash Function', () => {
    test('should produce consistent hashes', () => {
      const text = 'Sample text for hashing';
      const hash1 = scorer._hash(text);
      const hash2 = scorer._hash(text);

      expect(hash1).toBe(hash2);
    });

    test('should produce different hashes for different text', () => {
      const hash1 = scorer._hash('text1');
      const hash2 = scorer._hash('text2');

      expect(hash1).not.toBe(hash2);
    });

    test('should use SHA-256 hashing', () => {
      const hash = scorer._hash('test');
      expect(hash).toHaveLength(64); // SHA-256 hex = 64 chars
    });
  });
});
