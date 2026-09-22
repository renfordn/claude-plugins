# Agent-Cache Plugin — Roadmap

Genuinely still-open future work, carried forward from the retired `FOLLOW_UP_ITEMS.md`
(deleted as a stray one-time status doc — see `docs/first-class-backlog.md` item 5). Everything
below was unimplemented as of 2026-09-22 (confirmed against `skills/`, which has no
`analytics`, `adaptive-ttl`, `cache-warming`, `multi-tenant`, or `monitoring-export` skill).
Items from the old doc already shipped (persistent storage, embedding-based scoring, metrics
dashboard, `skills/cache-sharing`, `audit-logger.js`) are not repeated here — see `CHANGELOG.md`
for what's actually landed.

## Open ideas

- **Real-world integration testing** — validate against live workflows with 1K+ real queries;
  only synthetic-data testing exists today.
- **Full audit/compliance logging** — `skills/audit-logger.js` exists, but SOC 2/GDPR-grade
  retention policy, data residency options, and compliance export are not built.
- **Rewrite `docs/CONFIGURATION.md` and audit `docs/API.md`** — both largely predate the SQLite
  rewrite and document settings and behaviour that no longer exist (`maxSize`,
  `evictionPolicy`, `backend`, `persistenceEnabled`, …). `CONFIGURATION.md` carries an accuracy
  warning pointing at `commands/cache-config.md` until it is rewritten.
- **Finish `commands/cache-dashboard.js`** — it exports a bare class, is not routed in
  `scripts/cache-command.js`, and its `_generateChartData()` returns `Math.random()` values, so
  it is deliberately not exposed as a `/cache-dashboard` command. Either give it real
  time-series data from `cache_events` and wire it into the CLI router, or delete it.
- **Advanced reporting & analytics** — hit-rate-by-dimension reports, token-savings ROI
  analysis, anomaly detection; `metrics-tracker` covers basic stats only.
- **Further retrieval performance work** — bloom filters for miss detection, batch
  store/invalidate operations, parallel search for very large caches.
- **Adaptive TTL optimization** — tune TTL per entry type from age/hit-count correlation.
- **Cache warming & preloading** — detect recurring task patterns, pre-warm during idle periods.
- **Multi-tenant isolation & quotas** — per-tenant partitioning and usage tracking, for SaaS
  deployment.
- **Additional eviction policies** — ARC, W-TinyLFU, time-decay, or cost-aware eviction beyond
  the current LRU/LFU/FIFO set.
- **External monitoring integration** — Datadog/New Relic/CloudWatch/Prometheus metrics export.
- **Sibling-plugin key/value transport** — a local socket or `store`/`retrieve` verbs on
  `scripts/cache-command.js` so non-Node callers (e.g. agent-isdd's Python hooks) could cache
  scoped state. The `phase_state_cache` contract that assumed an HTTP server on
  `localhost:7771` was retired 2026-09-22 because that server never existed.
- **GraphQL API** — alternative to the current CLI surface (there is no REST surface).

None of these are committed or scheduled; this is an idea list, not a plan of record.
