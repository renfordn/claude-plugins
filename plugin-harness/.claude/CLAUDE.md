# Plugin Harness - Claude Project Guide

## Project Overview

**plugin-harness** is a type-safe, high-performance routing and handoff system for multi-agent AI workflows. It orchestrates handoffs between specialized plugins (agents) while maintaining strict contracts and ensuring sub-millisecond latencies.

**Key Design Principle:** Plugins don't know about each other—the orchestrator knows how to connect them safely based on their declared capabilities.

## Architecture

### High-Level Design

```
┌──────────────────────────────────────────────────────────────┐
│                    Workflow Orchestration                     │
├──────────────────────────────────────────────────────────────┤
│                                                                │
│  PluginRouter (Core Orchestrator)                             │
│  ├─ route_to_next_plugin()      [O(1) phase-based routing]   │
│  ├─ validate_handoff()           [Contract validation]        │
│  └─ check_plugin_availability()  [Plugin readiness detection] │
│                                                                │
│  ↓ consumes                      ↓ produces                  │
│                                                                │
│  CapabilityMap (Plugin Registry)                              │
│  ├─ get_plugin()                 [Fetch plugin metadata]     │
│  ├─ find_capability()            [Locate specific capability]│
│  └─ is_soft_dependency()         [Check if optional]         │
│                                                                │
│  ↑ parses                        ↑ maintains                 │
│                                                                │
│  INTEROP.md Files (Plugin Contracts)                          │
│  ├─ agent-isdd/INTEROP.md        [Spec-driven design agent] │
│  ├─ agent-tdd/INTEROP.md         [Test-driven dev agent]     │
│  ├─ code-reviewer/INTEROP.md     [Code review agent]         │
│  ├─ agent-nelly/INTEROP.md       [Memory system (optional)]  │
│  ├─ agent-ux/INTEROP.md          [UI renderer (optional)]    │
│  └─ agent-cache-plugin/INTEROP.md [Caching (optional)]       │
│                                                                │
└──────────────────────────────────────────────────────────────┘
```

### Workflow Example

```
1. agent-isdd
   ├─ Generates: design_spec_handoff (spec + requirements)
   └─ Capability: design_spec_handoff

2. PluginRouter.validate_handoff()
   ├─ Checks: design_spec_handoff capability exists in isdd
   ├─ Checks: design_spec_slicing capability exists in tdd
   ├─ Validates: payload contains required fields
   └─ Result: ✓ Valid handoff

3. PluginRouter.route_to_next_plugin()
   ├─ Current: agent-isdd with phase "design_approved"
   ├─ Decision: Route to agent-tdd
   └─ Next: agent-tdd (implementation phase)

4. agent-tdd
   ├─ Consumes: design_spec from isdd
   ├─ Produces: sliced_specs + TDD phases
   └─ Capability: design_spec_slicing

5. PluginRouter.validate_handoff()
   ├─ Checks: design_spec_slicing capability exists in tdd
   ├─ Checks: code_review capability exists in code-reviewer
   ├─ Validates: sliced_specs + phases present
   └─ Result: ✓ Valid handoff

6. PluginRouter.route_to_next_plugin()
   ├─ Current: agent-tdd with phase "implementation_complete"
   ├─ Decision: Route to code-reviewer
   └─ Next: code-reviewer (quality gates phase)

7. code-reviewer
   ├─ Consumes: sliced_specs + implementation
   ├─ Produces: review_feedback + approval
   └─ Capability: code_review

8. PluginRouter.route_to_next_plugin()
   ├─ Current: code-reviewer with phase "review_complete"
   ├─ Decision: No more targets
   └─ Result: Workflow complete ✓
```

## Component Details

### PluginRouter

**Responsibility:** Orchestrate plugin handoffs with full contract validation and route decisions.

**Key Methods:**
- `validate_handoff()` - Validate contracts before handoff (O(1) complexity)
- `route_to_next_plugin()` - Determine next plugin based on phase (O(1) lookup)
- `check_plugin_availability()` - Check if plugin is ready (pattern matching, <0.001ms)

**SLAs:**
- Handoff validation: <0.5ms (typical: 0.001ms)
- Routing decision: <0.1ms (typical: <0.001ms)
- Complete chain (3 handoffs): <100ms (typical: <0.01ms)

### CapabilityMap

**Responsibility:** Parse INTEROP.md files and maintain queryable capability registry.

**Key Methods:**
- `get_plugin()` - Fetch plugin with all capabilities
- `find_capability()` - Locate specific capability by ID
- `validate_input()` - Check input against consumes contract

**Features:**
- Graceful degradation: Missing INTEROP files don't crash system
- Change detection: MD5 hashes of INTEROP files for cache invalidation
- Caching: Can save/load from workflow-state.json for faster startup

**Initialization:** 0.34ms (SLA: <30ms) - One-time cost, negligible per session

### INTEROP.md Format

Each plugin exposes its capabilities via INTEROP.md:

```markdown
# agent-isdd Capabilities

## Design Spec Handoff

### design_spec_handoff

**Description:** Hand off design spec to implementation agent

**Consumes:**
- requirements_md: string
- design_md: string
- research_cache: object
- recap_md: string

**Produces:**
- design_spec: object
- design_decisions: array

## → agent-tdd

Next plugin in workflow (can hand off to agent-tdd)
```

## Handoff Contracts

### Contract Validation

All handoffs must satisfy contracts defined in INTEROP.md:

```python
# Handoff is valid if:
# 1. Source capability exists (agent-isdd.design_spec_handoff)
# 2. Target capability exists (agent-tdd.design_spec_slicing)
# 3. Payload contains ALL required fields from consumes contract
# 4. No type mismatches (checked at runtime, not serialized)

is_valid, error = router.validate_handoff(
    "agent-isdd", "design_spec_handoff",
    "agent-tdd", "design_spec_slicing",
    {
        "requirements_md": "...",
        "design_md": "...",
        "research_cache": {},
        "recap_md": "..."
    }
)
```

### Contract Guarantees

- **Field presence:** Validation checks ONLY field presence, not content
- **Type safety:** Types are declared but NOT enforced at validation time
- **Extensibility:** Extra fields in payload are ignored (forward-compatible)
- **Performance:** Constant-time O(1) validation regardless of payload size

## Testing Strategy

### Unit Tests
- **test_core.py** (9 tests): Router core functionality
- **test_interop_parser.py** (8 tests): INTEROP parsing and capability lookup
- **test_edge_cases.py** (21 tests): Plugin unavailability, circular deps, missing capabilities
- **test_observability.py** (18 tests): Logging, metrics, audit trails, SLA compliance
- **test_integration_agent_stubs.py** (9 tests): Complete workflows with agent stubs

### Performance Tests
- **test_performance_profiling.py** (9 benchmarks): Latency, throughput, cache efficiency
- **PERFORMANCE.md** (comprehensive report): SLA analysis, scaling characteristics

### Coverage
- ✅ 206 total tests, all passing
- ✅ Core workflows (isdd → tdd → reviewer)
- ✅ Soft dependency handling (nelly absent, ux missing, cache-plugin missing)
- ✅ Error recovery and graceful degradation
- ✅ Sub-millisecond SLA compliance verified

## Dependency Analysis

### Hard Dependencies (Required)
- **agent-isdd**: Spec-driven design
- **agent-tdd**: Test-driven implementation
- **code-reviewer**: Quality gates

Workflow blocks if any hard dependency is unavailable.

### Soft Dependencies (Optional)
- **agent-nelly**: Memory system (optional, improves context)
- **agent-ux**: UI rendering (optional, nice-to-have)
- **agent-cache-plugin**: Prompt-caching and context-deduplication (optional, nice-to-have)

Workflow continues if soft dependencies are unavailable—graceful degradation.

## Cloud Session Bootstrap (Required First Step)

All 6 plugins live together in one repo, `renfordn/claude-plugins` (one subdirectory per
plugin: `agent-isdd/`, `agent-tdd/`, `code-reviewer/`, `agent-nelly/`, `agent-ux/`,
`agent-cache-plugin/`), migrated there from separate repos specifically to make cloud bootstrap
cheaper — see that repo's README for why. As an installed plugin, `hooks/bootstrap-plugins.sh`
clones it into `${CLAUDE_PLUGIN_DATA}/claude-plugins` (plugin-harness's own data directory), and
`CapabilityMap()` reads from there. When developing *in this repo*, `.claude/settings.json` sets
`CLAUDE_PLUGINS_DIR` to your existing checkout instead, and both the bootstrap script and
`CapabilityMap()` use that.

`renfordn/claude-plugins` is currently **public**, so this session's git proxy serves anonymous
reads (clone/fetch) of it directly — the hook's plain `git clone` succeeds on its own with no
`add_repo` call needed. `add_repo` on a public repo is a no-op for permissions (confirmed: it
reports read access already available and attaches nothing).

**If the repo is ever made private**, anonymous reads stop working and this changes: at the
start of every new cloud session, before relying on the hook's clone having worked, check
whether the `CLAUDE_PLUGINS_DIR` checkout exists with all 6 plugin subdirectories. If not, call
`add_repo` (owner `renfordn`, repo `claude-plugins`) — this is a session-scoped grant, not a
persistent whitelist, so it must be called again in *every* fresh session, not just once — then
`git clone https://github.com/renfordn/claude-plugins "$CLAUDE_PLUGINS_DIR"` directly (not into
the session's default workspace). `add_repo` grants session-wide git-proxy access, so this one
clone covers all 6 plugins, and a subsequent hook-issued `git clone`/`pull` to that path will also
succeed for the rest of that same session.

Either way, a failed clone no longer aborts the session: `bootstrap-plugins.sh` warns and
continues for all 6 plugins, hard or soft (only a missing `python3` still hard-fails the hook).
It still takes out all 3 hard dependencies — `agent-isdd`, `agent-tdd`, `code-reviewer` — plus
the soft ones, `agent-nelly`, `agent-ux`, and `agent-cache-plugin`, for the rest of that session,
since there's no partial-success case with one repo; `PluginRouter`/`Subagent_Stop` still enforce
hard-dependency blocking at handoff time (see "Dependency Analysis" and "Validation Order" below),
so a missing hard dependency surfaces there instead of at bootstrap.

The former per-plugin repos (`renfordn/agent-isdd`, `agent-tdd`, `code-reviewer`, `agent-nelly`,
`agent-ux`, `agent-cache-plugin`) are archived and no longer updated — do not add_repo or clone
those individually.

## Performance Characteristics

### Sub-Millisecond Latencies

| Operation | Typical | SLA | Headroom |
|-----------|---------|-----|----------|
| Initialization | 0.34ms | <30ms | 88x |
| Availability check | <0.001ms | <0.1ms | 100x |
| Validation | 0.001ms | <0.5ms | 500x |
| Routing | <0.001ms | <0.1ms | 100x |
| Complete chain | <0.01ms | <100ms | 10000x |

### Throughput
- **Handoffs/second:** ~1.8M (tested with 100 complete chains)
- **Validations/second:** ~2M (tested with 1000 iterations)
- **Decisions/second:** ~7.5M (tested with 10000 iterations)

### Scalability
- **Plugins:** O(1) with routing table lookup (no degradation up to 100+ plugins)
- **Payload size:** O(1) constant-time validation (tested up to 500x baseline)
- **Memory:** Negligible overhead (~6 plugins, 4 capabilities, <1KB registry)

### No Performance Regressions
- SessionStart CI hook verifies SLAs on every commit
- Performance profiling tests included in test suite
- Latency baselines documented and tracked

## Code Style

### Naming Conventions
- **Plugins:** kebab-case (agent-isdd, code-reviewer)
- **Capabilities:** snake_case (design_spec_handoff)
- **Methods:** snake_case (route_to_next_plugin)
- **Constants:** UPPER_CASE

### Error Handling
- Validate inputs at system boundaries (user input, external APIs)
- Trust internal code and framework guarantees
- Prefer raising errors over returning None for validation failures
- Graceful degradation for optional/soft dependencies

### Testing
- Unit tests with fixtures (tests/fixtures/)
- Relative paths for portable tests
- Mock agent stubs for integration testing
- Performance benchmarks with baselines

## Development Workflow

### Branch Strategy
- Develop on `claude/project-next-steps-*` branch
- Commit with clear, descriptive messages
- Run full test suite before pushing
- CI verifies: tests pass, SLAs met, no regressions

### Before Committing
```bash
# Install dev/test-only dependencies first (redis, needed by test_state_store.py)
pip install -r requirements-dev.txt

# Run all tests
python3 -m unittest discover tests/ -v

# Run performance profiling
python3 -m unittest tests.test_performance_profiling -v

# Verify no SLA regressions
# (SessionStart hook does this automatically)
```

### Commit Message Format
```
Brief description of change (step name if applicable)

Detailed explanation of what changed, why, and any important context.
Include test counts and pass/fail status.

Co-Authored-By: Claude Haiku 4.5 <noreply@anthropic.com>
```

## API Documentation

See [API.md](../API.md) for complete API reference:
- CapabilityMap methods and examples
- PluginRouter methods and examples
- Data classes (PluginInfo, Capability)
- Error handling patterns
- Performance characteristics
- Best practices

## Observability

### Logging
- **orchestrator.interop_parser**: INTEROP file loading and parsing
- **orchestrator.core**: Routing decisions and validation failures

### Metrics
- Plugin availability checks (pattern matching latency)
- Handoff validation latency (field presence checking)
- Routing decision latency (phase-based lookup)
- Error rates (validation failures, missing capabilities)

### Audit Trails
- Handoff events (source, target, payload hash, result)
- Permission checks (plugin availability, capability access)
- Error events (type, severity, message)

### Telemetry Hooks
- Extensible event publishing system
- Multiple hooks can be registered
- Standard event structure with metadata
- Integration points for monitoring/alerting

## Hook Architecture

### Setup_Workflow_State (Before_Continue)

**When:** Session initialization, before first agent spawn

**Responsibilities:**
1. Fetch and cache nelly brief (Intent Hash + 1-hour TTL)
2. Build capability map snapshot
3. Create pre-spawn checkpoints
4. Initialize error_lessons for cross-phase sharing

**Key Features:**
- Idempotent: safe to call multiple times
- Graceful degradation: never blocks on network failure
- Intent Hash validation: refresh cache if Intent diverges

**Error Handling:**
- Network timeout → log warning, use stale cache or empty brief
- Missing INTEROP.md → log warning, skip that plugin
- I/O failure → log warning, create empty cache structure

### Subagent_Stop (Post-Agent Completion)

**When:** After any agent completes

**Responsibilities:**
1. Parse phase markers from agent report
2. Detect escalation markers (research gaps, contract violations)
3. Validate output against capability contract (with strict ordering)
4. Log handoff event to workflow-state
5. Persist errors to error_registry.json (JSON lines format)
6. Return systemMessage if errors detected

**Validation Order (strict):**
1. Hard dependencies unavailable → HALT (set escalation_marker)
2. Soft dependencies unavailable → LOG WARN, CONTINUE
3. Payload schema mismatch → CONTRACT_VIOLATION error

**Error Types:**
- **CONTRACT_VIOLATION** (critical): Required fields missing or invalid
- **DEPENDENCY_UNAVAILABLE** (warn): Optional plugin missing
- **INFRASTRUCTURE_ERROR** (critical): File corruption, I/O failure

**Error Observability:**
- All errors logged to error_registry.json (timestamps, severity, recovery actions)
- Errors surface in systemMessage to user (readable format, not JSON)
- Error lessons shared to next phase via workflow_state

## Known Limitations & Tradeoffs

### Validation Scope
- Field presence is validated, NOT field content
- Payload is NOT scanned or serialized (performance requirement)
- Type checking is NOT enforced at handoff time
- Extra fields in payload are silently ignored

### Dependency Management
- Soft dependencies cannot be marked as critical mid-workflow
- No dynamic dependency injection or plugin substitution
- Circular dependencies are detected but NOT automatically resolved
- No transaction/rollback semantics for workflows

### Scaling Considerations
- Routing table is in-memory (no distributed state)
- CapabilityMap is not auto-reloaded when INTEROP changes (manual refresh needed)
- No automatic plugin discovery (static registry only)

## Future Enhancements

### Priority 1 (High Impact)
- [ ] Production telemetry integration (Datadog, New Relic)
- [ ] Distributed workflow state tracking
- [ ] Plugin hot-reload without session restart

### Priority 2 (Medium Impact)
- [ ] Async validation for high-concurrency scenarios
- [ ] INTEROP file schema validation with JSON Schema
- [ ] Workflow history and rollback capability

### Priority 3 (Nice-to-Have)
- [ ] Plugin dependency injection for testing
- [ ] Dynamic routing policy customization
- [ ] Payload transformation and mapping

## Questions or Issues?

- Check [API.md](../API.md) for API reference
- See [PERFORMANCE.md](../PERFORMANCE.md) for performance details
- Review [test files](../tests/) for usage examples
- Check logger output in orchestrator.interop_parser and orchestrator.core

---

**Project Status:** Fully functional, production-ready. All 206 tests passing. All SLAs met with significant headroom. Sub-millisecond orchestration overhead.
