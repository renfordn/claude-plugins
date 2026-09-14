# Embedding-based Relevance Scoring

## Overview

The cache validation system now supports embedding-based semantic similarity for improved cache hit rates. Instead of relying solely on keyword overlap (Jaccard similarity), it can use semantic embeddings to understand meaning and context, handling synonyms, paraphrasing, and semantic variations.

**Expected Improvement**: Hit rates from 60-85% → 75-90%

## How It Works

### Two-Tier Scoring Strategy

1. **Semantic Scoring (Primary)**: Uses OpenAI embeddings to compute cosine similarity
   - Handles synonyms: "capital" ≈ "biggest city"
   - Understands paraphrasing: "What is AI?" ≈ "Tell me about artificial intelligence"
   - Semantic context: knows related concepts

2. **Keyword Fallback (Secondary)**: Uses Jaccard similarity
   - Fast, no API calls
   - Always available even without embeddings
   - Good for exact/similar matches

### Scoring Pipeline

```
Input: Cached prompt + Current prompt
  ↓
Check cache for embeddings (in-memory)
  ↓
  ├─ Hit: Use cached embedding vectors
  │
  └─ Miss: Call OpenAI API for embeddings
      ├─ Success: Cache result + score
      │
      └─ Failure: Fall back to keyword scoring
  ↓
Compute cosine similarity (0-1) → Scale to 0-100
```

## Configuration

### Enabling Embeddings

Set `OPENAI_API_KEY` environment variable:

```bash
export OPENAI_API_KEY="sk-..."
```

Or pass config to CacheValidator:

```javascript
const validator = new CacheValidator({
  useEmbeddings: true,
  embeddingModel: 'text-embedding-3-small',  // default
  enableFallbackScoring: true  // use keyword scoring if embeddings fail
});
```

### Embedding Models

Available OpenAI models:

| Model | Dimensions | Speed | Cost | Use Case |
|-------|-----------|-------|------|----------|
| `text-embedding-3-small` | 512 | Fast | Cheap | Default, good accuracy |
| `text-embedding-3-large` | 1536 | Medium | Expensive | High-precision matching |

## Usage Examples

### Basic Validation with Embeddings

```javascript
const { CacheValidator } = require('./skills/cache-validation');

const validator = new CacheValidator({
  useEmbeddings: true
});

const cachedEntry = {
  prompt: 'What is the capital of France?',
  output: { answer: 'Paris' },
  metadata: { /* ... */ }
};

const result = await validator.validate(cachedEntry, {
  task: 'Tell me about Paris, the largest city in France'
});

console.log(result.relevanceScore);  // 85+ (semantic match)
console.log(result.scoringMethod);  // 'embedding'
```

### Batch Scoring

```javascript
const cachedPrompts = [
  'What is Python?',
  'How to learn programming?',
  'Tell me about JavaScript'
];

const scores = await embeddingScorer.scoreRelevanceBatch(
  cachedPrompts,
  'machine learning algorithms',
  fallbackJaccardScorer
);

// Returns: [15, 25, 35] (relevance scores)
```

### Preloading for Performance

```javascript
// Preload embeddings for frequently used prompts
await validator.preloadEmbeddings([
  'How do I use Python?',
  'Explain machine learning',
  'What is the cloud?'
]);

// Later retrievals are faster (no API calls)
const result = await validator.validate(entry, context);
```

## Performance Characteristics

| Operation | Latency | Notes |
|-----------|---------|-------|
| Cached lookup | <1ms | In-memory embedding cache |
| API call | 200-500ms | First retrieval, cached after |
| Jaccard fallback | <5ms | No network |
| Cosine similarity | <0.1ms | Vector math |

**Caching Impact**: After 100 unique prompts, 90%+ requests are cache hits (<1ms)

## Metrics & Monitoring

### Get Embedding Scorer Statistics

```javascript
const stats = validator.getEmbeddingStats();

console.log(stats);
// {
//   cacheHits: 450,
//   cacheMisses: 50,
//   apiCalls: 45,
//   fallbacks: 5,
//   hitRate: '90.0%',
//   cacheSize: 495,
//   ready: true
// }
```

### Understanding the Metrics

- **cacheHits**: Embeddings retrieved from memory (fast)
- **cacheMisses**: First time seeing these prompts
- **apiCalls**: OpenAI API requests made
- **fallbacks**: Switched to keyword scoring due to API failure
- **hitRate**: Percentage of requests served from cache
- **cacheSize**: Number of unique embeddings cached
- **ready**: Whether embeddings are enabled

## Failure Handling

### API Error Recovery

If OpenAI API fails:

1. **Automatic Fallback** (if enabled):
   ```javascript
   const validator = new CacheValidator({
     enableFallbackScoring: true  // Default
   });
   // Falls back to Jaccard similarity automatically
   ```

2. **Fail Fast** (if disabled):
   ```javascript
   const validator = new CacheValidator({
     enableFallbackScoring: false
   });
   // Throws error, stops scoring
   ```

### Common Issues & Solutions

**No API key provided**
```
[EmbeddingScorer] No API key provided, embeddings disabled
Solution: Set OPENAI_API_KEY environment variable
```

**API timeout**
```
Configuration:
- timeout: 10000ms (default)
- batchSize: 100 (requests per batch)

Solution: Increase timeout or reduce batch size
```

**Cache full**
```
Max cache size: 10000 embeddings (default, ~100MB memory)
Eviction: LRU (least recently used) removed first

Solution: Increase maxCacheSize or clear periodically
```

## Tuning for Your Use Case

### High-Precision Matching (Legal, Medical)

```javascript
new CacheValidator({
  useEmbeddings: true,
  embeddingModel: 'text-embedding-3-large',  // Higher precision
  minRelevanceScore: 85  // Higher threshold
})
```

### High-Volume Caching (Chat, Support)

```javascript
new CacheValidator({
  useEmbeddings: true,
  embeddingModel: 'text-embedding-3-small',  // Faster, cheaper
  maxCacheSize: 50000  // Large cache
})
```

### Resource-Constrained Environment

```javascript
new CacheValidator({
  useEmbeddings: false,  // Disable embeddings
  enableFallbackScoring: true  // Use keyword only
})
```

## Testing

### Mock Embeddings in Tests

```javascript
const scorer = new EmbeddingScorer({ apiKey: null });

// Uses Jaccard fallback scoring
const score = await scorer.scoreRelevance(
  'cached prompt',
  'current prompt',
  (a, b) => scorer._jaccard(a, b)
);
```

### Unit Tests

```bash
npm test -- tests/embedding-scorer.test.js
npm test -- tests/cache-validator.test.js
```

## Cost Estimation

OpenAI Embedding Costs (text-embedding-3-small):

- **Price**: $0.02 per 1M tokens
- **Average prompt**: 50-200 tokens
- **Cost per 1000 API calls**: ~$0.10
- **Monthly budget** (1M cache calls):
  - API calls: ~10K (90% cache hit rate)
  - Cost: ~$1

## Migration from Keyword-Only Scoring

### Gradual Rollout

```javascript
// Phase 1: Enable with fallback (safe)
new CacheValidator({
  useEmbeddings: true,
  enableFallbackScoring: true,
  minRelevanceScore: 70  // Same threshold
});

// Phase 2: Monitor metrics
const stats = validator.getEmbeddingStats();
if (stats.fallbacks > stats.apiCalls * 0.1) {
  // More than 10% fallbacks, investigate issues
}

// Phase 3: Increase threshold
new CacheValidator({
  useEmbeddings: true,
  minRelevanceScore: 75  // Higher threshold for better matches
});
```

### Rollback Plan

If embeddings cause issues:

```javascript
// Quick disable
new CacheValidator({
  useEmbeddings: false
});
// Falls back to keyword-only scoring automatically
```

## Roadmap

- [ ] Support for local embedding models (Ollama)
- [ ] Redis backend for cross-process caching
- [ ] Configurable embedding providers (other API services)
- [ ] Batch preloading from database
- [ ] Adaptive threshold tuning based on metrics
