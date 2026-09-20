# Tasks: Cache Plugin Greenfield Architecture

## Slice 1: SQLite CacheManager module

**Risk Tier:** standard  
**Depends On:** (none)  
**Files:** skills/sqlite-cache/schema.js, skills/sqlite-cache/index.js

### Test Intent
store() writes a row readable by retrieve(); TTL expiry returns null; LRU eviction removes oldest-accessed row; stats() returns counts from DB.

### Validation Target
`cd agent-cache-plugin && npx jest tests/sqlite-cache.test.js --no-coverage`

### Ordered Steps
1. Write schema.js: CREATE TABLE cache + cache_events + two indexes.
2. Write CacheManager class: constructor opens better-sqlite3 at given path (`:memory:` in tests), runSchema(), store(), retrieve(), invalidate(), stats(), enforce(), getSingleton()/resetSingleton().
3. TTL check: `created_at + ttl > Date.now()` in SELECT.
4. LRU evict: DELETE WHERE key IN (SELECT ... ORDER BY accessed_at ASC LIMIT n) before INSERT when count >= maxEntries.

---

## Slice 2: sanitize-deep.js utility

**Risk Tier:** standard  
**Depends On:** (none)  
**Files:** utils/sanitize-deep.js

### Test Intent
sanitizeDeep() redacts credential keys at arbitrary nesting depth; leaves non-credential keys unchanged; handles arrays; handles null/primitives safely.

### Validation Target
`cd agent-cache-plugin && npx jest tests/sanitize-deep.test.js --no-coverage`

### Ordered Steps
1. Write sanitizeDeep(obj): if primitive/null return as-is; if array map recursively; else sanitizeParameters(obj) then recurse over values.
2. Wrap utils/credential-sanitizer.js sanitizeParameters (unchanged).

---

## Slice 3: post-agent-completion.js rewrite (M2 + M3 write)

**Risk Tier:** standard  
**Depends On:** Slice 1, Slice 2  
**Files:** hooks/post-agent-completion.js

### Test Intent
Valid input causes a SQLite row to be written and a CACHE.md line appended; uncacheable input emits passthrough with exit 0; errors in DB write emit passthrough with exit 0 (never crash).

### Validation Target
`cd agent-cache-plugin && npx jest tests/post-agent-completion.test.js --no-coverage`

### Ordered Steps
1. Replace Map write with CacheManager.getSingleton(dbPath).store({...}).
2. Compute key = sha256(toolName + "\x00" + taskSlug + "\x00" + sha256(JSON.stringify(input))).
3. sanitizeDeep(output) before store and before CACHE.md write.
4. Append 6-line CACHE.md block; rotate at 500 KB (rename to .bak, start fresh).
5. On any error in DB/MD write: log stderr, emit writePostToolUse() passthrough, exit 0.
6. Keep determineCacheability/serializeOutput/buildTags/writePostToolUse shapes.

---

## Slice 4: cache-invalidation.js rewrite (TTL/LRU SQL)

**Risk Tier:** standard  
**Depends On:** Slice 1  
**Files:** hooks/cache-invalidation.js

### Test Intent
Running the hook deletes expired rows (TTL elapsed) and trims to maxEntries via LRU; emits { invalidated, entriesRemoved } JSON to stdout; exits 0 even on DB open error.

### Validation Target
`cd agent-cache-plugin && npx jest tests/cache-invalidation.test.js --no-coverage`

### Ordered Steps
1. Replace JS loop with: DELETE WHERE (created_at + ttl) < Date.now().
2. LRU trim: if count > MAX_ENTRIES, DELETE ... ORDER BY accessed_at ASC LIMIT (count - MAX_ENTRIES).
3. Prune cache_events older than 7 days.
4. Emit JSON result stdout; exit 0 (try/catch all).

---

## Slice 5: metrics-tracker rewrite (SQLite queries)

**Risk Tier:** standard  
**Depends On:** Slice 1  
**Files:** skills/metrics-tracker/index.js

### Test Intent
recordHit/recordMiss insert rows into cache_events; getHitRate() aggregates from DB; getTokenSavings() aggregates from DB; getRecommendations() threshold logic preserved.

### Validation Target
`cd agent-cache-plugin && npx jest tests/metrics-tracker.test.js --no-coverage`

### Ordered Steps
1. Rewrite MetricsTracker: constructor accepts db path (`:memory:` for tests).
2. recordHit()/recordMiss() INSERT into cache_events.
3. getHitRate() = SELECT COUNT(*) WHERE event_type='hit' / total.
4. getTokenSavings() = SELECT SUM/AVG/MAX token_count WHERE event_type='hit'.
5. getPerformanceMetrics() returns object with avgRetrievalTime etc.
6. getRecommendations() preserves hitRate < 0.1 and tokensSaved < 5000 thresholds.
7. getSingleton()/resetSingleton() export.

---

## Slice 6: cache-status command rewrite (SQLite read)

**Risk Tier:** standard  
**Depends On:** Slice 1, Slice 5  
**Files:** commands/cache-status.js

### Test Intent
execute() returns a text report with real totals from SQLite; _buildReport and formatters produce unchanged output shape.

### Validation Target
`cd agent-cache-plugin && npx jest tests/cache-status.test.js --no-coverage`

### Ordered Steps
1. Replace cacheManagement.getSingleton() with sqliteCache.getSingleton().
2. Replace metricsTracker.getSingleton() with new MetricsTracker(dbPath).
3. All _buildReport, _exportReport, _toHtml, _toCsv, _format* helpers unchanged.
4. getStats() call maps to CacheManager.stats() shape.

---

## Slice 7: plugin.json hooks block

**Risk Tier:** standard  
**Depends On:** Slice 3, Slice 4  
**Files:** .claude-plugin/plugin.json

### Test Intent
plugin.json contains a hooks array with PostToolUse entries for post-agent-completion and cache-invalidation; no PreToolUse entry present.

### Validation Target
`cd agent-cache-plugin && npx jest tests/manifest.test.js --no-coverage`

### Ordered Steps
1. Add "hooks" array with two PostToolUse entries.
2. Add "commands" array with cache-status, cache-clear, cache-config.
3. Verify no PreToolUse hook listed.

---

## Slice 8: M1 re-validation task (PreToolUse gate)

**Risk Tier:** standard  
**Depends On:** Slice 1  
**Files:** hooks/pre-agent-spawn.js

### Test Intent
Write a minimal PreToolUse hook that reads stdin, looks up SQLite, and either returns cached output path or passthrough. If it cannot run cleanly (schema bug still present), file is deleted and M1 is marked dropped.

### Validation Target
`cd agent-cache-plugin && npx jest tests/pre-agent-spawn.test.js --no-coverage`

### Ordered Steps
1. Rewrite pre-agent-spawn.js: read stdin, compute key, db.retrieve(key).
2. If hit: write output_blob to temp file, emit { permissionDecision: 'allow', tempFilePath }.
3. If miss: emit passthrough { permissionDecision: 'allow' }.
4. Try/catch all: on error emit passthrough, exit 0.
5. Run test — if harness schema bug causes failures, delete file and mark M1 dropped.
