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
node scripts/cache-command.js cache-status

# Clear cache
node scripts/cache-command.js cache-clear --all --yes

# Configure settings
node scripts/cache-command.js cache-config --set maxSize 1073741824
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
- **[STRUCTURE.md](STRUCTURE.md)** — Detailed architecture and file organization
- **[SHIPPING_CHECKLIST.md](SHIPPING_CHECKLIST.md)** — Pre-deployment verification

## Testing

Run all tests:
```bash
npm test
```

Run specific test file:
```bash
npm test -- tests/cache-management.test.js
```

Run with coverage:
```bash
npm test -- --coverage
```

## Configuration Examples

### Development
```javascript
configure({
  maxSize: 50 * 1024 * 1024,      // 50 MB
  maxEntries: 1000,
  defaultTTL: 1 * 60 * 60 * 1000, // 1 hour
  evictionPolicy: 'FIFO'
});
```

### Production
```javascript
configure({
  maxSize: 2 * 1024 * 1024 * 1024,  // 2 GB
  maxEntries: 50000,
  defaultTTL: 3 * 24 * 60 * 60 * 1000, // 3 days
  evictionPolicy: 'LRU'
});
```

See [CONFIGURATION.md](docs/CONFIGURATION.md) for full guide with presets.

## Performance

- **Retrieval**: O(1) by ID, O(n) for search
- **Storage**: O(1) amortized
- **Typical hit rate**: 60-85% in stable workflows
- **Memory**: Configurable, default 100 MB
- **Eviction policies**: LRU (default), LFU, FIFO

## Known Limitations

- **In-memory only**: Cache lost on process restart
- **Single process**: Not shared across multiple processes
- **Large caches**: Search performance degrades >50k entries
- **No persistence**: No built-in backup/recovery

For persistence, see [Architecture Guide](STRUCTURE.md#Storage).

## Contributing

When modifying cache behavior:
1. Update relevant tests in `tests/`
2. Update documentation in `docs/`
3. Run full test suite to verify
4. Update FOLLOW_UP_ITEMS.md with any discovered work

## License

MIT
