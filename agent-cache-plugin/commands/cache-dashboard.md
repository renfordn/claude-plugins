---
description: Generate an HTML dashboard of cache hit rate, token savings, and request volume
keywords: [dashboard, metrics, visualization, charts]
version: 1.0.0
---

# Command: /cache-dashboard

Generate an interactive HTML dashboard from real `cache_events` data — the
same source `/cache-status` reads. Covers hit rate trend, cumulative tokens
saved, and request volume over the last 24 hours, plus cache status and
recommendations. Retrieval latency is not instrumented anywhere in this
plugin yet, so latency stat cards show "Not tracked" rather than invented
numbers.

## Usage
```
/cache-dashboard [--output FILE]
```

## Run
```bash
CLAUDE_PLUGIN_DATA="${CLAUDE_PLUGIN_DATA}" node "${CLAUDE_PLUGIN_ROOT}/scripts/cache-command.js" dashboard [options]
```
Pass `CLAUDE_PLUGIN_DATA` explicitly -- the Bash tool doesn't have it, and the script refuses to guess a data directory.

## Options
- `--output FILE` - Destination for the generated HTML (default: `cache-dashboard.html`)

## Example
```
/cache-dashboard --output dashboard.html
```
Then open `dashboard.html` in a browser.

## Related Commands
- `/cache-status` - Text/JSON/CSV/HTML summary of the same metrics
- `/cache-config` - Configure cache settings
