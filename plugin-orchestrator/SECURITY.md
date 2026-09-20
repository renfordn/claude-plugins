# plugin-orchestrator Security Review

**Date:** 2026-09-20  
**Scope:** MCP server (`mcp_server/server.py`), hook state helpers (`hooks/hook_state.py`)  
**Reviewer:** Claude Sonnet 4.6 (automated audit)

## MCP Server Audit

### 1. Network Binding

**Finding: CLEAN — stdio transport only, no TCP/UDP socket.**

`mcp_server/server.py` uses `FastMCP` from the `mcp` package and calls `mcp.run()` with no
arguments, which defaults to stdio transport. The server communicates exclusively over
stdin/stdout pipes established by the Claude Code host process at spawn time. No TCP or UDP
socket is opened; there is no bind address to harden.

### 2. Authentication

**Finding: CLEAN — OS-level process isolation is the auth boundary.**

Because the server uses stdio transport, only the process that spawned it (Claude Code) can
communicate with it. There are no unauthenticated network endpoints. MCP protocol-level auth is
managed by the host; no additional auth layer is needed or applicable.

### 3. File Access Scope

**Finding: CLEAN — read-only, path traversal impossible.**

The sole MCP tool (`get_spawn_context`) reads one file: the active `workflow-state.json` under
`~/.claude/.../sdd-memory/<project-slug>/`. The `cwd` parameter supplied by the caller is
passed through `project_slug(cwd)`, which applies:

```python
re.sub(r"[^A-Za-z0-9]+", "-", absp).strip("-").lower()
```

Path separators (`/`) and all special characters are replaced with `-` before any path join,
making traversal (e.g. `../../etc`) structurally impossible — the slug can only produce a
subdirectory name within the fixed `BASE` directory. No writes are performed.

### 4. Dependency Surface

`mcp_server/requirements.txt` pins `mcp<2`. The `mcp` package itself is a third-party
dependency; keep it updated. The server has no other runtime imports beyond the stdlib and
plugin-internal modules.

## Residual Notes (non-blocking)

- **`agent_type` parameter** is accepted but unused (logged comment in docstring confirms this
  is intentional — "informational only").
- The `mcp` package version constraint (`<2`) should be re-evaluated when mcp 2.x stabilises
  to avoid falling behind security fixes.

## Sign-off

All three audit criteria (network binding, authentication, file access scope) are **CLEAN**.
No remediation required for this server.
