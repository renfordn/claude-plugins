# Plugin Hooks Pattern: Unified Permission Model

A standardized approach for managing plugin_data permissions, audit trails, and state rotation across the Claude Agent ecosystem.

---

## Section 1: Overview

### Problem
Multiple plugins (agent-nelly, agent-isdd, agent-tdd, future plugins) need to safely manage plugin-specific data under `~/.claude/plugin-data/`. Without coordination:
- Each plugin repeats permission logic (code duplication)
- Security checks are inconsistent (file-type blocking, namespace enforcement)
- Audit trails are incomplete (no traceability of what accessed what)
- State files grow unbounded (no rotation policy)
- Cross-agent access is not consistently denied (security gap)

### Solution
A shared, three-layer architecture:
1. **Permission layer**: File-type validation, namespace enforcement
2. **Audit layer**: Traceable decision logging
3. **Rotation layer**: Bounded history with archive support

All plugins inherit the same security model, reducing surface area and enabling consistent audit trails across the ecosystem.

---

## Section 2: Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ Plugin (agent-nelly, agent-isdd, agent-tdd, future)         │
│ ├─ PreToolUse Hooks (permission gates)                      │
│ └─ PostToolUse Hooks (audit logging)                        │
└─────────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────┐
│ Validators (plugin_data_whitelist.py)                        │
│ ├─ File-type blocker (.exe check)                           │
│ ├─ Namespace enforcer (agent-specific directory)            │
│ └─ Audit logger factory (entry creation)                    │
└─────────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────┐
│ State Files (~/.claude/plugin-data/<agent>/)                │
│ ├─ Active state (write operations)                          │
│ ├─ Audit entries (operation log)                            │
│ └─ Archive (rotated old entries)                            │
└─────────────────────────────────────────────────────────────┘
```

**Three Layers:**
1. **Permission checks**: Validator gates allow/deny based on file type and namespace
2. **Audit logging**: Decisions and operations logged with timestamp + metadata
3. **Rotation**: Bounded history in active file; old entries moved to archive.json

---

## Section 3: Implementation Guide

### Step 1: Import Shared Validators

```python
from plugin_data_whitelist import (
    create_whitelist_validator,
    create_audit_logger,
    should_use_env_gate
)
```

**Three key functions:**
- `create_whitelist_validator(check_namespace: bool = True)` — Returns a validator callable
- `create_audit_logger()` — Returns a logger callable
- `should_use_env_gate(gate_var: str)` — Checks if an env-var is set

### Step 2: Create Allow-Only Hook

```python
def main():
    # Check env-gate first (short-circuit to allow)
    if os.environ.get("YOUR_GATE", "").lower() in ("off", "0", "false", "disabled"):
        allow("Gate disabled")

    # Load payload
    payload = json.load(sys.stdin)
    file_path = payload.get("tool_input", {}).get("file_path", "")
    
    # Use validator to check file type and namespace
    validator = create_whitelist_validator(check_namespace=True)
    validation = validator(file_path=file_path, operation="write", plugin_name="your-plugin")
    
    if not validation.get("allowed"):
        no_decision()  # Block by not allowing
    
    allow(f"Your plugin permission: {file_path} is in your namespace")
```

### Step 3: Create Deny-Only Hook

```python
PLUGIN_DATA_BASE = os.path.join(os.path.expanduser("~"), ".claude", "plugin-data")
ALLOWED_AGENT = "your-plugin"
_AGENT_PATTERN = re.compile(
    r"^" + re.escape(os.path.normpath(PLUGIN_DATA_BASE)) + 
    re.escape(os.sep) + r"([^" + re.escape(os.sep) + r"]+)"
)

def main():
    # Check env-gate
    if os.environ.get("YOUR_GATE", "").lower() in ("off", "0", "false", "disabled"):
        allow()

    payload = json.load(sys.stdin)
    file_path = payload.get("tool_input", {}).get("file_path", "")
    
    # Extract agent name from path
    m = _AGENT_PATTERN.match(file_path)
    if not m:
        no_decision()  # Not under plugin-data
    
    agent_name = m.group(1)
    if agent_name == ALLOWED_AGENT:
        no_decision()  # Let allow hook handle it
    
    deny(f"Cross-agent access denied: cannot write to {agent_name} namespace")
```

### Step 4: Register in hooks.json

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Write|Edit|MultiEdit",
        "hooks": [
          {
            "type": "command",
            "command": "python3 \"${CLAUDE_PLUGIN_ROOT}/hooks/your_slug_guard.py\""
          },
          {
            "type": "command",
            "command": "python3 \"${CLAUDE_PLUGIN_ROOT}/hooks/your_plugin_write.py\""
          }
        ]
      }
    ]
  }
}
```

**Important:** Slug guard (deny) always comes before write hook (allow).

### Step 5: Add Tests

```python
def test_allow_own_namespace(self):
    """Writes to plugin's namespace should be allowed."""
    target = os.path.join(home, ".claude", "plugin-data", "your-plugin", "state.json")
    payload = {"tool_input": {"file_path": target}, "cwd": "/some/project"}
    proc = run_hook(payload)
    assert proc.returncode == 0
    assert "allow" in json.loads(proc.stdout)["hookSpecificOutput"]["permissionDecision"]

def test_deny_cross_namespace(self):
    """Writes to other plugin's namespace should be denied."""
    target = os.path.join(home, ".claude", "plugin-data", "agent-nelly", "state.json")
    payload = {"tool_input": {"file_path": target}, "cwd": "/some/project"}
    proc = run_hook(payload)
    assert proc.returncode == 0
    assert "deny" in json.loads(proc.stdout)["hookSpecificOutput"]["permissionDecision"]

def test_block_executables(self):
    """Executable files should be blocked."""
    target = os.path.join(home, ".claude", "plugin-data", "your-plugin", "malware.exe")
    payload = {"tool_input": {"file_path": target}, "cwd": "/some/project"}
    proc = run_hook(payload)
    assert proc.returncode == 0
    assert proc.stdout.strip() == ""  # No decision (blocked)
```

### Step 6: Document in Your Plugin

- Create `YOUR_PLUGIN_HOOKS.md` (or similar)
- Reference this pattern document
- List your specific env-gate name and namespace
- Include examples from your codebase

---

## Section 4: File-Type Restrictions

### Current Blocklist
- `.exe` — Executable files (Windows)

**Blocked by:** `plugin_data_whitelist.py:BLOCKED_FILE_TYPES`

### How to Extend

1. **Add to blocklist** in `plugin_data_whitelist.py`:
```python
BLOCKED_FILE_TYPES = {".exe", ".sh", ".bat", ".cmd"}
```

2. **Propagate to all agents:**
   - Update `agent-nelly/hooks/plugin_data_whitelist.py`
   - Update `agent-isdd/hooks/plugin_data_whitelist.py`
   - Update `agent-tdd/hooks/plugin_data_whitelist.py`
   - Update any future plugin copies

3. **Test**:
```python
validator = create_whitelist_validator()
result = validator("/path/to/file.sh", "write", "your-plugin")
assert not result["allowed"]
```

### Why Block Executables?
Plugin-data should contain configuration, state, and caches — never executable code. Blocking .exe (and eventually .sh, .bat, etc.) prevents accidental or malicious code injection into the plugin-data tree.

---

## Section 5: Directory Scoping

### Per-Agent Namespace
Each plugin gets its own directory under `~/.claude/plugin-data/`:

```
~/.claude/plugin-data/
├─ agent-nelly/      ← agent-nelly writes here only
│  ├─ state.json
│  └─ ...
├─ agent-isdd/       ← agent-isdd writes here only
│  ├─ state.json
│  └─ ...
├─ agent-tdd/        ← agent-tdd writes here only
│  ├─ state.json
│  └─ ...
└─ future-plugin/    ← future plugin writes here only
   ├─ state.json
   └─ ...
```

### Namespace Enforcement
The validator checks that:
1. Path contains `plugin-data/<plugin-name>/` pattern
2. Plugin name matches the one making the request
3. Path doesn't escape the namespace via `../` tricks

**In code:**
```python
plugin_namespace = f"plugin-data{os.sep}agent-nelly{os.sep}"
if plugin_namespace not in normalized_path:
    return {"allowed": False, "reason": "Cross-namespace access denied"}
```

---

## Section 6: Audit Trail

### What Is Logged

Each audit entry captures:
- **timestamp** — When the decision was made (time.time())
- **plugin_name** — Which plugin made the request (e.g., "agent-nelly")
- **operation** — "read", "write", or "delete"
- **file_path** — Full path to the file
- **allowed** — True if permitted, False if denied
- **reason** — Explanation (e.g., "Namespace valid" or "Executable blocked")

### Example Audit Entry
```json
{
  "timestamp": 1693017600.123456,
  "plugin_name": "agent-nelly",
  "operation": "write",
  "file_path": "/Users/user/.claude/plugin-data/agent-nelly/state.json",
  "allowed": true,
  "reason": "File type allowed, namespace valid"
}
```

### Rotation Policy

**Active file:** `~/.claude/plugin-data/<agent>/hook_history.json` (capped at 1000 entries)

**Trigger:** When active history reaches 1001 entries
- Oldest 1000 entries move to `hook_history.archive.json`
- Newest 1 entry stays in active file
- Archive grows without limit (full audit trail)

**Why rotate?** Large JSON files slow down reads/writes. Rotation keeps active file small while preserving audit trail in archive.

### Reading the Audit Trail
```python
from hook_history_rotate import HookHistoryManager

manager = HookHistoryManager(json_path)
recent_10 = manager.get(limit=10)  # Most recent 10, newest first

for entry in recent_10:
    print(f"{entry['timestamp']}: {entry['plugin_name']} {entry['operation']} "
          f"{entry['file_path']} → {'allowed' if entry['allowed'] else 'denied'}")
```

---

## Section 7: Testing Strategy

### Unit Tests (Validators)
```python
def test_file_type_blocking():
    """Validator should block .exe files."""
    validator = create_whitelist_validator(check_namespace=False)
    result = validator("/path/to/malware.exe", "write", "plugin")
    assert not result["allowed"]

def test_namespace_enforcement():
    """Validator should enforce plugin namespace."""
    validator = create_whitelist_validator(check_namespace=True)
    result = validator(
        "/home/user/.claude/plugin-data/agent-nelly/state.json",
        "write",
        "agent-isdd"
    )
    assert not result["allowed"]
```

### Integration Tests (Hooks)
```python
def test_hook_allows_own_namespace():
    """Hook should allow writes to own namespace."""
    target = os.path.join(home, ".claude", "plugin-data", "plugin-name", "state.json")
    proc = run_hook({"tool_input": {"file_path": target}, "cwd": cwd})
    assert json.loads(proc.stdout)["hookSpecificOutput"]["permissionDecision"] == "allow"

def test_hook_denies_cross_namespace():
    """Hook should deny writes to other namespace."""
    target = os.path.join(home, ".claude", "plugin-data", "agent-nelly", "state.json")
    proc = run_hook({"tool_input": {"file_path": target}, "cwd": cwd})
    assert json.loads(proc.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"
```

### Security Tests (Attack Scenarios)
```python
def test_path_traversal_blocked():
    """Path traversal via ../ should be blocked."""
    target = os.path.join(home, ".claude", "plugin-data", "plugin", "..", "agent-nelly", "state.json")
    proc = run_hook({"tool_input": {"file_path": target}, "cwd": cwd})
    # Should either normalize to own namespace or deny
    result = json.loads(proc.stdout)
    decision = result["hookSpecificOutput"]["permissionDecision"]
    assert decision in ["allow", "deny"]  # Not a crash

def test_symlink_escape():
    """Symlink escape attempts should be blocked by namespace check."""
    # Create symlink pointing outside plugin-data
    # Attempt to write through it
    # Validator should normalize path and still catch cross-namespace access
    pass
```

---

## Section 8: Examples

### Example 1: Agent-Nelly (Memory Directory)

**Allow hook** (`nelly_memory_permission.py`):
```python
validator = create_whitelist_validator(check_namespace=False)
validation = validator(file_path=norm, operation="write", plugin_name="agent-nelly")
if not validation.get("allowed"):
    no_decision()

# Check if path is under memory_dir or global_dir
if path_under_memory_dir(norm):
    allow("Agent Nelly memory permission: ...")
```

**Deny hook** (`nelly_slug_guard.py`):
```python
# Extract project slug from path
# If slug doesn't match canonical slug, deny
if wrong_slug(segment, canonical):
    deny("Agent Nelly slug guard: wrong project slug")
```

**Env-gate:** `NELLY_GATE=off` disables all checks

---

### Example 2: Agent-ISDD (Per-Feature Spec)

**Allow hook** (`memory_permission.py`):
```python
validator = create_whitelist_validator(check_namespace=False)
validation = validator(file_path=norm, operation="write", plugin_name="agent-isdd")

if path_under_spec_dir(norm):
    allow("SDD memory permission: ...")
```

**Deny hook** (`memory_slug_guard.py`):
```python
# Similar pattern to agent-nelly
if wrong_spec_slug(segment, canonical):
    deny("SDD slug guard: wrong feature slug")
```

**Env-gate:** `SDD_GATE=off` disables all checks

---

### Example 3: Agent-TDD (Plugin Data)

**Allow hook** (`plugin_data_write.py`):
```python
validator = create_whitelist_validator(check_namespace=True)
validation = validator(
    file_path=norm,
    operation="write",
    plugin_name="agent-tdd"
)

if validation.get("allowed"):
    allow("Agent-TDD plugin data permission: ...")
```

**Deny hook** (`plugin_data_slug_guard.py`):
```python
# Extract agent name from plugin-data path
if agent_name != "agent-tdd":
    deny("Agent-TDD slug guard: cross-agent write denied")
```

**Env-gate:** `TDD_GATE=off` disables all checks

---

## Section 9: Future Extensions

### Adding New File-Type Restrictions

1. **Identify the type** (e.g., `.sh` for shell scripts)
2. **Update blocklist** in all three `plugin_data_whitelist.py` copies
3. **Add test** for the new block
4. **Coordinate** with all plugins (shared validators auto-inherit)

**No hook changes needed** — validators are used by all plugins automatically.

### Adding Process-Identity Checks

Currently, the hooks trust the plugin name passed in. To add process-identity verification:

```python
def verify_process_identity(plugin_name: str) -> bool:
    """Verify that the calling process matches the declared plugin."""
    calling_pid = os.getppid()
    # Check if PID belongs to the declared plugin
    # (Implementation depends on plugin launch mechanism)
    return True
```

Then integrate into validator:
```python
if not verify_process_identity(plugin_name):
    return {"allowed": False, "reason": "Process identity mismatch"}
```

### Modifying Rotation Policy

Current: Rotate at 1000 entries (move oldest 1000 to archive, keep newest entries active).

To change:
1. **Update threshold** in `hook_history_rotate.py`:
   ```python
   HISTORY_CAP = 2000  # Up from 1000
   ARCHIVE_ROTATION_THRESHOLD = HISTORY_CAP + 1
   ```
2. **Update template** in `workflow-state.template.json` to document new cap
3. **Add tests** to verify new threshold

---

## Section 10: New Plugin Adoption Checklist

Use this checklist when adding a new plugin to the ecosystem:

### Pre-Implementation
- [ ] Define plugin name (e.g., `new-plugin-name`)
- [ ] Define env-gate name (e.g., `NEW_PLUGIN_GATE`)
- [ ] Identify plugin-data needs (state files, caches, audit logs)
- [ ] Plan namespace structure (`~/.claude/plugin-data/new-plugin-name/...`)

### Implementation
- [ ] Copy `plugin_data_whitelist.py` to `hooks/`
- [ ] Create `hooks/new_plugin_write.py` (allow-only hook)
- [ ] Create `hooks/new_plugin_slug_guard.py` (deny-only hook)
- [ ] Update `hooks/hooks.json` to register PreToolUse handlers
- [ ] Add `hooks/test_new_plugin_write.py` (unit + integration tests)
- [ ] Add `hooks/test_new_plugin_slug_guard.py` (security tests)

### Validation
- [ ] All tests pass (unit, integration, security)
- [ ] Backward compatibility verified (env-gate on/off)
- [ ] Cross-agent access explicitly denied
- [ ] Executables blocked
- [ ] Path traversal protection confirmed

### Documentation
- [ ] Create `NEW_PLUGIN_HOOKS.md` (or append to plugin docs)
- [ ] Reference `PLUGIN_HOOKS_PATTERN.md` for pattern details
- [ ] Document env-gate name and namespace structure
- [ ] Include example usage and test patterns
- [ ] Add to this document's "Examples" section

### Security Review
- [ ] Code review for permission logic
- [ ] Validator integration verified
- [ ] Namespace enforcement confirmed
- [ ] No cross-plugin data leakage possible

### Deployment
- [ ] All hooks deployed to all three agents (nelly, isdd, tdd)
- [ ] Hooks.json wired and tested
- [ ] Monitor initial hook runs for unexpected denials
- [ ] Audit trail verified (entries logged correctly)

---

## Quick Reference: Environment Gates

| Plugin | Gate Name | Values | Behavior |
|--------|-----------|--------|----------|
| agent-nelly | `NELLY_GATE` | `off`, `0`, `false`, `disabled` (case-insensitive) | Short-circuit to allow (skip validation) |
| agent-isdd | `SDD_GATE` | `off`, `0`, `false`, `disabled` (case-insensitive) | Short-circuit to allow (skip validation) |
| agent-tdd | `TDD_GATE` | `off`, `0`, `false`, `disabled` (case-insensitive) | Short-circuit to allow (skip validation) |

**Note:** Gates are meant for testing and backward compatibility, not for production use. Gates disabled = all security checks active.

---

## Related Documentation

- **[hook_history_rotate.py](agent-isdd/hooks/hook_history_rotate.py)** — HookHistoryManager for bounded history rotation
- **[plugin_data_whitelist.py](agent-nelly/hooks/plugin_data_whitelist.py)** — Shared validators and audit logger
- **[shared_slug.py](agent-nelly/hooks/shared_slug.py)** — Canonical project slug derivation
- **[nelly_memory_permission.py](agent-nelly/hooks/nelly_memory_permission.py)** — Reference implementation for memory dirs
- **[plugin_data_write.py](agent-tdd/hooks/plugin_data_write.py)** — Reference implementation for plugin-data
