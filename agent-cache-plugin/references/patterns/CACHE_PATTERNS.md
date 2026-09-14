# Cache Patterns & Heuristics

## Overview
This document describes recommended patterns and heuristics for effective cache usage in Agent-Cache.

## 1. Relevance Scoring Patterns

### Keyword Overlap Scoring
Simple but effective for initial filtering:
- Split prompt into keywords (length > 3)
- Calculate Jaccard similarity: `intersection / union`
- Score: `(keyword_overlap * 100) %`
- Threshold: 70-80% for semantic match

### Embedding-based Scoring
More sophisticated approach using semantic similarity:
- Generate embeddings for prompt and cached entries
- Calculate cosine similarity: `dot(v1, v2) / (|v1| * |v2|)`
- Score: `(cosine_similarity + 1) / 2 * 100` (normalize to 0-100)
- Threshold: 75-85% for strong semantic match

### Hybrid Scoring
Combine keyword and embedding scores:
```
relevance = 0.3 * keyword_score + 0.7 * embedding_score
```

## 2. Cache Entry Classification

### Highly Cacheable
- Research summaries (stable, not time-dependent)
- Code analysis outputs (stable, reusable)
- Design discussions (stable, good for reference)
- Error pattern analysis
- Long-running validations

**Suggested TTL:** 7 days

### Moderately Cacheable
- Task planning and slicing
- Test generation
- Code review findings
- Complexity analysis

**Suggested TTL:** 3 days

### Conditionally Cacheable
- Real-time data queries (require freshness flag)
- User-specific outputs (isolate by user ID)
- Time-sensitive analysis
- Market/pricing information

**Suggested TTL:** 4-24 hours (depends on change frequency)

### Non-Cacheable
- Responses to `noCache: true` parameter
- Random or stochastic outputs
- Current time/date dependent
- Live system status queries
- One-time credentials or tokens

## 3. Tagging Strategy

### Hierarchical Tags
Use dot notation for categorization:
```
agent.tdd.implementation     // Agent type
task.research                // Task category
domain.backend               // Domain
language.typescript          // Language/tech
complexity.high              // Complexity level
user.specific                // User-specific
```

### Search Optimization
- Use tags to narrow search scope
- Combine tags for precise queries
- Tag frequency drives hit rates

## 4. TTL Calculation Heuristics

### Based on Content Type
```
simple_analysis      → 7 days
medium_analysis      → 3 days
complex_reasoning    → 1 day
high_risk_decisions  → 4 hours
time_sensitive       → 1 hour
```

### Based on Volatility
- Stable content (language docs) → 30 days
- Semi-stable (API patterns) → 7 days
- Volatile (code examples) → 1 day
- Highly volatile (real-time data) → 1 hour

### Override Strategy
Parameters can override defaults:
```javascript
{
  taskType: 'implementation',
  cacheTTL: 12 * 60 * 60 * 1000,  // 12 hours override
  noCache: false
}
```

## 5. Cache Invalidation Strategies

### TTL-based (Passive)
- Entries expire after TTL
- Checked on access
- Minimal overhead
- Staleness risk

### Hit-count based (Active)
- Remove zero-hit entries after N days
- Remove low-hit entries if cache full
- Requires metrics tracking
- Balances freshness and capacity

### LRU Eviction (Capacity)
- Evict least recently used when cache full
- Maintains high-value entries
- Predictable performance
- Good for size-limited caches

### Hybrid Approach (Recommended)
```
1. Remove expired entries (TTL)
2. Remove zero-hit entries (3+ days)
3. If still over limit: LRU eviction
4. Refresh high-value entries' timestamps
```

## 6. Hit Rate Optimization

### Minimum Viable Cache (MVP)
- Start with simple keyword scoring (70% threshold)
- TTL: 24 hours
- Tag by: agentType, taskType
- Monitor hit rates

### Progressive Enhancement
- Week 1: Review top cache misses
- Week 2: Adjust thresholds based on false positives
- Week 3: Add embedding-based scoring for high-value tasks
- Week 4: Fine-tune by domain/language

### Target Metrics
- Hit rate: 15-25% (varies by workload)
- Average tokens saved per hit: 200-500
- Cache retrieval time: <5ms

## 7. Parameter Isolation

### By User
```javascript
tags: [..., `user.${userId}`]
```
Prevents privacy leaks in shared caches.

### By Project
```javascript
tags: [..., `project.${projectId}`]
```
Isolates cache by project scope.

### By Domain
```javascript
tags: [..., `domain.${domain}`]
```
Groups semantically related entries.

## 8. Performance Considerations

### Cache Lookup Time
- Keyword search: ~1-5ms
- Embedding search: ~10-50ms (depends on model)
- Hybrid search: ~15-60ms

### Trade-offs
- Faster lookup = simpler scoring (keyword)
- Better relevance = expensive scoring (embedding)
- Balance: Use keyword for pre-filtering, embedding for ranking

### Optimization Tips
1. Limit search results with `limit` parameter
2. Use time windows to reduce search scope
3. Index by agentType/taskType for faster queries
4. Cache embedding vectors separately

## 9. Troubleshooting Patterns

### Low Hit Rate
- Increase relevance threshold (more false negatives)
- Add embedding-based scoring
- Review top missed opportunities
- Improve tagging strategy

### High False Positives
- Decrease relevance threshold
- Add constraint checking (parameter compatibility)
- Implement validation layer
- Use cache-validator agent

### Cache Size Growing
- Reduce TTL values
- Increase hit rate threshold
- Review low-value entries
- Implement aggressive eviction policy

## 10. Monitoring & Analytics

### Key Metrics
- **Hit Rate:** `hits / total_queries`
- **Token Savings:** `sum(tokens_saved_per_hit)`
- **Retrieval Time:** `p50/p95/p99 of lookup_time`
- **Cache Efficiency:** `tokens_saved / cache_size`

### Alerts
- Hit rate dropping below 10%
- Cache size exceeding limits
- Retrieval time > 100ms
- High false positive rate (>10%)

### Regular Review (Weekly)
1. Check hit rate trends
2. Identify top cache misses
3. Analyze false positives
4. Review storage efficiency
5. Adjust parameters based on patterns
