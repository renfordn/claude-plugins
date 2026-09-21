# Plugin Collection Security Review

**Date:** 2026-09-20  
**Scope:** All 7 plugins — agent-isdd, agent-nelly, agent-tdd, agent-ux, code-reviewer,
plugin-harness, agent-cache-plugin  
**Reviewer:** Claude Sonnet 4.6 (automated review) + renfordn  
**Status:** ✅ SIGNED OFF — no open blockers

---

## 1. Threat Model

### 1.1 Attack Surface Summary

| Plugin | Runtime | External Network | File I/O | Third-party Deps |
|---|---|---|---|---|
| agent-isdd | Python (hooks) | None | `~/.claude/sdd-memory/` read/write | None (stdlib only) |
| agent-nelly | Python (hooks) | None | `~/.claude/agent-nelly-memory/` read/write | None (stdlib only) |
| agent-tdd | Python (hooks) | None | `~/.claude/agent-tdd-state/` read/write | None (stdlib only) |
| agent-ux | None (skills only) | None | None | None |
| code-reviewer | Python (hooks) | None | Project files read-only | None (stdlib only) |
| plugin-harness | Python (hooks) + MCP server | None (stdio MCP) | `~/.claude/.../sdd-memory/` read/write | `redis` (dev/optional), `mcp<2` (MCP server only) |
| agent-cache-plugin | Node.js | None | `~/.claude/plugin-data/` read/write | `better-sqlite3` (production) |

**No plugin opens an inbound network listener.** All external communication is either:
- Outbound only, initiated by the Claude Code host (never by the plugins themselves), or
- Stdio IPC (plugin-harness MCP server), which is OS-level process isolation.

### 1.2 Trust Boundaries

```
Claude Code host (trusted)
  │
  ├─ Hook subprocesses (Python/Node) — spawned with the user's own OS privileges
  │    └─ Read/write confined to ~/.claude/ plugin-data and project dirs
  │
  ├─ plugin-harness MCP server — stdio pipe, no TCP/UDP socket
  │    └─ Read-only access to workflow-state.json
  │
  └─ agent-cache-plugin CLI commands — Node.js, path-validated DB writes
       └─ DB confined to CLAUDE_PLUGIN_DATA or ~/.claude/plugin-data/
```

### 1.3 Threat Vectors Considered

| Vector | Applicable plugins | Finding |
|---|---|---|
| Path traversal via user-supplied paths | agent-cache-plugin, plugin-harness | Both mitigated (see §2) |
| DB file world-readable | agent-cache-plugin | Mitigated — chmod 0600 on create (see §2) |
| MCP server binding to public interface | plugin-harness | N/A — stdio transport only |
| Unauthenticated MCP endpoints | plugin-harness | N/A — stdio transport only |
| Dependency CVE in production code | agent-cache-plugin | Mitigated — `npm audit fix` applied 2026-09-20 |
| Dependency CVE in dev/test code | agent-cache-plugin | Mitigated — `npm audit fix` applied 2026-09-20 |
| Hook code injection via workflow-state.json | All hooks | Low risk — state is deserialized as data, never eval'd |
| Privilege escalation | All | Not applicable — plugins run as the invoking user |

---

## 2. Security Findings and Remediations

### 2.1 Path Traversal — agent-cache-plugin `getSingleton()` ✅ FIXED

**Finding (commit e024db8):** `getSingleton(dbPath)` accepted arbitrary paths including
relative traversal sequences (e.g. `../../etc/evil`).

**Fix:** Added `_assertAllowedPath(dbPath)` which resolves the path with `path.resolve()` and
asserts it starts with `CLAUDE_PLUGIN_DATA` (or `~/.claude/plugin-data` if unset). The
`:memory:` sentinel bypasses the check for tests. Any out-of-scope path throws before a DB
is opened.

**Verification:** `agent-cache-plugin/tests/sqlite-cache.test.js` — "Security — path
sanitization" describe block, 3 tests (relative traversal, absolute out-of-scope, `:memory:`
sentinel).

### 2.2 DB File Permissions — agent-cache-plugin ✅ FIXED

**Finding (commit e024db8):** SQLite DB file was created with default umask permissions
(typically 0644), world-readable on shared-user systems.

**Fix:** `fs.chmodSync(dbPath, 0o600)` called in `CacheManager` constructor immediately after
the `new Database(dbPath)` call. Wrapped in try/catch for read-only filesystem graceful
degradation.

**Verification:** `agent-cache-plugin/tests/sqlite-cache.test.js` — "Security — DB file
permissions" describe block, 1 test asserting mode === 0o600.

### 2.3 MCP Server Network Binding — plugin-harness ✅ CONFIRMED CLEAN

**Finding (commit 6899052):** Audited `mcp_server/server.py` for TCP/UDP socket binding.

**Result:** `FastMCP("plugin-harness").run()` uses stdio transport by default. No
`host=` or `port=` argument is passed. No HTTP server library is imported. The server is
unreachable from any network interface.

**Verification:** `plugin-harness/tests/test_mcp_server_security.py` — 8 tests passing
(2 skip cleanly when `mcp` package not installed).

**Detail:** See `plugin-harness/SECURITY.md` for full audit narrative.

### 2.4 MCP Server `cwd` Parameter — plugin-harness ✅ CONFIRMED CLEAN

**Finding:** The `get_spawn_context(agent_type, cwd)` tool accepts a caller-supplied `cwd`.

**Result:** `hook_state.project_slug(cwd)` strips all non-alphanumeric characters (including
path separators) before the value is used in any file path join. Traversal sequences like
`../../etc` are reduced to `etc` within `~/.claude/.../sdd-memory/`. File writes via this
path do not occur — the tool is read-only.

---

## 3. Dependency Audit

### 3.1 npm — agent-cache-plugin

**Audit date:** 2026-09-20  
**Tool:** `npm audit` (npm 11.x)  
**Result after fix:** 0 vulnerabilities

**Pre-fix finding (resolved):**

| Package | Severity | CVE | Affected range | Direct? | Fixed in |
|---|---|---|---|---|---|
| js-yaml | High | [GHSA-2883-xcg3-v3hh](https://github.com/advisories/GHSA-2883-xcg3-v3hh) | `>=3.0.0 <3.15.2`, `>=4.0.0 <4.3.2` | No (via `@istanbuljs/load-nyc-config`) | js-yaml 3.15.2 / 4.3.2 |

**CWE:** CWE-400 (Uncontrolled Resource Consumption), CWE-407  
**CVSS:** 7.5 (High) — DoS via crafted YAML with empty merge keys; no confidentiality/integrity impact  
**Risk to production:** **None** — js-yaml is not a production dependency (`dependencies`).
It is a transitive dev-dependency through `eslint` → `@istanbuljs/load-nyc-config`. It is
never loaded when the plugin is installed by an end user.  
**Remediation:** `npm audit fix` applied 2026-09-20, upgrading js-yaml to 4.3.2 / 3.15.2.

**Production dependency surface (post-fix):**

| Package | Version | Purpose | CVEs |
|---|---|---|---|
| better-sqlite3 | 13.0.3 | SQLite driver | None known |

### 3.2 pip — plugin-harness

**Audit date:** 2026-09-20  
**Tool:** Manual CVE check (pip-audit unavailable in environment)  
**Result:** No known vulnerabilities

| Package | Version constraint | Installed | Purpose | CVEs |
|---|---|---|---|---|
| redis | `>=5.0,<9` | 8.1.0 (dev-only) | RedisStateStore unit tests | None known |
| mcp | `>=1.2,<2` | 1.x (MCP server only) | stdio MCP protocol | None known |

**Notes:**
- `redis` is a dev/test-only dependency. Production hooks (`before_continue.py`,
  `subagent_stop.py`) are stdlib-only and carry zero third-party dependencies.
- The `mcp<2` constraint should be re-evaluated when mcp 2.x stabilises; the current
  constraint prevents accidental upgrade to the 2.x API which changed the FastMCP interface.

### 3.3 Plugins with zero third-party dependencies

agent-isdd, agent-nelly, agent-tdd, agent-ux, code-reviewer — all hooks and skill files are
pure Python (stdlib) or Markdown. No `requirements.txt`, no `package.json` production deps.
Dependency surface: **zero**.

---

## 4. Per-Plugin Threat Summary

### agent-isdd

- **File I/O:** Reads/writes `~/.claude/sdd-memory/<project-slug>/` — scoped to memory dir,
  slugs are sanitised with `re.sub(r"[^A-Za-z0-9]+", "-", ...)`.
- **Hook inputs:** `workflow-state.json` is parsed as data (JSON), never executed.
- **Verdict:** ✅ Clean

### agent-nelly

- **File I/O:** Reads/writes `~/.claude/agent-nelly-memory/<project-slug>/` — same slug
  sanitisation as agent-isdd.
- **Verdict:** ✅ Clean

### agent-tdd

- **File I/O:** Reads project files (scoped to invocation cwd) and writes
  `~/.claude/agent-tdd-state/`. No user-supplied paths used in file operations.
- **Verdict:** ✅ Clean

### agent-ux

- **Runtime:** Skills only (Markdown). No hooks, no file I/O, no deps.
- **Verdict:** ✅ Clean

### code-reviewer

- **File I/O:** Reads project files for review analysis. No writes outside project dir.
- **Verdict:** ✅ Clean

### plugin-harness

- **MCP server:** stdio transport, no network binding, read-only, cwd-parameter traversal
  mitigated. See §2.3–2.4 and `SECURITY.md`.
- **Hook I/O:** Writes `~/.claude/.../sdd-memory/` and error registry files, all within the
  plugin data directory.
- **Verdict:** ✅ Clean

### agent-cache-plugin

- **Path traversal:** Mitigated via `_assertAllowedPath()`. See §2.1.
- **DB permissions:** Mitigated via `chmod 0600`. See §2.2.
- **Dependency CVE:** Resolved via `npm audit fix`. See §3.1.
- **Verdict:** ✅ Clean

---

## 5. Sign-off

All seven plugins have been audited. No open security blockers remain.

| Check | Result |
|---|---|
| Path traversal vectors | ✅ Mitigated |
| File permission hardening | ✅ Applied |
| MCP network exposure | ✅ Confirmed stdio-only |
| npm audit | ✅ 0 vulnerabilities (post-fix) |
| pip audit | ✅ No known CVEs |
| Hook input handling | ✅ Data only, never executed |
| Privilege scope | ✅ User-level only, no escalation |

**Signed off:** renfordn, 2026-09-20
