# Agent-Cache Plugin

Intelligent cache management for reducing token usage and improving performance across agent workflows.

## Overview

Agent-Cache provides a production-ready caching system that:
- Stores agent outputs and reasoning for reuse across tasks
- Validates cache relevance to current work with scoring
- Manages cache lifecycle with TTL-based expiration
- Tracks performance metrics (hit rate, token savings)
- Integrates via CLI commands and hooks

## Quick Start

### Installation

**Option 1: Local Development (Recommended)**
```bash
# Clone the repository
git clone https://github.com/renfordn/agent-cache-plugin.git
cd agent-cache-plugin

# Install dependencies
npm install

# Load into Claude Code as a local plugin
claude plugin add ./agent-cache-plugin
```

**Option 2: Direct Path Installation**
```bash
# If you have the plugin cloned locally
claude plugin add /absolute/path/to/agent-cache-plugin
```

**Note**: Claude Code currently requires local installation of plugins via `claude plugin add`. Direct git URL or npm installation is not yet supported by Claude Code's plugin system.

### Basic Usage

```javascript
const cacheManagement = require('./skills/cache-management');

// Store a result
const stored = await cacheManagement.store({
  prompt: 'Refactor this code',
  output: { refactoredCode: '...' },
  metadata: { agentType: 'agent-refactor', ttl: 3 * 24 * 60 * 60 * 1000 }
});

// Retrieve it later
const result = await cacheManagement.retrieve(stored.entryId);
if (result.found) {
  console.log('Cache hit:', result.entry.output);
}
```

### CLI Commands

```bash
# Check cache status
node scripts/cache-command.js status

# Clear cache
node scripts/cache-command.js clear --all --yes

# Configure settings
node scripts/cache-command.js config --set maxEntries 50000
```

## Architecture

### Directory Structure

```
agent-cache-plugin/
├── skills/                      # Core cache operations
│   ├── cache-management/        # Store, retrieve, search, invalidate
│   ├── cache-orchestration/     # Decide when to use cache
│   ├── cache-validation/        # Score relevance and validate
│   └── metrics-tracker/         # Track performance
├── commands/                    # CLI command definitions
├── scripts/                     # CLI entry points
├── hooks/                       # Integration hooks
│   ├── pre-agent-execution/    # Check cache before running
│   ├── post-agent-completion/  # Store results after execution
│   └── cache-invalidation/     # Handle eviction and cleanup
├── tests/                       # Test suites
├── docs/                        # Documentation
│   ├── API.md                  # API reference
│   ├── CONFIGURATION.md        # Configuration guide
│   └── TROUBLESHOOTING.md      # Troubleshooting guide
├── plugin.json                  # Plugin manifest
└── README.md                    # This file
```

### Skills

**cache-management** — Core cache operations
- `store()`: Save entries with auto-generated IDs
- `retrieve()`: Get entries by ID with expiration checking
- `search()`: Find entries by tags, pattern, age
- `invalidate()`: Remove entries by ID or pattern
- `stats()`: Get cache health metrics
- `configure()`: Update limits and policies

**cache-orchestration** — Intelligent cache usage
- Decides cache vs. fresh reasoning based on relevance
- Scores entry relevance to current task
- Checks staleness and conflicts
- Proposes fallback strategies

**cache-validation** — Cache quality assurance
- Five-layer validation model
- Relevance scoring
- Confidence assessment
- Recommendation system

**metrics-tracker** — Performance monitoring
- Hit/miss tracking
- Token savings calculation
- Timing measurements
- Cost analysis

### Hooks

**pre-agent-execution** — Check cache before agent runs
- Retrieves cached results for matching prompts
- Validates relevance to current task
- Returns cached output or proceeds to execution

**post-agent-completion** — Store results after execution
- Automatically caches agent outputs
- Extracts metadata (agent type, task type, complexity)
- Sanitizes sensitive parameters before storage

**cache-invalidation** — Manage cache lifecycle
- Removes stale entries (expired TTL)
- Enforces size/entry limits
- Handles eviction policies

## Documentation

- **[API.md](docs/API.md)** — Complete API reference with examples
- **[CONFIGURATION.md](docs/CONFIGURATION.md)** — Configuration guide with presets
- **[TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)** — Common issues and solutions
- **[STRUCTURE.md](STRUCTURE.md)** — Detailed architecture, file organization, and this plugin's INTEROP capability contract
- **[ROADMAP.md](docs/ROADMAP.md)** — Open, not-yet-built ideas

## Testing

Requires Node >= 22 (`better-sqlite3` 13). Tests are isolated from your real cache: `jest.config.js`
points `CLAUDE_PLUGIN_DATA` at a throwaway temp dir for the whole run, so nothing under
`~/.claude/plugin-data/` is read or written.

Run all tests:
```bash
npm test
```

Run specific test file:
```bash
npm test -- tests/sqlite-cache.test.js
```

Run with coverage:
```bash
npm test -- --coverage
```

## Configuration

Four settings, persisted in the cache DB's `config` table and shared by every process:

| Key | Default | Range |
|-----|---------|-------|
| `maxEntries` | 10000 | ≥ 100 |
| `defaultTTL` | 3d | ≥ 1m |
| `relevanceThreshold` | 75 | 50–95 |
| `stalenessThreshold` | 1d | ≥ 1m |

```bash
node scripts/cache-command.js config --list
node scripts/cache-command.js config --set defaultTTL 7d
node scripts/cache-command.js config --reset
```

From Node code:
```javascript
const { getSingleton } = require('./skills/sqlite-cache');
getSingleton().configure({ maxEntries: 50000, defaultTTL: 3 * 24 * 60 * 60 * 1000 });
```

There is no `maxSize` or `evictionPolicy`: the SQLite backend evicts LRU by entry count and
does not track bytes. See [commands/cache-config.md](commands/cache-config.md).

## Performance

- **Retrieval**: O(1) by key (primary-key lookup), O(n) for `search()`
- **Storage**: O(1) amortized, with LRU eviction once `maxEntries` is reached
- **Typical hit rate**: 60-85% in stable workflows
- **Eviction**: LRU by entry count

## Known Limitations

- **Single SQLite file**: one `cache.db` under `CLAUDE_PLUGIN_DATA`; not shared across machines
- **Large caches**: `search()` degrades past ~50k entries (no full-text index)
- **No byte accounting**: entry size is not tracked, so size-based limits are not available
- **No backup/recovery tooling**: the DB is a plain file; back it up yourself

See [Architecture Guide](STRUCTURE.md#Storage) for the storage layer.

## Contributing

When modifying cache behavior:
1. Update relevant tests in `tests/`
2. Update documentation in `docs/`
3. Run full test suite to verify
4. Update `docs/ROADMAP.md` with any discovered future work

## License

See [LICENSE](LICENSE).
