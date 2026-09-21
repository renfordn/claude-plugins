# Plugin-Harness: Hook Contracts & Capabilities

**Version:** 1.0  
**Last Updated:** 2026-09-16

## Overview

Plugin-harness provides hooks for coordinating multi-agent workflows and ensuring all errors are observable.

## Hooks

### Before_Continue Hook (Setup_Workflow_State)

**Matcher:** Session initialization (manual before first agent spawn)

**Input:**
```
{
  "tool_name": "Agent",
  "tool_input": { "prompt": "...", "description": "...", "subagent_type": "..." },
  "cwd": "."
}
```

**Output:**
- Cache state in `workflow_state["orchestration"]`:
  - `capability_map_snapshot`: Available plugins and their capabilities
  - `nelly_brief_cache`: Project context and Intent Hash
  - `checkpoints`: Pre-spawn state snapshots
  - `error_lessons`: Prior phase errors for next agent

**Guarantees:**
- Idempotent: safe to call multiple times
- Graceful degradation: no errors raised on network failure
- Non-blocking: cache structure created even if fetch fails

**Error Handling:**
- Network timeout: logs warning, continues with empty brief
- File I/O failure: logs warning, continues with empty cache
- Missing INTEROP.md: logs warning, skips that plugin's contract

### Subagent_Stop Hook

**Matcher:** After agent completion

**Input:**
```
{
  "agent_type": "agent-tdd",
  "report": "agent output containing phase markers",
  "workflow_state": { ... }
}
```

**Output:**
- Update `workflow_state["orchestration"]["handoff_history"]`
- Write to `error_registry.json` (JSON lines format)
- Return systemMessage to user if errors detected

**Guarantees:**
- Never blocks agent completion (always exit 0)
- Validates contracts in strict order: hard deps → soft deps → payload
- Observable errors: all failures logged to error_registry.json

**Error Handling:**
- Hard dependency unavailable: set escalation_marker, halt workflow
- Soft dependency unavailable: log warning, continue with degraded state
- Contract violation: log error, surface in systemMessage, set rollback_pending

## Capabilities

### → Agent-ISDD

Orchestrator routes to agent-isdd for requirements and design phases.

**Handoff Fields:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| workflow_state | object | yes | Full orchestrator state including error_lessons and nelly_brief_cache |
| capability_map_snapshot | object | yes | Available plugins |
| error_lessons | array | yes | Errors from prior phases |

### → Agent-TDD

Orchestrator routes to agent-tdd for implementation phases.

**Handoff Fields (validated):**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| requirements_md | string | yes | Full approved requirements.md |
| design_md | string | yes | Full approved design.md |
| research_cache | object | yes | Research findings (design_findings, task_findings, file_summaries, git_hashes) |
| recap_md | string | yes | Summarized recap of known risks and blockers |

**Optional Context Fields (passed through, not validated):**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| error_lessons | array | no | Errors from prior phases |
| nelly_brief_cache | object | no | Cached project context from agent-nelly |

### → Code-Reviewer

Orchestrator routes to code-reviewer for quality gates.

**Handoff Fields:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| implementation | string/object | yes | Code to review |
| error_lessons | array | no | Implementation errors from agent-tdd |
| high_risk_slices | array | no | Slices marked for extra scrutiny |

## Error Types

- **CONTRACT_VIOLATION** (critical, blocking): Capability contract mismatch → escalate
- **DEPENDENCY_UNAVAILABLE** (warn, soft): Optional plugin missing → degrade gracefully
- **INFRASTRUCTURE_ERROR** (critical, non-recoverable): File corruption, I/O failure → pause workflow

## Example: Error Flow

```
Agent-ISDD completes with contract violation
  ↓
subagent_stop detects and logs error
  ↓
error_registry.json updated
  ↓
systemMessage returned to user with recovery guidance
  ↓
rollback_pending set in workflow_state
  ↓
before_continue detects rollback and surfaces to next spawn
```

## Performance

- Hook execution: < 10ms typical
- Error logging: < 5ms typical
- Brief fetch (on miss): < 500ms typical

---

**For implementation details, see:**
- orchestrator/hooks/before_continue.py (setup_workflow_state)
- orchestrator/hooks/subagent_stop.py (hook entrypoint & validation)
- orchestrator/error_logger.py (ErrorRegistry for error persistence)
